"""CSV ingest validation tests (FR-B13 + contracts/ohlcv-csv.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_invest.backtest.ingest import IngestError, ingest_history

HEADER = "session_date,open,high,low,close,volume,session_schedule_tag\n"

VALID_CSV = HEADER + (
    "2024-01-02,185.640000,188.440000,183.890000,185.640000,82488700,regular\n"
    "2024-01-03,184.220000,185.880000,183.430000,184.250000,58414500,regular\n"
    "2024-01-04,182.150000,183.090000,180.880000,181.910000,71983600,regular\n"
    "2024-01-05,181.990000,182.760000,180.170000,181.180000,62303300,regular\n"
    "2024-01-08,182.090000,185.600000,181.500000,185.560000,59144500,regular\n"
)


def _src_with(tmp_path: Path, csv_body: str, file_name: str = "AAPL.csv") -> Path:
    src = tmp_path / "from"
    src.mkdir(exist_ok=True)
    (src / file_name).write_text(csv_body)
    return src


def test_valid_csv_ingests_and_returns_dataset_version(tmp_path: Path):
    src = _src_with(tmp_path, VALID_CSV)
    out = tmp_path / "history"
    result = ingest_history(src, out)
    assert result.files_ingested == 1
    assert result.rows_ingested == 5
    assert len(result.dataset_version) == 64
    assert (result.dataset_dir / "manifest.json").is_file()
    assert (result.dataset_dir / "bars.sqlite").is_file()


def test_header_mismatch_fails(tmp_path: Path):
    src = _src_with(tmp_path, "date,o,h,l,c,v,tag\n2024-01-02,1,1,1,1,1,regular\n")
    with pytest.raises(IngestError, match="HEADER_MISMATCH"):
        ingest_history(src, tmp_path / "history")


def test_unparseable_row_fails(tmp_path: Path):
    src = _src_with(tmp_path, HEADER + "2024-01-02,oops,1,1,1,1,regular\n")
    with pytest.raises(IngestError, match="UNPARSEABLE_ROW"):
        ingest_history(src, tmp_path / "history")


def test_bad_price_range_fails(tmp_path: Path):
    src = _src_with(tmp_path, HEADER + "2024-01-02,1,0.5,2,1,1,regular\n")
    with pytest.raises(IngestError, match="BAD_PRICE_RANGE"):
        ingest_history(src, tmp_path / "history")


def test_negative_price_fails(tmp_path: Path):
    src = _src_with(tmp_path, HEADER + "2024-01-02,-1,2,-2,1,1,regular\n")
    with pytest.raises(IngestError, match="BAD_PRICE_RANGE"):
        ingest_history(src, tmp_path / "history")


def test_bad_volume_fails(tmp_path: Path):
    src = _src_with(tmp_path, HEADER + "2024-01-02,1,2,0.5,1,-5,regular\n")
    with pytest.raises(IngestError, match="BAD_VOLUME"):
        ingest_history(src, tmp_path / "history")


def test_unknown_schedule_tag_fails(tmp_path: Path):
    src = _src_with(tmp_path, HEADER + "2024-01-02,1,2,0.5,1,1,bogus\n")
    with pytest.raises(IngestError, match="UNKNOWN_SCHEDULE_TAG"):
        ingest_history(src, tmp_path / "history")


def test_duplicate_date_fails(tmp_path: Path):
    body = HEADER + "2024-01-02,1,2,0.5,1,1,regular\n2024-01-02,1,2,0.5,1,1,regular\n"
    src = _src_with(tmp_path, body)
    with pytest.raises(IngestError, match="DUPLICATE_DATE"):
        ingest_history(src, tmp_path / "history")


def test_non_monotonic_date_fails(tmp_path: Path):
    body = HEADER + "2024-01-03,1,2,0.5,1,1,regular\n2024-01-02,1,2,0.5,1,1,regular\n"
    src = _src_with(tmp_path, body)
    with pytest.raises(IngestError, match="NON_MONOTONIC_DATE"):
        ingest_history(src, tmp_path / "history")


def test_zero_volume_regular_emits_warning(tmp_path: Path):
    body = HEADER + "2024-01-02,1,2,0.5,1,0,regular\n2024-01-03,1,2,0.5,1,1,regular\n"
    src = _src_with(tmp_path, body)
    result = ingest_history(src, tmp_path / "history")
    kinds = {w.kind for w in result.warnings}
    assert "zero_volume_regular" in kinds


def test_identical_inputs_produce_identical_dataset_version(tmp_path: Path):
    src1 = tmp_path / "src1"
    src1.mkdir()
    (src1 / "AAPL.csv").write_text(VALID_CSV)
    src2 = tmp_path / "src2"
    src2.mkdir()
    (src2 / "AAPL.csv").write_text(VALID_CSV)
    r1 = ingest_history(src1, tmp_path / "history1")
    r2 = ingest_history(src2, tmp_path / "history2")
    assert r1.dataset_version == r2.dataset_version


def test_re_ingest_same_content_reuses_existing(tmp_path: Path):
    src = _src_with(tmp_path, VALID_CSV)
    out = tmp_path / "history"
    r1 = ingest_history(src, out)
    r2 = ingest_history(src, out)
    assert r2.reused_existing is True
    assert r1.dataset_version == r2.dataset_version


def test_dry_run_does_not_write_dataset(tmp_path: Path):
    src = _src_with(tmp_path, VALID_CSV)
    out = tmp_path / "history"
    r = ingest_history(src, out, dry_run=True)
    assert not r.dataset_dir.exists()
    assert r.files_ingested == 1
