import hashlib
import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.broker.intraday_inputs import REST_URL
from auto_invest.execution import intraday_qualification as q
from auto_invest.execution.intraday_rehearsal import rehearsal_session
from auto_invest.execution.intraday_selection import ResearchSelection
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.market_data.intraday import DataError

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("fault", [None, "offset_days", "missing_date", "unconfirmed_close"])
async def test_repeated_orders_match_dated_groups_without_fee_allocation(
        prepared, tmp_path, fault, monkeypatch):
    from auto_invest.persistence import audit

    args, selected, forward, _ = prepared
    forward["session_dates"] = ["2026-09-09", "2026-09-11"]
    # Research/forward authentication are isolated here; their independent
    # signed-source replay tests cover those producers. HTTP/ledger/model/guard
    # below are real, and no production authorization file is created.
    forward["market_source_authentication_verified"] = True
    forward["_interval_bars_json"] = json.dumps([
        dict(symbol="SPY", timestamp_utc=f"2026-09-{day}T14:00:00Z", open=101, volume=1000)
        for day in ("09", "10")
    ])
    async with rehearsal_session(tmp_path / "repeated.db") as book:
        authority, conn = book.engine.router.execution_authority, book.conn
        rows = []
        for index, day in enumerate(("09", "09", "10")):
            number = str(index)
            requested = 2 if fault == "unconfirmed_close" and index == 0 else 1
            rule = "intraday:" + selected.execution_identity + ":" + number
            conn.execute("""INSERT INTO orders
                (correlation_id,rule_id,symbol,side,order_type,qty,state,kis_order_id,
                 limit_price_usd,submitted_at_utc) VALUES(?,?,'SPY','BUY','LIMIT',?,
                 'FILLED',?,'102',?)""", (number, rule, requested, number,
                                        f"2026-09-{day}T14:01:00Z"))
            conn.execute("INSERT INTO fills(order_correlation_id,kis_fill_id,qty,price_usd,"
                         "executed_at_utc) VALUES(?,?,1,'101',?)",
                         (number, number, f"2026-09-{day}T14:01:00Z"))
            conn.execute("INSERT INTO intraday_execution_claims VALUES(?,?,?)", (
                number, selected.execution_identity, json.dumps(dict(symbol="SPY", side="BUY",
                    qty=requested, limit="102", signal_bar_end=f"2026-09-{day}T14:00:00Z",
                    decision_kind="SIGNAL")),
            ))
            conn.execute("INSERT INTO order_state_history(order_correlation_id,from_state,"
                         "to_state,ts_utc) VALUES(?,'INTENT','SUBMITTING',?)",
                         (number, f"2026-09-{day}T14:01:00Z"))
            audit.append(conn, audit.FillPayload(kis_fill_id=number, qty=1, price_usd="101",
                executed_at_utc=f"2026-09-{day}T14:01:00Z",
                broker_response_received_at_utc=f"2026-09-{day}T14:02:00Z"),
                correlation_id=number, symbol="SPY", rule_id=rule)
            rows.append(dict(odno=number, pdno="SPY", sll_buy_dvsn_cd="02", ovrs_excg_cd="AMEX",
                             ord_dt=f"202609{day}", ft_ord_qty=str(requested),
                             ft_ccld_qty="1", nccs_qty="0",
                             ft_ccld_unpr3="101", ord_dvsn="00", ord_unpr="102"))
        conn.commit()
        if fault == "missing_date":
            rows[0].pop("ord_dt")

        def handle(request):
            if request.url.path == "/oauth2/tokenP":
                return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
            assert request.method == "GET"
            if request.url.path.endswith("inquire-ccnl"):
                return httpx.Response(200, json=dict(rt_cd="0", output=rows))
            assert request.url.path.endswith("inquire-period-trans")
            report = []
            for day, qty in (("09", 1 if fault == "offset_days" else 2),
                             ("10", 2 if fault == "offset_days" else 1)):
                report.append(dict(trad_dt=f"202609{day}", sttl_dt="20260911", pdno="SPY",
                    crcy_cd="USD", sll_buy_dvsn_cd="02", ccld_qty=str(qty),
                    tr_frcr_amt2=str(qty * 101),
                    frcr_excc_amt_1=str(Decimal(qty * 101) + Decimal(".1")),
                    dmst_frcr_fee1="0.1", frcr_fee1="0"))
            return httpx.Response(200, headers={"tr_cont": "D"},
                                  json=dict(rt_cd="0", output1=report, output2=[]))

        async with httpx.AsyncClient(base_url=REST_URL,
                                    transport=httpx.MockTransport(handle)) as http:
            authority.broker._client = http
            source = q.ExecutionCostSource(authority, token_cache=tmp_path / "token.json",
                                           runtime_digest=args["runtime_digest"])
            args.update(account=authority.account_no, execution_source=source)
            if fault:
                with pytest.raises(DataError, match="QUALIFICATION_EXECUTION_COSTS_NOT_ACCEPTED"):
                    await q.prepare_qualification(**args)
            else:
                qualification = await q.prepare_qualification(**args)
            result = source.last_assessment
        if fault:
            reason = dict(offset_days="DATED_TRANSACTION_EXECUTION_TOTAL_MISMATCH",
                          missing_date="MULTIPLE_ORDERS_WITHOUT_REPORTED_DATES",
                          unconfirmed_close="BROKER_ORDER_NOT_CLOSED")[fault]
            assert reason in result.issues
        else:
            assert not result.issues
            groups = json.loads(result.fee_groups_json)
            assert sorted(len(group["order_ids"]) for group in groups) == [1, 2]
            intervals = json.loads(result.intervals_json)
            assert sum(entry["reported_fees"] is None for entry in intervals) == 2
            model = json.loads(qualification.interval_model_json)
            assert model["next_bar_fee_bound_verified"]
            assert model["next_bar_price_bound_verified"]
            assert not model["full_execution_parity_verified"]
            assert qualification.execution_model_verified()
            approval = grant(qualification)
            monkeypatch.setattr(q, "_read_authorization", lambda: approval)
            assert qualification() is None
            for field in (
                "interval_volume_verified", "next_bar_timing_verified",
                "model_fill_quantity_verified",
                "next_bar_price_bound_verified", "next_bar_fee_bound_verified",
                "registered_forward_replay_verified", "market_source_authentication_verified",
            ):
                for wrong in (False, None, 1):
                    changed = replace(qualification, interval_model_json=json.dumps(
                        dict(model, **{field: wrong}),
                    ))
                    assert changed() == "QUALIFICATION_EXECUTION_MODEL_EVIDENCE_MISSING", field
            for field in ("account_digest", "execution_identity", "cost_digest",
                          "source_attestation_basis", "model"):
                changed = replace(qualification, interval_model_json=json.dumps(
                    dict(model, **{field: "different"}),
                ))
                assert not changed.execution_model_verified(), field
            for field in ("issues", "timing_issues", "quantity_issues", "cost_issues"):
                changed = replace(qualification, interval_model_json=json.dumps(
                    dict(model, **{field: ["UNRESOLVED"]}),
                ))
                assert not changed.execution_model_verified(), field
            checks = json.loads(result.checks_json)
            for field in checks:
                changed = replace(qualification, execution_cost=replace(result,
                    checks_json=json.dumps(dict(checks, **{field: False})),
                ))
                assert not changed.execution_model_verified(), field
            unknown = replace(qualification, execution_cost=replace(result,
                missing_model_conditions=("NEW_UNSUPPORTED_CONDITION",),
            ))
            assert unknown() == "QUALIFICATION_EXECUTION_MODEL_EVIDENCE_MISSING"
            extra_check = replace(qualification, execution_cost=replace(result,
                checks_json=json.dumps(dict(checks, new_requirement=False)),
            ))
            assert not extra_check.execution_model_verified()
            duplicate = replace(qualification, interval_model_json=(
                qualification.interval_model_json[:-1] + ',"interval_volume_verified":true}'
            ))
            assert not duplicate.execution_model_verified()
            empty_claim = replace(qualification, interval_model_json="{}",
                                  execution_cost=replace(result, missing_model_conditions=()))
            assert empty_claim() == "QUALIFICATION_EXECUTION_MODEL_EVIDENCE_MISSING"
            monkeypatch.setattr(q, "_read_authorization", lambda: {})
            assert qualification.execution_model_verified()
            assert qualification() == "QUALIFICATION_AUTHORIZATION_MISMATCH"


@pytest.mark.parametrize("change", [None, "account", "strategy", "window", "fees", "ledger",
                                    "order_date", "missing_order_date", "quantity", "unfilled"])
@pytest.mark.parametrize("stored_bound", [False, True])
async def test_real_get_parsers_and_ledger_reach_qualification(
        prepared, tmp_path, change, stored_bound):
    # Research/forward acceptance is isolated by prepared; everything from HTTP
    # response parsing through SQLite reconciliation and qualification is real.
    args, selected, forward, _ = prepared
    forward["session_dates"] = ["2026-09-10", "2026-09-11"]
    calls = []
    async with rehearsal_session(tmp_path / "source.db") as book:
        authority = book.engine.router.execution_authority
        conn = authority.conn
        conn.execute("INSERT INTO intraday_execution_claims VALUES(?,?,?)", (
            "SPY", selected.execution_identity,
            json.dumps(dict(symbol="SPY", side="BUY", qty=2, limit="102",
                            signal_bar_end="2026-09-10T14:00:00Z", decision_kind="SIGNAL")),
        ))
        conn.execute("""INSERT INTO orders
            (correlation_id, rule_id, symbol, side, order_type, qty, state,
             kis_order_id, limit_price_usd, submitted_at_utc)
            VALUES ('cost-local', ?, 'SPY', 'BUY', 'LIMIT', 2, 'FILLED',
                    'cost-broker', '102', '2026-09-10T14:00:00Z')""",
                     ("intraday:" + ("wrong" if change == "strategy"
                                     else selected.execution_identity) + ":SPY",))
        conn.execute("""INSERT INTO fills
            (order_correlation_id, kis_fill_id, qty, price_usd, executed_at_utc)
            VALUES ('cost-local', 'cost-fill', 2, '101', '2026-09-10T14:01:00Z')""")
        conn.commit()

        conn.execute("""INSERT INTO order_state_history
            (order_correlation_id, from_state, to_state, ts_utc)
            VALUES ('cost-local', 'INTENT', 'SUBMITTING', '2026-09-10T14:01:00Z')""")
        conn.commit()

        if stored_bound:
            from auto_invest.persistence import audit
            audit.append(conn, audit.FillPayload(
                kis_fill_id="cost-fill", qty=2, price_usd="101",
                executed_at_utc="2026-09-10T14:01:00Z",
                broker_response_received_at_utc="2026-09-10T14:02:00+00:00",
            ), correlation_id="cost-local", symbol="SPY",
                rule_id="intraday:" + selected.execution_identity + ":SPY")
            conn.commit()

        if change == "unfilled":
            conn.execute("""INSERT INTO orders
                (correlation_id,rule_id,symbol,side,order_type,qty,state,kis_order_id,
                 limit_price_usd,submitted_at_utc)
                VALUES ('unfilled-local',?,'QQQ','BUY','LIMIT',2,'CANCELLED','unfilled-broker',
                        '102','2026-09-10T14:00:00Z')""",
                         ("intraday:" + selected.execution_identity + ":QQQ",))
            conn.execute("INSERT INTO intraday_execution_claims VALUES(?,?,?)", (
                "QQQ", selected.execution_identity,
                json.dumps(dict(symbol="QQQ", side="BUY", qty=2, limit="102",
                                signal_bar_end="2026-09-10T14:00:00Z", decision_kind="SIGNAL")),
            ))
            conn.commit()

        def handle(request):
            calls.append(request)
            if request.url.path == "/oauth2/tokenP":
                return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
            assert request.method == "GET"
            assert request.headers["authorization"] == "Bearer fresh"
            assert request.url.params["CANO"] == authority.account_no[:8]
            if request.url.path.endswith("inquire-ccnl"):
                rows = [dict(odno="cost-broker", pdno="SPY", sll_buy_dvsn_cd="02",
                             ord_dt="20260909" if change == "order_date" else "20260910",
                             ft_ord_qty="3" if change == "quantity" else "2",
                             ovrs_excg_cd="AMEX", ft_ccld_qty="2", nccs_qty="0",
                             ft_ccld_unpr3="101", ord_dvsn="00", ord_unpr="102")]
                if change == "missing_order_date":
                    rows[0].pop("ord_dt")
                if change == "unfilled":
                    rows.append(dict(rows[0], odno="unfilled-broker", pdno="QQQ",
                                     ft_ccld_qty="0", ft_ccld_unpr3="0", prcs_stat_name="취소완료"))
                return httpx.Response(200, json=dict(rt_cd="0", output=rows))
            assert request.url.path.endswith("inquire-period-trans")
            if change == "ledger":
                conn.execute("UPDATE orders SET limit_price_usd='103' "
                             "WHERE correlation_id='cost-local'")
                conn.commit()
            row = dict(trad_dt="20260910", sttl_dt="20260911", pdno="SPY", crcy_cd="USD",
                       sll_buy_dvsn_cd="02", ccld_qty="2", tr_frcr_amt2="202",
                       frcr_excc_amt_1="202.02", dmst_frcr_fee1="0.01", frcr_fee1="0.01")
            if change == "fees":
                row.update(frcr_excc_amt_1="212", dmst_frcr_fee1="9.99")
            if change == "window":
                row["sttl_dt"] = "20260912"
            return httpx.Response(200, headers={"tr_cont": "D"},
                                  json=dict(rt_cd="0", output1=[row], output2=[]))

        async with httpx.AsyncClient(base_url=REST_URL,
                                    transport=httpx.MockTransport(handle)) as http:
            authority.broker._client = http
            args["account"] = authority.account_no if change != "account" else "9999999901"
            source = q.ExecutionCostSource(authority, token_cache=tmp_path / "token.json",
                                           runtime_digest=args["runtime_digest"])
            args["execution_source"] = source
            if change and change not in {"missing_order_date", "unfilled"}:
                reason = ("QUALIFICATION_EXECUTION_BINDING_MISMATCH" if change == "account"
                          else "QUALIFICATION_EXECUTION_COSTS_NOT_ACCEPTED")
                with pytest.raises(DataError, match=reason):
                    await q.prepare_qualification(**args)
            else:
                result = await q.prepare_qualification(**args)
                assessment = result.execution_cost
                assert not assessment.issues
                checks = json.loads(assessment.checks_json)
                assert checks.pop("reported_order_trade_dates_match") is (
                    change != "missing_order_date"
                )
                assert all(checks.values())
                assert not assessment.public()["execution_parity_verified"]
                intervals = json.loads(assessment.intervals_json)
                assert len(intervals) == 1
                assert intervals[0]["before_submission"] == "2026-09-10T14:01:00+00:00"
                assert intervals[0]["quantity"] == 2
                assert intervals[0]["side"] == "BUY"
                assert intervals[0]["average_fill_price"] == "101"
                assert intervals[0]["reported_fees"] == "0.02"
                orders = json.loads(assessment.orders_json)
                by_id = {order["order_id"]: order for order in orders}
                filled_order = by_id["cost-broker"]
                assert filled_order["ordered_quantity"] == filled_order["filled_quantity"] == 2
                assert filled_order["signal_bar_end"] == "2026-09-10T14:00:00Z"
                if change == "unfilled":
                    assert len(orders) == 2
                    assert by_id["unfilled-broker"]["filled_quantity"] == 0
                    assert by_id["unfilled-broker"]["ordered_quantity"] == 2
                assert intervals[0]["response_received"]
                assert intervals[0]["signal_bar_end"] == "2026-09-10T14:00:00Z"
                timing = assessment.assess_interval_volume(
                    [], participation="0.01", observed_at="2026-09-12T00:00:00Z",
                )
                assert timing["next_bar_timing_verified"] is stored_bound
                if stored_bound:
                    assert intervals[0]["response_received"] == "2026-09-10T14:02:00+00:00"
                assert "ORDER_TRADE_DATE_LINK_NOT_PROVIDED" in assessment.missing_model_conditions
            assert len(calls) == 8  # token + 3 exchanges twice + transaction report
            if change is None:
                conn.execute("""INSERT INTO orders
                    (correlation_id,rule_id,symbol,side,order_type,qty,state,kis_order_id,
                     limit_price_usd,submitted_at_utc)
                    VALUES ('outside','other','QQQ','BUY','LIMIT',1,'FILLED','outside-broker',
                            '100','2026-09-09T14:00:00Z')""")
                conn.execute("""INSERT INTO fills
                    (order_correlation_id,kis_fill_id,qty,price_usd,executed_at_utc)
                    VALUES ('outside','outside-fill',1,'100','2026-09-09T14:01:00Z')""")
                conn.commit()
                repeated = await q.prepare_qualification(**args)
                assert repeated.execution_cost.digest == assessment.digest
                conn.execute("UPDATE orders SET submitted_at_utc='2026-09-10T14:00:00Z' "
                             "WHERE correlation_id='outside'")
                conn.commit()
                with pytest.raises(DataError, match="QUALIFICATION_EXECUTION_COSTS_NOT_ACCEPTED"):
                    await q.prepare_qualification(**args)
            assert not book.orders


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    candidate = build_candidate_registry(load_preregistration(q.PREREGISTRATION))[0]
    provider = "kis-nasdaq-partial-unadjusted"
    selection = ResearchSelection(candidate, provider, "a" * 40, "dataset", "research",
                                  execution_fingerprint(candidate, provider),
                                  "PAPER_CHALLENGER", 756, 0)
    forward = dict(freeze_authentication_verified=True, minimum_observation_count_met=True,
                   complete_sessions=60, required_sessions=60, invalid_sessions=0,
                   execution_parity_verified=False, session_dates=["2026-09-01", "2026-09-10"])
    record = tmp_path / "freeze.json"
    record.write_bytes(b"frozen-record")
    calls = []

    def select(archives, prereg, commit):
        assert prereg != q.PREREGISTRATION
        assert prereg.read_bytes() == q.PREREGISTRATION.read_bytes()
        assert commit == "a" * 40
        calls.append(("research", prereg))
        return selection

    def assess(database, raw, selected, prereg, **kwargs):
        assert kwargs == {"include_interval_bars": True}
        assert selected is selection and raw == b"frozen-record"
        assert prereg == calls[-1][1]
        calls.append(("forward", prereg))
        return forward

    monkeypatch.setattr(q, "subprocess", SimpleNamespace(check_output=lambda *a, **k: "a" * 40))
    monkeypatch.setattr(q, "select_research", select)
    monkeypatch.setattr(q, "assess_registered_forward", assess)
    args = dict(archives=tmp_path, forward_database=tmp_path / "forward.db",
                registration=record, account="1234567801", capital_limit=Decimal("600.00"),
                runtime_digest="sha256:" + "d" * 64)
    source = object.__new__(q.ExecutionCostSource)

    async def assess_cost(selected, dates, commission):
        # Unit isolation of authorization consumption; actual GET/recalculation
        # coverage is in the execution evidence integration tests.
        return q.ExecutionCostAssessment(
            "sha256:" + hashlib.sha256(args["account"].encode()).hexdigest(),
            selected.execution_identity, args["runtime_digest"], ("20260901", "20260910"),
            "sha256:" + "e" * 64, "{}", (), ("SOURCE_EXECUTION_TIMING_NOT_PROVIDED",),
        )

    source.assess = assess_cost
    args["execution_source"] = source
    return args, selection, forward, calls


def grant(qualification):
    selected = qualification.selection
    now = datetime.now(UTC)
    return dict(
        schema=1, scope="intraday-repeated-orders", authorization_id="operator-reviewed-1",
        account_digest=qualification.account_digest, execution_identity=selected.execution_identity,
        research_digest=selected.research_digest, dataset_fingerprint=selected.dataset_fingerprint,
        registration_digest=qualification.registration_digest, capital_limit_usd="600",
        runtime_digest=qualification.runtime_digest,
        valid_from=(now - timedelta(minutes=1)).isoformat(),
        valid_until=(now + timedelta(minutes=1)).isoformat(),
        broker_execution_parity_digest=qualification.execution_cost.digest,
        hardened_canary_digest="sha256:" + "b" * 64,
        deployment_audit_digest="sha256:" + "c" * 64,
    )


@pytest.mark.parametrize("volume,verified", [(200, True), (199, False)])
@pytest.mark.parametrize("source_verified", [False, True])
@pytest.mark.parametrize("response_minute,timing_verified", [("04", True), ("07", False)])
@pytest.mark.parametrize("fee,fee_verified", [("0.50", True), ("0.50001", False)])
async def test_qualification_actually_consumes_replayed_bars(
        prepared, monkeypatch, volume, verified, source_verified, response_minute, timing_verified,
        fee, fee_verified):
    args, _, forward, _ = prepared
    forward["market_source_authentication_verified"] = source_verified
    forward["_interval_bars_json"] = json.dumps([
        dict(symbol="SPY", timestamp_utc=f"2026-09-10T14:{minute}:00Z", volume=volume, open=100)
        for minute in ("00", "05")
    ])
    original = args["execution_source"].assess

    async def costs(*values):
        cost = await original(*values)
        entry = dict(
            order_id="order", symbol="SPY", quantity=2,
            side="BUY", average_fill_price="100.06", reported_fees=fee,
            signal_bar_end="2026-09-10T14:00:00Z", decision_kind="SIGNAL",
            before_submission="2026-09-10T14:01:00Z",
            response_received=f"2026-09-10T14:{response_minute}:00Z",
        )
        return replace(cost, intervals_json=json.dumps([entry]), orders_json=json.dumps([
            dict(entry, ordered_quantity=2, filled_quantity=2, reported_order_date="2026-09-10"),
        ]))

    args["execution_source"].assess = costs
    result = await q.prepare_qualification(**args)
    model = json.loads(result.interval_model_json)
    assert model["interval_volume_verified"] is verified
    assert model["next_bar_timing_verified"] is timing_verified
    assert model["next_bar_price_bound_verified"] is timing_verified
    assert model["next_bar_fee_bound_verified"] is (timing_verified and fee_verified)
    assert model["model_fill_quantity_verified"] is verified
    assert model["registered_forward_replay_verified"]
    assert model["market_source_authentication_verified"] is source_verified
    assert model["source_attestation_basis"] == "TRUSTED_SERVER_COLLECTOR"
    assert model["cost_digest"] == result.execution_cost.digest
    monkeypatch.setattr(q, "_read_authorization", lambda: grant(result))
    assert result() == "QUALIFICATION_EXECUTION_MODEL_EVIDENCE_MISSING"


async def test_well_formed_but_unrelated_broker_digest_is_rejected(prepared, monkeypatch):
    result = await q.prepare_qualification(**prepared[0])
    approval = grant(result)
    approval["broker_execution_parity_digest"] = "sha256:" + "f" * 64
    monkeypatch.setattr(q, "_read_authorization", lambda: approval)
    assert result() == "QUALIFICATION_AUTHORIZATION_MISMATCH"


async def test_recomputation_is_required_and_server_authorization_is_separate(
    prepared, monkeypatch,
):
    args, _, _, calls = prepared
    result = await q.prepare_qualification(**args)
    assert [name for name, _ in calls] == ["research", "forward"]
    assert not calls[0][1].exists()
    monkeypatch.setattr(q, "_read_authorization", lambda: {})
    assert result() == "QUALIFICATION_AUTHORIZATION_MISMATCH"
    approved = grant(result)
    monkeypatch.setattr(q, "_read_authorization", lambda: approved)
    assert result() == "QUALIFICATION_EXECUTION_MODEL_EVIDENCE_MISSING"
    approved["authorization_id"] = ""
    assert result() == "QUALIFICATION_AUTHORIZATION_MISMATCH"


@pytest.mark.parametrize("field,value", [
    ("complete_sessions", 59), ("complete_sessions", True), ("required_sessions", 1),
    ("invalid_sessions", 1), ("invalid_sessions", False),
    ("freeze_authentication_verified", False), ("minimum_observation_count_met", "true"),
])
async def test_bad_forward_evidence_never_produces_a_guard(prepared, field, value):
    args, _, forward, _ = prepared
    forward[field] = value
    with pytest.raises(DataError, match="QUALIFICATION_FORWARD_NOT_ACCEPTED"):
        await q.prepare_qualification(**args)


async def test_failed_research_never_reaches_forward_assessment(prepared, monkeypatch):
    args, selection, _, calls = prepared
    monkeypatch.setattr(q, "select_research", lambda *a: replace(selection, candidate=None))
    with pytest.raises(DataError, match="QUALIFICATION_RESEARCH_NOT_ACCEPTED"):
        await q.prepare_qualification(**args)
    assert calls == []


async def test_current_forward_without_execution_parity_uses_separate_cost_source(prepared):
    args, _, forward, _ = prepared
    forward["execution_parity_verified"] = False
    result = await q.prepare_qualification(**args)
    assert result.execution_cost.missing_model_conditions


@pytest.mark.parametrize("field", [
    "account_digest", "execution_identity", "research_digest", "dataset_fingerprint",
    "registration_digest", "runtime_digest", "capital_limit_usd", "scope",
    "broker_execution_parity_digest",
    "hardened_canary_digest", "deployment_audit_digest",
])
async def test_changed_authorization_identity_is_refused(prepared, monkeypatch, field):
    result = await q.prepare_qualification(**prepared[0])
    approved = grant(result)
    approved[field] = "changed"
    monkeypatch.setattr(q, "_read_authorization", lambda: approved)
    assert result() == "QUALIFICATION_AUTHORIZATION_MISMATCH"


async def test_expiry_and_strategy_change_are_checked_at_each_call(prepared, monkeypatch):
    result = await q.prepare_qualification(**prepared[0])
    approved = grant(result)
    monkeypatch.setattr(q, "_read_authorization", lambda: approved)
    assert result() == "QUALIFICATION_EXECUTION_MODEL_EVIDENCE_MISSING"
    approved["valid_until"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    assert result() == "QUALIFICATION_AUTHORIZATION_EXPIRED"
    monkeypatch.setattr(q, "execution_fingerprint", lambda *a: "changed")
    assert result() == "QUALIFICATION_STRATEGY_CHANGED"


async def test_unavailable_error_is_closed(prepared, monkeypatch):
    result = await q.prepare_qualification(**prepared[0])

    def fail():
        raise OSError("private path and contents")

    monkeypatch.setattr(q, "_read_authorization", fail)
    assert result() == "QUALIFICATION_AUTHORIZATION_UNAVAILABLE"


async def test_protected_file_missing_world_writable_or_symlink_is_refused(tmp_path, monkeypatch):
    path = tmp_path / "authorization.json"
    monkeypatch.setattr(q, "AUTHORIZATION_PATH", path)
    with pytest.raises(DataError, match="INTRADAY_AUTHORIZATION_UNAVAILABLE"):
        q._read_authorization()
    path.write_text("{}")
    path.chmod(0o666)
    with pytest.raises(DataError, match="INTRADAY_AUTHORIZATION_UNAVAILABLE"):
        q._read_authorization()
    alias = tmp_path / "alias"
    alias.symlink_to(path)
    monkeypatch.setattr(q, "AUTHORIZATION_PATH", alias)
    with pytest.raises(DataError, match="INTRADAY_AUTHORIZATION_UNAVAILABLE"):
        q._read_authorization()


async def test_root_file_parser_rejects_duplicate_keys_and_oversize(tmp_path, monkeypatch):
    path = tmp_path / "authorization.json"
    monkeypatch.setattr(q, "AUTHORIZATION_PATH", path)
    real = os.fstat

    def owned(fd):
        info = real(fd)
        return SimpleNamespace(**{name: 0 if name == "st_uid" else getattr(info, name)
                                  for name in dir(info) if name.startswith("st_")})

    proxy = SimpleNamespace(**{name: getattr(os, name) for name in dir(os)})
    proxy.fstat = owned
    monkeypatch.setattr(q, "os", proxy)
    path.write_text(json.dumps({"schema": 1}))
    path.chmod(0o600)
    assert q._read_authorization() == {"schema": 1}
    path.write_text('{"schema":1,"schema":2}')
    with pytest.raises(DataError):
        q._read_authorization()
    path.write_text("x" * 16385)
    with pytest.raises(DataError):
        q._read_authorization()
