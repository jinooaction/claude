from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.analytics.credit_spread_factory import (
    CreditCurveSnapshot,
    build_credit_curve_snapshots,
    generate_credit_candidates,
    run_credit_spread_factory,
    validate_live_credit_evidence,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow
from auto_invest.config.rules import CreditSpreadPolicyConfig, PortfolioRebalanceConfig
from auto_invest.market_data.public_data import SeriesPoint
from auto_invest.portfolio.autoarm import strategy_fingerprint, strategy_fingerprint_digest
from auto_invest.strategy.rebalance import credit_spread_target_weights


def _rows(count: int = 444) -> list[MonthlyRow]:
    output: list[MonthlyRow] = []
    year, month = 1990, 1
    for index in range(count):
        output.append(
            MonthlyRow(
                date(year, month, 1).isoformat(),
                price=100 * (1.006**index),
                dividend=2.0,
                long_rate=4.0 + (index % 24 - 12) / 20,
            )
        )
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return output


def _snapshots(rows: list[MonthlyRow]) -> list[CreditCurveSnapshot]:
    keys = (
        "corporate_10",
        "corporate_20",
        "treasury_10",
        "treasury_20",
        "spread_10",
        "spread_20",
    )
    histories: dict[str, list[Decimal]] = {key: [] for key in keys}
    output: list[CreditCurveSnapshot] = []
    for index, row in enumerate(rows):
        tsy10 = Decimal("3.5") + Decimal(index % 18) / Decimal("20")
        tsy20 = tsy10 + Decimal("0.3")
        spread10 = Decimal("0.8") + Decimal(index % 12) / Decimal("20")
        spread20 = spread10 + Decimal("0.2")
        values = {
            "corporate_10": tsy10 + spread10,
            "corporate_20": tsy20 + spread20,
            "treasury_10": tsy10,
            "treasury_20": tsy20,
            "spread_10": spread10,
            "spread_20": spread20,
        }
        for key, value in values.items():
            histories[key].append(value)
        output.append(
            CreditCurveSnapshot(
                as_of_date=row.date,
                corporate_yields={"10Y": values["corporate_10"], "20Y": values["corporate_20"]},
                treasury_yields={"10Y": tsy10, "20Y": tsy20},
                spreads={"10Y": spread10, "20Y": spread20},
                observation_dates={
                    key: row.date for key in ("HQMCB10YR", "HQMCB20YR", "DGS10", "DGS30")
                },
                credit_history={key: tuple(history) for key, history in histories.items()},
                complete=True,
                fresh=True,
            )
        )
    return output


def _records(prefix: str, count: int) -> list[dict]:
    return [
        {
            "candidate_id": f"{prefix}{index:03d}",
            "strategy_fingerprint": f"sha256:{prefix}{index:03d}",
            "status": "complete",
            "segment_sharpes": [0.1] * 10,
        }
        for index in range(count)
    ]


def _ledger(count: int = 256) -> list[dict]:
    return _records("factory-", count)


def _macro_payload(*, exploratory_count: int = 192, macro_count: int = 64) -> dict:
    exploratory = _records("exploratory-", exploratory_count)
    for record in exploratory:
        record["status"] = "EXPLORATORY_REJECTED"
    return {
        "exploratory_replay": exploratory,
        "trial_records": _records("macro-", macro_count),
    }


def _treasury_payload(count: int = 64) -> dict:
    return {"trial_records": _records("treasury-", count)}


def _calibration() -> dict:
    return {
        "gate_version": "2.0",
        "verdict": "CALIBRATED",
        "code_commit": "abc123",
        "scenario": {"repetitions": 500},
        "revised": {"false_acceptance_rate": 0.036, "detection_rate": 0.834},
        "thresholds": {
            "development_dsr_diagnostic_min": 0.95,
            "development_pbo_diagnostic_max": 0.10,
            "holdout_psr_min": 0.95,
        },
    }


def _run(
    snapshots: list[CreditCurveSnapshot],
    prior: list[dict] | None = None,
    *,
    macro_payload: dict | None = None,
    treasury_payload: dict | None = None,
) -> dict:
    rows = _rows()
    return run_credit_spread_factory(
        rows,
        [400 * (1.004**index) for index in range(len(rows))],
        snapshots,
        credit_data_quality={"complete": True},
        prior_trial_records=_ledger() if prior is None else prior,
        prior_factory_payload=_treasury_payload() if treasury_payload is None else treasury_payload,
        macro_factory_payload=_macro_payload() if macro_payload is None else macro_payload,
        calibration_evidence=_calibration(),
        code_commit="abc123",
        timestamp_utc="2026-08-23T00:00:00Z",
    )


def test_candidate_grammar_is_64_unique_and_not_live_authorized() -> None:
    first, second = generate_credit_candidates(), generate_credit_candidates()
    assert len(first) == 64
    assert [item.candidate_id for item in first] == [item.candidate_id for item in second]
    assert len({item.strategy_fingerprint for item in first}) == 64
    assert {item.policy.family for item in first} == {
        "carry_buffer",
        "spread_compression",
        "curve_value",
        "stress_reentry",
    }
    assert all(item.as_dict()["live_expressible"] is False for item in first)


def test_shared_policy_is_long_only_and_stale_fails_closed() -> None:
    snapshot = _snapshots(_rows(14))[-1].as_dict(include_history=True)
    policy = CreditSpreadPolicyConfig(
        family="spread_compression",
        lookback_months=3,
        spread_threshold_bps=50,
        confirmation_months=1,
        max_credit_weight=Decimal("0.5"),
    )
    weights = credit_spread_target_weights(policy=policy, snapshot=snapshot)
    assert set(weights) == {"LQD", "IEF"}
    assert sum(weights.values()) == Decimal("1.000000")
    snapshot["fresh"] = False
    with pytest.raises(ValueError, match="stale"):
        credit_spread_target_weights(policy=policy, snapshot=snapshot)
    with pytest.raises(ValueError, match="max_credit_weight"):
        CreditSpreadPolicyConfig(
            family="carry_buffer",
            lookback_months=3,
            spread_threshold_bps=50,
            confirmation_months=1,
            max_credit_weight=Decimal("0.75"),
        )


def test_policy_changes_strategy_fingerprint() -> None:
    policy = CreditSpreadPolicyConfig(
        family="carry_buffer",
        lookback_months=3,
        spread_threshold_bps=50,
        confirmation_months=1,
        max_credit_weight=Decimal("0.5"),
    )
    first = PortfolioRebalanceConfig(
        id="credit-a",
        universe=("LQD", "IEF"),
        weights={"momentum": Decimal("1")},
        top_n=2,
        credit_spread_policy=policy,
    )
    second = first.model_copy(
        update={
            "credit_spread_policy": policy.model_copy(update={"max_credit_weight": Decimal("1.0")})
        }
    )
    assert strategy_fingerprint_digest(first) != strategy_fingerprint_digest(second)


def test_existing_strategy_fingerprint_shape_is_unchanged() -> None:
    config = PortfolioRebalanceConfig(
        id="existing",
        universe=("SPY", "IEF", "GLD"),
        weights={"momentum": Decimal("1")},
        top_n=2,
    )
    assert strategy_fingerprint_digest(config) == (
        "sha256:0ec53e0d014ae5a0732eca4322d05e0f7b1f2afd7fd9d7bc35772bf27c22e922"
    )
    assert len(strategy_fingerprint(config)) == 11


def test_point_in_time_snapshot_lags_monthly_hqm() -> None:
    series = {
        "HQMCB10YR": [
            SeriesPoint("2020-01-01", Decimal("5")),
            SeriesPoint("2020-02-01", Decimal("9")),
        ],
        "HQMCB20YR": [
            SeriesPoint("2020-01-01", Decimal("6")),
            SeriesPoint("2020-02-01", Decimal("9")),
        ],
        "DGS10": [SeriesPoint("2020-01-31", Decimal("2"))],
        "DGS30": [SeriesPoint("2020-01-31", Decimal("3"))],
    }
    snapshot = build_credit_curve_snapshots(["2020-02-01"], series=series)[0]
    assert snapshot.complete is True
    assert snapshot.corporate_yields == {"10Y": Decimal("5"), "20Y": Decimal("6")}


def test_point_in_time_snapshot_rejects_stale_matched_treasury() -> None:
    series = {
        "HQMCB10YR": [SeriesPoint("2020-01-01", Decimal("5"))],
        "HQMCB20YR": [SeriesPoint("2020-01-01", Decimal("6"))],
        "DGS10": [SeriesPoint("2020-01-10", Decimal("2"))],
        "DGS30": [SeriesPoint("2020-01-10", Decimal("3"))],
    }
    snapshot = build_credit_curve_snapshots(["2020-02-01"], series=series)[0]
    assert snapshot.complete is True
    assert snapshot.fresh is False

    missing = build_credit_curve_snapshots(
        ["2020-02-01"], series={key: value for key, value in series.items() if key != "DGS30"}
    )[0]
    assert missing.complete is False
    assert missing.fresh is False


def test_factory_separates_640_audit_from_64_family_trials() -> None:
    payload = _run(_snapshots(_rows()))
    assert payload["prior_trial_count"] == 576
    assert payload["prior_audit_lineage"] == {
        "production_price_candidates": 256,
        "exploratory_replays": 192,
        "macro_candidates": 64,
        "treasury_candidates": 64,
    }
    assert payload["global_audit_trial_count"] == 640
    assert payload["multiplicity_trial_count"] == 64
    assert Decimal("1") <= Decimal(payload["family_effective_trial_count"]) <= Decimal("64")
    assert payload["unique_trial_fingerprint_count"] == 640
    assert len(payload["audit_records"]) == 640
    assert payload["decision"]["selected_deploy_config"] is None
    assert payload["decision"]["live_whitelist_authorized"] is False


def test_repeated_prior_batches_do_not_inflate_global_audit() -> None:
    duplicated_ledger = _ledger() + _ledger()
    payload = _run(_snapshots(_rows()), duplicated_ledger)
    assert payload["prior_trial_count"] == 576
    assert payload["global_audit_trial_count"] == 640
    assert payload["unique_trial_fingerprint_count"] == 640


def test_holdout_does_not_reselect_and_missing_prior_fails() -> None:
    original = _snapshots(_rows())
    first = _run(original)
    altered = [
        item
        if item.as_of_date < "2007-01-01"
        else replace(
            item,
            corporate_yields={
                key: value + Decimal("3") for key, value in item.corporate_yields.items()
            },
        )
        for item in original
    ]
    second = _run(altered)
    assert (
        first["development_selection"]["selected_candidate_id"]
        == second["development_selection"]["selected_candidate_id"]
    )
    missing = _run(original, _ledger(255))
    gates = {gate["gate_id"]: gate for gate in missing["decision"]["gates"]}
    assert gates["prior_audit_complete"]["passed"] is False
    assert missing["decision"]["research_canary_eligible"] is False


def _eligible_live_payload() -> dict:
    return {
        "gate_version": "2.0",
        "timestamp_utc": "2026-08-23T00:00:00Z",
        "code_commit": "abc",
        "credit_data_fingerprint": "sha256:data",
        "decision": {
            "verdict": "FACTORY_EDGE",
            "research_canary_eligible": True,
            "live_whitelist_authorized": True,
            "selected_candidate_id": "candidate",
            "selected_strategy_fingerprint": "sha256:x",
            "gates": [{"passed": True, "blocking": True}],
        },
        "research_live_parity": {"target_weights_digest": "sha256:weights"},
        "live_credit_evidence": {
            "candidate_id": "candidate",
            "strategy_fingerprint": "sha256:x",
            "data_fingerprint": "sha256:data",
            "code_commit": "abc",
            "target_weights_digest": "sha256:weights",
            "fresh": True,
            "complete": True,
            "live_whitelist_authorized": True,
            "latest_snapshot": _snapshots(_rows(14))[-1].as_dict(),
        },
    }


def test_live_evidence_accepts_exact_all_pass_and_rejects_each_failed_gate() -> None:
    payload = _eligible_live_payload()
    snapshot = validate_live_credit_evidence(
        payload,
        candidate_id="candidate",
        strategy_fingerprint="sha256:x",
        now=datetime(2026, 8, 23, tzinfo=UTC),
    )
    assert snapshot == payload["live_credit_evidence"]["latest_snapshot"]

    failed = deepcopy(payload)
    failed["decision"]["gates"][0]["passed"] = False
    with pytest.raises(ValueError, match="gates"):
        validate_live_credit_evidence(
            failed,
            candidate_id="candidate",
            strategy_fingerprint="sha256:x",
            now=datetime(2026, 8, 23, tzinfo=UTC),
        )


def test_live_evidence_rejects_unapproved_whitelist() -> None:
    payload = _eligible_live_payload()
    payload["decision"]["live_whitelist_authorized"] = False
    payload["live_credit_evidence"]["live_whitelist_authorized"] = False
    with pytest.raises(ValueError, match="whitelist"):
        validate_live_credit_evidence(
            payload,
            candidate_id="candidate",
            strategy_fingerprint="sha256:x",
            now=datetime(2026, 8, 23, tzinfo=UTC),
        )

    stale = _eligible_live_payload()
    stale["timestamp_utc"] = "2026-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="stale"):
        validate_live_credit_evidence(
            stale,
            candidate_id="candidate",
            strategy_fingerprint="sha256:x",
            now=datetime(2026, 8, 23, tzinfo=UTC),
        )


def test_credit_evidence_validation_precedes_any_broker_path() -> None:
    text = (Path(__file__).resolve().parents[2] / "src" / "auto_invest" / "cli.py").read_text(
        encoding="utf-8"
    )
    validation = text.index("credit_snapshot = validate_live_credit_evidence(")
    broker_path = text.index("async def _go_dry()")
    assert validation < broker_path
    assert "credit spread policy requires --credit-evidence before broker call" in text
