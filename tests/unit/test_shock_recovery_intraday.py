from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from auto_invest.analytics import intraday_paper_challenger as paper
from auto_invest.analytics import shock_recovery_intraday as research

CONTRACT = Path("specs/191-shock-recovery-research/contracts/preregistration.json")
PRIOR = Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")


def candidates():
    contract, _ = research.load_contract(CONTRACT, PRIOR)
    return research.candidate_registry(contract)


def bars(timeframe=15):
    moment = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    prices = [(100, 100.2, 99.8, 100), (98.6, 98.7, 98.4, 98.5),
              (98.5, 99, 98.4, 98.9), (98.95, 99.2, 98.8, 99),
              (99, 100.2, 98.9, 100.1), (100.2, 100.3, 100, 100.1),
              (100.1, 100.3, 99.9, 100.2), (99.7, 100, 99.6, 99.8)]
    return [paper.ResampledBar(
        symbol="SPY", session_date=moment.date(),
        timestamp_utc=moment + timedelta(minutes=i * timeframe),
        end_utc=moment + timedelta(minutes=(i + 1) * timeframe),
        timeframe_minutes=timeframe, bar_index=i, open=o, high=h, low=lo, close=c,
        volume=1000000, base_bar_count=timeframe // 5,
        complete=True, entry_eligible=i < len(prices) - 1,
    ) for i, (o, h, lo, c) in enumerate(prices)]


def simulate(candidate, rows, model="base"):
    _, prior = research.load_contract(CONTRACT, PRIOR)
    session = rows[0].session_date
    resampled = {symbol: {session: tuple(replace(r, symbol=symbol) for r in rows)}
                 for symbol in paper.EXPECTED_UNIVERSE}
    return paper.simulate_candidate(candidate, resampled, [session], prior, cost_model_name=model)


def test_contract_four_distinct_candidates_and_prior_preserved(tmp_path):
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    rows = research.candidate_registry(contract)
    assert len(rows) == len({r.strategy_fingerprint for r in rows}) == 4
    assert {(r.timeframe_minutes, r.variant) for r in rows} == {
        (t, v) for t in (15, 30) for v in ("anchor", "session")}
    assert len(paper.build_candidate_registry(prior)) == 18
    altered = tmp_path / "contract.json"
    altered.write_bytes(CONTRACT.read_bytes() + b" ")
    with pytest.raises(ValueError, match="seal"):
        research.load_contract(altered, PRIOR)
    altered.write_bytes(PRIOR.read_bytes() + b" ")
    with pytest.raises(ValueError, match="prior contract"):
        research.load_contract(CONTRACT, altered)


@pytest.mark.parametrize("candidate", candidates())
def test_signals_are_causal_and_require_shock_recovery_and_headroom(candidate):
    rows = bars(candidate.timeframe_minutes)
    assert paper._entry_signal(candidate, rows, 2)
    assert not paper._entry_signal(candidate, rows, 0)
    for index, changes in [(1, {"close": 99.5}), (1, {"high": 98.9}),
                           (2, {"close": 99.5}), (2, {"entry_eligible": False}),
                           (0, {"complete": False}), (1, {"complete": False}),
                           (2, {"complete": False})]:
        modified = list(rows)
        modified[index] = replace(modified[index], **changes)
        assert not paper._entry_signal(candidate, modified, 2)
    modified = rows[:3] + [replace(r, open=1000, high=2000, close=1500) for r in rows[3:]]
    assert paper._entry_signal(candidate, modified, 2)
    assert paper._entry_signal(candidate, rows[:3], 2)


def test_inclusive_shock_headroom_and_stop_boundaries():
    candidate = candidates()[0]
    rows = bars()
    shock = 100 * (1 - .0124)
    rows[1] = replace(rows[1], close=shock, high=shock + .01)
    headroom = 100 / (1 + .0082)
    rows[2] = replace(rows[2], close=headroom, high=headroom)
    assert paper._entry_signal(candidate, rows, 2)
    rows[2] = replace(rows[2], close=headroom + 1e-8)
    assert not paper._entry_signal(candidate, rows, 2)
    rows[2] = replace(rows[2], close=headroom)
    rows[1] = replace(rows[1], close=shock + 1e-8)
    assert not paper._entry_signal(candidate, rows, 2)
    stop = rows[3].open * (1 - .0082)
    rows[4] = replace(rows[4], close=stop)
    assert paper._exit_signal(candidate, rows, 4, 3)
    rows[4] = replace(rows[4], close=stop + 1e-8)
    assert not paper._exit_signal(candidate, rows, 4, 3)
    rows[4] = replace(rows[4], close=100)
    assert paper._exit_signal(candidate, rows, 4, 3)
    assert not paper._exit_signal(candidates()[1], rows, 4, 3)
    rows[4] = replace(rows[4], complete=False)
    assert not paper._exit_signal(candidate, rows, 4, 3)


@pytest.mark.parametrize("candidate", candidates())
def test_next_open_fills_and_distinct_exit_policies(candidate):
    rows = bars(candidate.timeframe_minutes)
    run = simulate(candidate, rows)
    assert run.unclosed_quantity == 0
    ledger = [r for r in run.ledger_rows if r["symbol"] == "SPY"]
    assert [r["side"] for r in ledger] == ["BUY", "SELL"]
    assert ledger[0]["reference_price"] == rows[3].open
    exit_index = 5 if candidate.variant == "anchor" else 7
    assert ledger[1]["reference_price"] == rows[exit_index].open
    assert ledger[0]["signal_at_utc"] == paper._iso(rows[2].end_utc)
    assert ledger[0]["eligible_at_utc"] == paper._iso(rows[3].timestamp_utc)
    assert (datetime.fromisoformat(ledger[0]["filled_at_utc"])
            > datetime.fromisoformat(ledger[0]["eligible_at_utc"]))


def test_gap_entry_does_not_cancel_using_future_open_and_stop_is_not_guaranteed():
    candidate = candidates()[0]
    rows = bars()
    rows[3] = replace(rows[3], open=102, high=102, close=98, low=97.9)
    rows[4] = replace(rows[4], open=96, high=98, close=97, low=95)
    run = simulate(candidate, rows)
    ledger = [r for r in run.ledger_rows if r["symbol"] == "SPY"]
    assert [r["reference_price"] for r in ledger] == [102, 96]
    assert ledger[1]["net_pnl_usd"] < -102 * .0082 * ledger[1]["filled_qty"]


def test_zero_volume_consumes_buy_attempt_and_does_not_retry():
    rows = bars()
    rows[3] = replace(rows[3], volume=0, open=98.6, high=98.7, low=98.4, close=98.5)
    rows[4] = replace(rows[4], open=98.5, high=99, low=98.4, close=98.9)
    assert paper._entry_signal(candidates()[0], rows, 4)
    run = simulate(candidates()[0], rows)
    ledger = [r for r in run.ledger_rows if r["symbol"] == "SPY"]
    assert len(ledger) == 1 and ledger[0]["fill_status"] == "UNFILLED"
    assert run.unclosed_quantity == 0


def test_partial_exit_retries_remainder_and_failed_last_exit_is_reported():
    rows = bars()
    rows[5] = replace(rows[5], volume=200)
    run = simulate(candidates()[0], rows)
    ledger = [r for r in run.ledger_rows if r["symbol"] == "SPY"]
    assert ledger[1]["fill_status"] == "PARTIAL"
    assert sum(r["filled_qty"] for r in ledger if r["side"] == "SELL") == ledger[0]["filled_qty"]
    assert run.unclosed_quantity == 0
    rows = bars()
    rows[-1] = replace(rows[-1], volume=0)
    run = simulate(candidates()[1], rows)
    assert run.unclosed_quantity > 0
    assert any(r["reason"] == "session_close_liquidity_failure" for r in run.ledger_rows)


def test_penultimate_signal_never_buys_on_last_bar():
    rows = bars()[:4]
    rows[-1] = replace(rows[-1], entry_eligible=False)
    assert simulate(candidates()[0], rows).ledger_rows == ()


def reseal(payload):
    value = deepcopy(payload)
    value.pop("content_sha256", None)
    value["content_sha256"] = paper._sha256(paper._canonical_bytes(value))
    return value


def payload():
    return reseal({"stage": "development", "contract_sha256": research.CONTRACT_SHA256,
                   "code_commit": "a" * 40, "safety": dict(paper.EXPECTED_SAFETY),
                   "holdout_read": False, "ledger_sha256": paper._sha256(b""),
                   "ledger_row_count": 0, "verdict": "DEVELOPMENT_REJECTED",
                   "selected_candidate_id": None})


def test_resealed_forgery_fails_source_replay(monkeypatch):
    original = payload()
    monkeypatch.setattr(research, "run_development", lambda *a, **kw: (original, b""))
    assert research.verify_development(original, b"", None, {}, {}) == original
    forged = reseal({**original, "selected_candidate_id": "fake",
                     "verdict": "CONFIRMATION_REQUIRED"})
    with pytest.raises(ValueError, match="source replay"):
        research.verify_development(forged, b"", None, {}, {})
    with pytest.raises(ValueError, match="ledger fingerprint"):
        research.verify_development(original, b"altered", None, {}, {})
    with pytest.raises(ValueError, match="boundary"):
        research.validate_seal(reseal({**original, "holdout_read": True}), b"")


def test_other_manifest_rejected_before_price_read(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"dataset_id":"holdout"}')
    monkeypatch.setattr(paper, "load_intraday_dataset", lambda *a: pytest.fail("price read"))
    with pytest.raises(ValueError, match="price files not read"):
        research.load_development(tmp_path, manifest, {})


def test_full_development_shape_and_source_replay_with_simulated_inputs(monkeypatch):
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    session = bars()[0].session_date
    dataset = SimpleNamespace(sessions=(session,), dataset_fingerprint="sha256:fixture")
    monkeypatch.setattr(research, "validate_development", lambda *a: None)
    monkeypatch.setattr(paper, "resample_dataset", lambda _, tf: {
        symbol: {session: tuple(replace(r, symbol=symbol) for r in bars(tf))}
        for symbol in paper.EXPECTED_UNIVERSE})
    result, ledger = research.run_development(dataset, contract, prior, code_commit="a" * 40)
    assert len(result["evaluations"]) == 4
    assert result["selected_candidate_id"] is None
    assert result["verdict"] == "DEVELOPMENT_REJECTED"
    assert result["holdout_read"] is False
    assert result["safety"] == paper.EXPECTED_SAFETY
    assert result["ledger_row_count"] == 80
    assert research.verify_development(result, ledger, dataset, contract, prior) == result
    forged = deepcopy(result)
    forged["evaluations"][0]["base"]["net_return_pct"] += 1
    with pytest.raises(ValueError, match="source replay"):
        research.verify_development(reseal(forged), ledger, dataset, contract, prior)
