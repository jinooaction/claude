import json
from datetime import timedelta
from pathlib import Path

import pytest

from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.execution import intraday_selection
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.market_data.intraday import CALENDAR, SYMBOLS, iso, write_batch

PREREG = Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")
COMMIT = "a" * 40
PROVIDER = "kis-nasdaq-partial-unadjusted"


def test_raw_archive_is_recomputed_instead_of_trusting_a_forged_report(tmp_path):
    opening = CALENDAR.session_open("2026-09-08").to_pydatetime()
    closing = CALENDAR.session_close("2026-09-08").to_pydatetime()
    root = tmp_path / "sessions"
    folder = root / "2026-09-08"
    rows = [dict(symbol=s, timestamp_utc=iso(opening + timedelta(minutes=5 * i)),
                 open=100, high=101, low=99, close=100, volume=10000)
            for i in range(78) for s in SYMBOLS]
    write_batch(folder, dict(provider=PROVIDER, synthetic=False, pages=[], bars=rows,
                            retrieved_at_utc=iso(closing + timedelta(minutes=1))))
    forged = b'{"decision":{"passed":true,"verdict":"PAPER_CHALLENGER"}}'
    (folder / "research.json").write_bytes(forged)
    before = {p: p.read_bytes() for p in folder.iterdir()}
    result = intraday_selection.select_research(root, PREREG, COMMIT)
    assert result.candidate is None and result.execution_identity is None
    assert result.verdict == "INSUFFICIENT_EVIDENCE"
    assert result.session_count == 1 and result.missing_sessions == 755
    assert result.public()["live_eligible"] is False
    assert all(p.read_bytes() == value for p, value in before.items())


def computed_result(output, *, selected_id=None, provider=PROVIDER, synthetic=False):
    """Unit fixture for the selection boundary; not a history acceptance proof."""
    output.mkdir()
    if selected_id is None:
        selected_id = build_candidate_registry(load_preregistration(PREREG))[0].candidate_id
    (output / "research.json").write_text(json.dumps({
        "selection": {"selected_candidate_id": selected_id},
    }))
    return dict(decision=dict(passed=True, verdict="PAPER_CHALLENGER"),
                synthetic=synthetic, provider=provider, dataset_fingerprint="sha256:" + "b" * 64,
                session_count=756, missing_sessions=0)


def test_selected_candidate_and_execution_identity_are_bound_to_frozen_registration(
    tmp_path, monkeypatch,
):
    source = tmp_path / "registration.json"
    source.write_bytes(PREREG.read_bytes())
    observed = []

    def evaluate(archives, output, frozen, commit):
        assert commit == COMMIT and frozen != source
        observed.append(output)
        result = computed_result(output)
        source.write_text("concurrent edit")
        return result

    monkeypatch.setattr(intraday_selection, "review_archives", evaluate)
    result = intraday_selection.select_research(tmp_path, source, COMMIT)
    assert result.candidate.candidate_id.startswith("intraday-")
    assert result.execution_identity == execution_fingerprint(result.candidate, PROVIDER)
    assert result.public()["live_eligible"] is False
    assert not observed[0].exists()


@pytest.mark.parametrize("bad", ["unknown", "synthetic"])
def test_inconsistent_computed_selection_is_rejected(tmp_path, monkeypatch, bad):
    def evaluate(archives, output, frozen, commit):
        return computed_result(output, selected_id="unknown" if bad == "unknown" else None,
                               synthetic=bad == "synthetic")

    monkeypatch.setattr(intraday_selection, "review_archives", evaluate)
    with pytest.raises(ValueError, match="RESEARCH_.*_INVALID"):
        intraday_selection.select_research(tmp_path, PREREG, COMMIT)


def test_other_provider_is_not_silently_relabelled_as_kis(tmp_path, monkeypatch):
    monkeypatch.setattr(intraday_selection, "review_archives", lambda a, o, p, c:
                        computed_result(o, provider="alpaca-sip-split"))
    result = intraday_selection.select_research(tmp_path, PREREG, COMMIT)
    assert result.candidate is not None and result.execution_identity is None
    assert result.provider == "alpaca-sip-split"


def test_candidate_parameter_mutation_changes_execution_identity():
    candidate = build_candidate_registry(load_preregistration(PREREG))[0]
    before = execution_fingerprint(candidate, PROVIDER)
    original_claimed_fingerprint = candidate.strategy_fingerprint
    candidate.parameters["threshold_bps"] = 999
    assert candidate.strategy_fingerprint == original_claimed_fingerprint
    assert execution_fingerprint(candidate, PROVIDER) != before


@pytest.mark.parametrize("filename", [
    "intraday_observation.py", "intraday_selection.py", "intraday_cash_ledger.py",
    "intraday_account.py", "intraday_cash_baseline.py", "account_source_profile.py",
    "domestic_account.py",
    "intraday_holdings_coverage.py",
    "intraday_account_frame.py",
    "intraday_asset_scope.py",
    "account_asset_evidence.py", "intraday_balance_evidence.py",
    "intraday_reported_cash.py",
    "fill_amounts.py", "0005_fill_notionals.sql",
])
def test_new_input_sources_are_bound_to_execution_identity(monkeypatch, filename):
    candidate = build_candidate_registry(load_preregistration(PREREG))[0]
    before = execution_fingerprint(candidate, PROVIDER)
    original = Path.read_bytes

    def changed(path):
        return original(path) + (b"\n# changed" if path.name == filename else b"")

    monkeypatch.setattr(Path, "read_bytes", changed)
    assert execution_fingerprint(candidate, PROVIDER) != before
