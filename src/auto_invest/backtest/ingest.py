"""CSV → SQLite OHLCV ingest.

Implements `contracts/ohlcv-csv.md`. The ingest job is offline,
filesystem-only, and emits NO audit-log rows for itself (data quality
warnings will surface during the backtest run, not at ingest time).
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from auto_invest.backtest.data_model import DataQualityWarning, OHLCVBar
from auto_invest.backtest.data_source import trading_days_between

REQUIRED_HEADER = [
    "session_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "session_schedule_tag",
]
VALID_TAGS = {"regular", "early_close", "holiday", "halted"}


class IngestError(Exception):
    """Raised on any fatal CSV validation failure (rules 1–7)."""

    def __init__(self, file: str, rule: str, details: str, line: int | None = None):
        self.file = file
        self.rule = rule
        self.details = details
        self.line = line
        loc = f":{line}" if line is not None else ""
        super().__init__(f"{file}{loc}: {rule}: {details}")


@dataclass
class IngestResult:
    dataset_version: str
    dataset_dir: Path
    files_ingested: int
    rows_ingested: int
    warnings: list[DataQualityWarning] = field(default_factory=list)
    reused_existing: bool = False


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_decimal(value: str, file: str, line: int, field_name: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except (InvalidOperation, ValueError) as exc:
        raise IngestError(
            file, "UNPARSEABLE_ROW", f"{field_name}={value!r} not a decimal", line
        ) from exc


def _read_and_validate_csv(path: Path) -> tuple[list[OHLCVBar], list[DataQualityWarning]]:
    file = path.name
    bars: list[OHLCVBar] = []
    warnings: list[DataQualityWarning] = []
    symbol = path.stem.upper()
    with path.open(newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise IngestError(file, "HEADER_MISMATCH", "file is empty") from exc
        # Rule 1 — exact header match (lowercase, in declared order)
        if [h.strip().lower() for h in header] != REQUIRED_HEADER:
            raise IngestError(
                file,
                "HEADER_MISMATCH",
                f"expected {REQUIRED_HEADER}, got {header}",
            )
        prev_date: date | None = None
        seen: set[date] = set()
        for line_no, row in enumerate(reader, start=2):
            if not any(cell.strip() for cell in row):
                continue
            if len(row) != 7:
                raise IngestError(
                    file, "UNPARSEABLE_ROW", f"expected 7 fields, got {len(row)}", line_no
                )
            try:
                d = date.fromisoformat(row[0].strip())
            except ValueError as exc:
                raise IngestError(
                    file, "UNPARSEABLE_ROW", f"session_date={row[0]!r}", line_no
                ) from exc
            o = _parse_decimal(row[1], file, line_no, "open")
            h = _parse_decimal(row[2], file, line_no, "high")
            lo = _parse_decimal(row[3], file, line_no, "low")
            c = _parse_decimal(row[4], file, line_no, "close")
            try:
                v = int(row[5].strip())
            except ValueError as exc:
                raise IngestError(
                    file, "UNPARSEABLE_ROW", f"volume={row[5]!r}", line_no
                ) from exc
            tag = row[6].strip()
            # Rule 5 — tag whitelist
            if tag not in VALID_TAGS:
                raise IngestError(
                    file, "UNKNOWN_SCHEDULE_TAG", f"tag={tag!r}", line_no
                )
            # Rule 3 — price range sanity
            if any(p <= 0 for p in (o, h, lo, c)):
                raise IngestError(
                    file, "BAD_PRICE_RANGE", "non-positive price", line_no
                )
            if lo > min(o, h, c) or h < max(o, lo, c):
                raise IngestError(
                    file,
                    "BAD_PRICE_RANGE",
                    f"low={lo} open={o} high={h} close={c}",
                    line_no,
                )
            # Rule 4 — volume non-negative
            if v < 0:
                raise IngestError(file, "BAD_VOLUME", f"volume={v}", line_no)
            # Rule 6 — duplicate date
            if d in seen:
                raise IngestError(
                    file, "DUPLICATE_DATE", f"date={d.isoformat()}", line_no
                )
            seen.add(d)
            # Rule 7 — monotonic ascending
            if prev_date is not None and d <= prev_date:
                raise IngestError(
                    file,
                    "NON_MONOTONIC_DATE",
                    f"date={d} after {prev_date}",
                    line_no,
                )
            prev_date = d
            # Construct the bar (also validates via pydantic).
            bar = OHLCVBar(
                symbol=symbol,
                session_date=d,
                open=o,
                high=h,
                low=lo,
                close=c,
                volume=v,
                session_schedule_tag=tag,  # type: ignore[arg-type]
            )
            bars.append(bar)
            # Warnings (non-fatal).
            if v == 0 and tag == "regular":
                warnings.append(
                    DataQualityWarning(
                        symbol=symbol,
                        session_date=d,
                        kind="zero_volume_regular",
                        note=f"line {line_no}",
                    )
                )
    # Cross-bar checks once we have the whole series.
    for i in range(1, len(bars)):
        prev = bars[i - 1].session_date
        cur = bars[i].session_date
        if (cur - prev) > timedelta(days=7):
            warnings.append(
                DataQualityWarning(
                    symbol=symbol,
                    session_date=cur,
                    kind="gap_over_7_days",
                    note=f"gap from {prev} to {cur}",
                )
            )
    # Schedule-tag mismatch (compared to XNYS calendar).
    if bars:
        cal_dates = set(trading_days_between(bars[0].session_date, bars[-1].session_date))
        for bar in bars:
            cal_open = bar.session_date in cal_dates
            tag_open = bar.session_schedule_tag in ("regular", "early_close")
            if cal_open != tag_open:
                warnings.append(
                    DataQualityWarning(
                        symbol=symbol,
                        session_date=bar.session_date,
                        kind="schedule_tag_mismatch",
                        note=f"tag={bar.session_schedule_tag}; cal_open={cal_open}",
                    )
                )
    return bars, warnings


def _compute_dataset_version(csv_files: list[Path]) -> tuple[str, list[tuple[str, int, str]]]:
    """Return (dataset_version_hex, sorted list of (symbol, size, sha256))."""
    manifest_entries: list[tuple[str, int, str]] = []
    for p in csv_files:
        symbol = p.stem.upper()
        manifest_entries.append((symbol, p.stat().st_size, _file_sha256(p)))
    manifest_entries.sort()
    canonical = json.dumps(manifest_entries, separators=(",", ":"), sort_keys=True)
    dataset_version = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return dataset_version, manifest_entries


def ingest_history(
    from_dir: Path,
    out_dir: Path,
    *,
    dry_run: bool = False,
) -> IngestResult:
    """Ingest every <SYMBOL>.csv under `from_dir` into a versioned snapshot.

    Raises `IngestError` on the first validation failure (no partial ingest).
    """
    if not from_dir.is_dir():
        raise IngestError(str(from_dir), "USAGE", "from-dir does not exist")
    csv_files = sorted(p for p in from_dir.glob("*.csv") if p.is_file())
    if not csv_files:
        raise IngestError(str(from_dir), "USAGE", "no CSV files found")

    dataset_version, manifest_entries = _compute_dataset_version(csv_files)
    dataset_dir = out_dir / dataset_version

    # Idempotency: same content → reuse existing snapshot.
    if dataset_dir.exists() and (dataset_dir / "manifest.json").exists():
        existing = json.loads((dataset_dir / "manifest.json").read_text())
        if existing.get("dataset_version") == dataset_version:
            return IngestResult(
                dataset_version=dataset_version,
                dataset_dir=dataset_dir,
                files_ingested=len(csv_files),
                rows_ingested=sum(int(f["rows"]) for f in existing.get("files", [])),
                warnings=[],
                reused_existing=True,
            )

    if dry_run:
        # Validate without writing.
        warnings_all: list[DataQualityWarning] = []
        rows_total = 0
        for p in csv_files:
            _, w = _read_and_validate_csv(p)
            warnings_all.extend(w)
            rows_total += sum(1 for _ in p.open()) - 1
        return IngestResult(
            dataset_version=dataset_version,
            dataset_dir=dataset_dir,
            files_ingested=len(csv_files),
            rows_ingested=rows_total,
            warnings=warnings_all,
            reused_existing=False,
        )

    dataset_dir.mkdir(parents=True, exist_ok=False)
    db_path = dataset_dir / "bars.sqlite"
    db = sqlite3.connect(db_path)
    db.execute(
        """
        CREATE TABLE ohlcv_bars (
            symbol TEXT NOT NULL,
            session_date TEXT NOT NULL,
            open TEXT NOT NULL,
            high TEXT NOT NULL,
            low TEXT NOT NULL,
            close TEXT NOT NULL,
            volume INTEGER NOT NULL,
            session_schedule_tag TEXT NOT NULL,
            PRIMARY KEY (symbol, session_date)
        )
        """
    )
    db.execute("CREATE INDEX idx_session_date ON ohlcv_bars(session_date)")

    files_meta: list[dict] = []
    warnings_all: list[DataQualityWarning] = []
    rows_total = 0
    for p in csv_files:
        bars, warnings = _read_and_validate_csv(p)
        warnings_all.extend(warnings)
        db.executemany(
            """
            INSERT INTO ohlcv_bars
                (symbol, session_date, open, high, low, close, volume, session_schedule_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    b.symbol,
                    b.session_date.isoformat(),
                    str(b.open),
                    str(b.high),
                    str(b.low),
                    str(b.close),
                    b.volume,
                    b.session_schedule_tag,
                )
                for b in bars
            ],
        )
        files_meta.append(
            {
                "symbol": p.stem.upper(),
                "rows": len(bars),
                "file_sha256": _file_sha256(p),
                "session_date_min": bars[0].session_date.isoformat() if bars else "",
                "session_date_max": bars[-1].session_date.isoformat() if bars else "",
            }
        )
        rows_total += len(bars)
    db.commit()
    db.close()

    manifest = {
        "dataset_version": dataset_version,
        "ingested_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_csv_paths": [str(p) for p in csv_files],
        "files": files_meta,
        "quality_warnings": [
            {
                "symbol": w.symbol,
                "session_date": w.session_date.isoformat() if w.session_date else None,
                "kind": w.kind,
                "note": w.note,
            }
            for w in warnings_all
        ],
    }
    (dataset_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))

    return IngestResult(
        dataset_version=dataset_version,
        dataset_dir=dataset_dir,
        files_ingested=len(csv_files),
        rows_ingested=rows_total,
        warnings=warnings_all,
        reused_existing=False,
    )


def cleanup_dataset_dir(dataset_dir: Path) -> None:
    """Test helper: remove a dataset_dir entirely."""
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)


__all__ = [
    "REQUIRED_HEADER",
    "VALID_TAGS",
    "IngestError",
    "IngestResult",
    "cleanup_dataset_dir",
    "ingest_history",
]
