from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from auto_invest.analytics import cost_aware_intraday as research
from auto_invest.analytics import intraday_paper_challenger as paper
from auto_invest.analytics.cost_aware_intraday import (
    candidate_registry,
    load_contract,
    select_development,
    validate_development,
)
from auto_invest.analytics.intraday_paper_challenger import (
    IntradayDataset,
    ResampledBar,
    _entry_signal,
)

CONTRACT = Path("specs/190-cost-aware-intraday/contracts/preregistration.json")
PRIOR = Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")


def _row(name: str, *, sharpe: float = 1, trades: int = 200) -> dict:
    metrics = {"net_return_pct": 1, "annualized_sharpe": sharpe,
               "max_drawdown_pct": 2, "turnover_usd": 100,
               "closed_trade_count": trades, "unclosed_quantity": 0}
    return {"candidate_id": name, "base": dict(metrics), "stress": dict(metrics)}


def test_frozen_contract_registry_and_tampering(tmp_path: Path) -> None:
    contract, prior = load_contract(CONTRACT, PRIOR)
    registry = candidate_registry(contract)
    assert len(registry) == len({row.strategy_fingerprint for row in registry}) == 6
    assert {(row.timeframe_minutes, row.parameters["breakout_buffer_bps"])
            for row in registry} == {(t, b) for t in (30, 60) for b in (62, 124, 186)}
    assert all(row.parameters["range_bars"] == 1 for row in registry)
    assert prior["cost_models"]["base"]["commission_bps_per_side"] == 25
    altered = tmp_path / "contract.json"
    altered.write_bytes(CONTRACT.read_bytes().replace(b"[62, 124, 186]", b"[1, 2, 3]"))
    with pytest.raises(ValueError, match="seal"):
        load_contract(altered, PRIOR)
    altered.write_bytes(PRIOR.read_bytes() + b" ")
    with pytest.raises(ValueError, match="prior contract"):
        load_contract(CONTRACT, altered)


def test_all_six_signals_use_only_completed_opening_range_and_known_close() -> None:
    contract, _ = load_contract(CONTRACT, PRIOR)
    moment = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    for candidate in candidate_registry(contract):
        width = timedelta(minutes=candidate.timeframe_minutes)
        opening = ResampledBar(
            symbol="SPY", session_date=moment.date(), timestamp_utc=moment,
            end_utc=moment + width, timeframe_minutes=candidate.timeframe_minutes,
            bar_index=0, open=99, high=100, low=98, close=99,
            volume=10000, base_bar_count=candidate.timeframe_minutes // 5,
            complete=True, entry_eligible=True,
        )
        threshold = 100 * (1 + candidate.parameters["breakout_buffer_bps"] / 10000)
        signal = replace(opening, timestamp_utc=moment + width, end_utc=moment + 2 * width,
                         bar_index=1, high=threshold + 1, close=threshold + 0.01)
        assert not _entry_signal(candidate, [opening], 0)
        assert _entry_signal(candidate, [opening, signal], 1)
        assert not _entry_signal(candidate, [opening, replace(signal, close=threshold)], 1)
        assert not _entry_signal(candidate, [opening, replace(signal, entry_eligible=False)], 1)
        future = replace(signal, high=1000, close=900)
        assert _entry_signal(candidate, [opening, signal, future], 1)


@pytest.mark.parametrize("model,field,value", [
    ("base", "net_return_pct", 0), ("stress", "net_return_pct", -1),
    ("base", "closed_trade_count", 199), ("base", "unclosed_quantity", 1),
    ("stress", "unclosed_quantity", 1),
])
def test_selection_rejects_failed_development(model: str, field: str, value: int) -> None:
    row = _row("candidate")
    row[model][field] = value
    selected, reasons = select_development([row])
    assert selected is None
    assert reasons["candidate"]


def test_selection_rank_is_development_sharpe_then_drawdown_turnover_id() -> None:
    a, b = _row("a"), _row("b", sharpe=2)
    assert select_development([a, b])[0] == "b"
    b["base"]["annualized_sharpe"] = 1
    b["base"]["max_drawdown_pct"] = 1
    assert select_development([a, b])[0] == "b"
    a["base"]["max_drawdown_pct"] = 1
    b["base"]["turnover_usd"] = 99
    assert select_development([a, b])[0] == "b"
    a["base"]["turnover_usd"] = 99
    assert select_development([b, a])[0] == "a"
    for row in (a, b):
        row["confirmation"] = {"net_return_pct": 999 if row is b else -999}
    assert select_development([b, a])[0] == "a"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_metrics_are_not_selection_evidence(bad: float) -> None:
    row = _row("a")
    row["stress"]["net_return_pct"] = bad
    with pytest.raises(ValueError, match="non-finite"):
        select_development([row])


def test_development_rejects_synthetic_or_mismatched_fingerprint() -> None:
    contract, _ = load_contract(CONTRACT, PRIOR)
    fixture = IntradayDataset("fixture", "fixture", True, "sha256:other", {},
                              (date(2020, 3, 19),), ())
    with pytest.raises(ValueError, match="synthetic"):
        validate_development(fixture, contract)
    with pytest.raises(ValueError, match="interval"):
        validate_development(replace(fixture, synthetic=False), contract)


def _reseal(payload: dict) -> dict:
    value = deepcopy(payload)
    value.pop("content_sha256", None)
    value["content_sha256"] = paper._sha256(paper._canonical_bytes(value))
    return value


def _sealed_payload() -> dict:
    return _reseal({
        "stage": "development", "contract_sha256": research.CONTRACT_SHA256,
        "code_commit": "a" * 40, "safety": dict(paper.EXPECTED_SAFETY),
        "ledger_sha256": paper._sha256(b""), "ledger_row_count": 0,
        "verdict": "DEVELOPMENT_REJECTED", "selected_candidate_id": None,
    })


def test_replay_rejects_forged_selection_even_after_hash_is_resealed(monkeypatch) -> None:
    expected = _sealed_payload()
    monkeypatch.setattr(research, "run_development", lambda *a, **kw: (expected, b""))
    assert research.verify_development(expected, b"", None, {}, {}) == expected
    forged = {**expected, "verdict": "SELECTION_SEALED", "selected_candidate_id": "fake"}
    with pytest.raises(ValueError, match="content fingerprint"):
        research.verify_development(forged, b"", None, {}, {})
    with pytest.raises(ValueError, match="independent source replay"):
        research.verify_development(_reseal(forged), b"", None, {}, {})


def test_ledger_and_safety_changes_are_rejected_before_replay(monkeypatch) -> None:
    def must_not_replay(*args, **kwargs):
        pytest.fail("invalid envelope must not trigger costly replay")
    monkeypatch.setattr(research, "run_development", must_not_replay)
    with pytest.raises(ValueError, match="ledger fingerprint"):
        research.verify_development(_sealed_payload(), b"tampered", None, {}, {})
    altered = _sealed_payload()
    altered["safety"]["live_eligible"] = True
    with pytest.raises(ValueError, match="safety boundary"):
        research.verify_development(_reseal(altered), b"", None, {}, {})


def test_rejected_development_stops_confirmation_before_data_inspection(monkeypatch) -> None:
    def must_not_read(*args, **kwargs):
        pytest.fail("rejected selection must not inspect holdout")
    monkeypatch.setattr(research, "validate_holdout", must_not_read)
    with pytest.raises(ValueError, match="holdout must remain unopened"):
        research.run_confirmation(None, None, _sealed_payload(), {}, {}, code_commit="a" * 40)


def _holdout_fixture():
    contract, prior = load_contract(CONTRACT, PRIOR)
    sessions = tuple(stamp.date() for stamp in paper._CALENDAR.sessions_in_range(
        "2020-03-19", "2022-03-04"))
    holdout = IntradayDataset("holdout", "source", False, "sha256:test", {}, sessions, ())
    dev = replace(holdout, dataset_id="development", sessions=(date(2020, 3, 6),))
    return contract, prior, dev, holdout


def test_holdout_time_and_source_constraints() -> None:
    contract, _, development, holdout = _holdout_fixture()
    research.validate_holdout(holdout, development, contract)
    for bad in (replace(holdout, provider="different"), replace(holdout, synthetic=True),
                replace(holdout, sessions=holdout.sessions[:-1]),
                replace(holdout, sessions=(holdout.sessions[0],) * len(holdout.sessions))):
        with pytest.raises(ValueError):
            research.validate_holdout(bad, development, contract)
    with pytest.raises(ValueError, match="separation"):
        research.validate_holdout(holdout, holdout, contract)


def test_confirmation_includes_prior_trials_and_never_reselects(monkeypatch) -> None:
    contract, prior, development, holdout = _holdout_fixture()
    monkeypatch.setattr(research, "validate_development", lambda *a: None)
    monkeypatch.setattr(paper, "resample_dataset", lambda *a: {})
    calls = []
    def zero_simulation(candidate, bars, sessions, prereg, *, cost_model_name):
        calls.append((candidate.candidate_id, len(sessions), cost_model_name))
        return paper.SimulationResult(candidate.candidate_id, cost_model_name,
                                      dict.fromkeys(sessions, 0.0), (), (), 0, 0, 0, 0)
    monkeypatch.setattr(paper, "simulate_candidate", zero_simulation)
    selected = research.candidate_registry(contract)[-1].candidate_id
    frozen = {"verdict": "SELECTION_SEALED", "selected_candidate_id": selected,
              "content_sha256": "sha256:selection"}
    payload, ledger = research.run_confirmation(
        holdout, development, frozen, contract, prior, code_commit="a" * 40,
    )
    assert payload["trial_count"] == 24
    assert len({row[0] for row in calls}) == 24
    assert len(calls) == 72  # development base, holdout base and stress per trial
    assert payload["selected_candidate_id"] == selected
    assert payload["block_sessions"] == 247
    assert payload["confirmation_sessions"] == 248
    assert payload["verdict"] == "RESEARCH_REJECTED"
    assert payload["safety"]["live_eligible"] is False
    assert ledger == b""
    assert research.verify_confirmation(
        payload, ledger, holdout, development, frozen, contract, prior,
    ) == payload
    forged = _reseal({**payload, "verdict": "RESEARCH_PASSED", "reasons": []})
    with pytest.raises(ValueError, match="independent source replay"):
        research.verify_confirmation(
            forged, ledger, holdout, development, frozen, contract, prior,
        )
    # A missing historical trial is not silently treated as a smaller trial family.
    original = paper.build_candidate_registry(prior)
    monkeypatch.setattr(paper, "build_candidate_registry", lambda *a: original[:-1])
    with pytest.raises(ValueError, match="all 18 prior"):
        research.run_confirmation(
            holdout, development, frozen, contract, prior, code_commit="a" * 40,
        )
