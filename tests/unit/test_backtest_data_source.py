"""CSVDataSource adapter tests (coverage_holes + read_bars + version stability)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from auto_invest.backtest.data_source import CSVDataSource, latest_dataset_dir
from auto_invest.backtest.ingest import ingest_history

VALID_CSV = """\
session_date,open,high,low,close,volume,session_schedule_tag
2024-01-02,185.640000,188.440000,183.890000,185.640000,82488700,regular
2024-01-03,184.220000,185.880000,183.430000,184.250000,58414500,regular
2024-01-04,182.150000,183.090000,180.880000,181.910000,71983600,regular
2024-01-05,181.990000,182.760000,180.170000,181.180000,62303300,regular
2024-01-08,182.090000,185.600000,181.500000,185.560000,59144500,regular
"""


@pytest.fixture
def ingested_dataset(tmp_path: Path):
    src = tmp_path / "from"
    src.mkdir()
    (src / "AAPL.csv").write_text(VALID_CSV)
    out = tmp_path / "history"
    result = ingest_history(src, out)
    return result


def test_list_symbols(ingested_dataset):
    ds = CSVDataSource(ingested_dataset.dataset_dir)
    try:
        assert ds.list_symbols() == ["AAPL"]
    finally:
        ds.close()


def test_session_dates_sorted_ascending(ingested_dataset):
    ds = CSVDataSource(ingested_dataset.dataset_dir)
    try:
        dates = ds.session_dates("AAPL")
        assert dates == [
            date(2024, 1, 2),
            date(2024, 1, 3),
            date(2024, 1, 4),
            date(2024, 1, 5),
            date(2024, 1, 8),
        ]
    finally:
        ds.close()


def test_read_bars_filters_inclusive_range(ingested_dataset):
    ds = CSVDataSource(ingested_dataset.dataset_dir)
    try:
        bars = ds.read_bars("AAPL", date(2024, 1, 3), date(2024, 1, 5))
        assert [b.session_date for b in bars] == [
            date(2024, 1, 3),
            date(2024, 1, 4),
            date(2024, 1, 5),
        ]
    finally:
        ds.close()


def test_coverage_holes_returns_missing_trading_days(ingested_dataset):
    ds = CSVDataSource(ingested_dataset.dataset_dir)
    try:
        # The fixture covers 2024-01-02..2024-01-08 (missing 2024-01-09..2024-01-31).
        holes = ds.coverage_holes(["AAPL"], date(2024, 1, 2), date(2024, 1, 31))
        missing_dates = {d for _, d in holes}
        # 2024-01-09 is a Tuesday (NYSE open) but not in our fixture → must be missing.
        assert date(2024, 1, 9) in missing_dates
        # 2024-01-02 IS in our fixture → must NOT be missing.
        assert date(2024, 1, 2) not in missing_dates
        # 2024-01-06 is a Saturday → MUST NOT appear (calendar-closed).
        assert date(2024, 1, 6) not in missing_dates
    finally:
        ds.close()


def test_coverage_holes_empty_when_complete(ingested_dataset):
    ds = CSVDataSource(ingested_dataset.dataset_dir)
    try:
        holes = ds.coverage_holes(["AAPL"], date(2024, 1, 2), date(2024, 1, 5))
        # 2024-01-02, 03, 04, 05 are all in fixture; 06 (Sat) & 07 (Sun) are
        # calendar-closed so not expected. No holes.
        assert holes == []
    finally:
        ds.close()


def test_dataset_version_matches_directory_name(ingested_dataset):
    ds = CSVDataSource(ingested_dataset.dataset_dir)
    try:
        assert ds.dataset_version == ingested_dataset.dataset_dir.name
    finally:
        ds.close()


def test_dataset_version_mismatch_raises(tmp_path: Path, ingested_dataset):
    # Rename the directory; the manifest still says the original hash.
    renamed = tmp_path / "history" / "wrong_name"
    ingested_dataset.dataset_dir.rename(renamed)
    with pytest.raises(ValueError, match="does not match"):
        CSVDataSource(renamed)


def test_latest_dataset_dir_picks_most_recent(tmp_path: Path):
    history = tmp_path / "history"
    history.mkdir()
    src = tmp_path / "from"
    src.mkdir()
    (src / "AAPL.csv").write_text(VALID_CSV)
    ingest_history(src, history)
    # Mutate fixture so we get a different dataset_version, then re-ingest.
    (src / "MSFT.csv").write_text(VALID_CSV)
    r2 = ingest_history(src, history)
    latest = latest_dataset_dir(history)
    assert latest is not None
    # r2's snapshot is newer (mtime > r1's).
    assert latest.name == r2.dataset_version
