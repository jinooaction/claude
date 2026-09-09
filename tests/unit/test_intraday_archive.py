import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from auto_invest.analytics.intraday_archive import review_archives
from auto_invest.market_data.intraday import CALENDAR, SYMBOLS, DataError, digest, iso, write_batch

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"


def day(root, session, *, provider="kis-nasdaq-partial-unadjusted", synthetic=False):
    opening = CALENDAR.session_open(session).to_pydatetime()
    closing = CALENDAR.session_close(session).to_pydatetime()
    rows = [dict(timestamp_utc=iso(opening + timedelta(minutes=5 * i)), symbol=symbol,
                 open=100, high=102, low=99, close=101, volume=1000)
            for i in range(int((closing - opening).total_seconds() // 300)) for symbol in SYMBOLS]
    path = root / session
    write_batch(path, dict(
        provider=provider, synthetic=synthetic,
        retrieved_at_utc=iso(closing + timedelta(minutes=1)), pages=[], bars=rows,
    ))
    return path


def review(root, output):
    return review_archives(root, output, PREREG, "a" * 40)


@pytest.fixture
def archives(tmp_path):
    root = tmp_path / "sessions"
    day(root, "2026-09-03")
    day(root, "2026-09-04")
    return root


def test_complete_archives_reach_existing_research_without_becoming_forward_evidence(archives):
    original = {str(p): p.read_bytes() for p in archives.rglob("*") if p.is_file()}
    output = archives.parent / "review"
    result = review(archives, output)
    assert result["session_count"] == 2
    assert result["missing_sessions"] == 754 and result["missing_calendar_sessions"] == 0
    assert result["decision"]["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert result["observation_type"] == "HISTORICAL_RESEARCH"
    assert result["live_eligible"] is False and result["orders_submitted"] == 0
    assert json.loads((output / "review.json").read_bytes()) == result
    assert len(json.loads((output / "source.json").read_bytes())["archives"]) == 2
    assert len(json.loads((output / "research.json").read_bytes())["candidate_registry"]) == 18
    assert (output / "ledger.csv").is_file()
    assert all(Path(p).read_bytes() == value for p, value in original.items())
    with pytest.raises(DataError, match="OUTPUT_EXISTS"):
        review(archives, output)


@pytest.mark.parametrize("file", ["manifest.json", "source.json", "SPY.csv"])
def test_corruption_never_produces_review_marker(archives, file):
    (archives / "2026-09-03" / file).write_text("corrupt")
    output = archives.parent / "review"
    with pytest.raises(DataError, match="INTEGRITY_INVALID"):
        review(archives, output)
    assert not output.exists()


def test_rehashed_csv_must_still_agree_with_raw_source(archives):
    folder = archives / "2026-09-03"
    csv = folder / "SPY.csv"
    csv.write_text(csv.read_text().replace(",101,1000", ",100,1000"))
    manifest = json.loads((folder / "manifest.json").read_bytes())
    manifest["files"]["SPY"]["sha256"] = digest(csv.read_bytes())
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(DataError, match="SOURCE_CSV_DISAGREE"):
        review(archives, archives.parent / "review")


@pytest.mark.parametrize("change", ["missing", "link", "partial", "wrong_day"])
def test_incomplete_or_relabelled_archives_are_not_silently_skipped(archives, change):
    folder = archives / "2026-09-03"
    if change == "missing":
        (folder / "SPY.csv").unlink()
    elif change == "link":
        target = folder / "SPY.csv"
        target.rename(folder / "original.csv")
        target.symlink_to(folder / "original.csv")
    elif change == "partial":
        (archives / "2026-09-05-partial").mkdir()
    else:
        folder.rename(archives / "2026-09-02")
    with pytest.raises(DataError):
        review(archives, archives.parent / "review")


@pytest.mark.parametrize("change", [{"synthetic": True}, {"provider": "alpaca-sip-split"}])
def test_source_contracts_cannot_be_mixed(archives, change):
    day(archives, "2026-09-08", **change)
    with pytest.raises(DataError, match="SOURCE_MIXED"):
        review(archives, archives.parent / "review")


def test_actual_calendar_gaps_are_reported_as_missing_evidence(tmp_path):
    root = tmp_path / "sessions"
    day(root, "2026-09-02")
    day(root, "2026-09-04")
    result = review(root, tmp_path / "review")
    assert result["missing_calendar_sessions"] == 1
    assert "archive_calendar_sessions_missing" in result["decision"]["reasons"]
    assert result["decision"]["passed"] is False


def test_output_cannot_pollute_the_original_archive(archives):
    with pytest.raises(DataError, match="OUTPUT_INSIDE_SOURCE"):
        review(archives, archives / "review")


def test_retained_service_staging_is_counted_but_never_counted_as_a_session(archives):
    partial = archives / ("2026-09-03-partial-" + "a" * 32)
    partial.mkdir()
    (partial / "manifest.json").write_text("incomplete")
    result = review(archives, archives.parent / "review")
    assert result["session_count"] == 2 and result["incomplete_archive_count"] == 1
    assert (partial / "manifest.json").read_text() == "incomplete"


def test_failed_evaluation_never_leaves_a_completed_review(archives, monkeypatch):
    from auto_invest.analytics import intraday_archive

    def fail(*args, **kwargs):
        raise RuntimeError("simulated interruption")

    monkeypatch.setattr(intraday_archive, "run_intraday_paper_challenger", fail)
    output = archives.parent / "review"
    with pytest.raises(RuntimeError):
        review(archives, output)
    assert (output / "manifest.json").is_file()
    assert not (output / "review.json").exists()


def test_synthetic_history_remains_synthetic(tmp_path):
    root = tmp_path / "sessions"
    day(root, "2026-09-04", synthetic=True)
    result = review(root, tmp_path / "review")
    assert result["synthetic"] is True and result["live_eligible"] is False
    assert "synthetic_dataset_not_promotion_evidence" in result["decision"]["reasons"]


def test_cli_runs_without_broker_credentials_or_a_trading_database(archives):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("KIS_", "APCA_"))}
    result = subprocess.run(
        [sys.executable, "scripts/intraday_operator.py", "history-review", "--archives",
         str(archives), "--out", str(archives.parent / "review")], cwd=ROOT, env=env,
        text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["session_count"] == 2
    assert not list(archives.parent.rglob("*.db"))
