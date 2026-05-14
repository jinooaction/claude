"""HistoricalDataSource protocol + CSVDataSource adapter.

Per contracts/historical-data-source.md, the engine reads OHLCV bars
through a small protocol so future specs can drop in yfinance / KIS-
historical / IEX-Cloud adapters without engine changes. v1 ships ONE
adapter (`CSVDataSource`) backed by a single SQLite file per dataset
version. (Parquet was the original design; SQLite avoids a pyarrow dep
and indexes (symbol, session_date) cheaply for our scale.)
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol

import exchange_calendars as ec

from auto_invest.backtest.data_model import OHLCVBar


def trading_days_between(date_start: date, date_end: date) -> list[date]:
    """List XNYS trading days in [date_start, date_end] inclusive."""
    cal = ec.get_calendar("XNYS")
    sessions = cal.sessions_in_range(
        date_start.isoformat(), date_end.isoformat()
    )
    return [s.date() if hasattr(s, "date") else s for s in sessions]


class HistoricalDataSource(Protocol):
    @property
    def dataset_version(self) -> str: ...
    def list_symbols(self) -> list[str]: ...
    def session_dates(self, symbol: str) -> list[date]: ...
    def coverage_holes(
        self, symbols: list[str], date_start: date, date_end: date
    ) -> list[tuple[str, date]]: ...
    def read_bars(
        self, symbol: str, date_start: date, date_end: date
    ) -> list[OHLCVBar]: ...


@dataclass(frozen=True)
class ManifestFileEntry:
    symbol: str
    rows: int
    file_sha256: str
    session_date_min: date
    session_date_max: date


@dataclass(frozen=True)
class Manifest:
    dataset_version: str
    ingested_at_utc: str
    source_csv_paths: list[str]
    files: list[ManifestFileEntry]
    quality_warnings: list[dict]


def load_manifest(dataset_dir: Path) -> Manifest:
    payload = json.loads((dataset_dir / "manifest.json").read_text())
    return Manifest(
        dataset_version=payload["dataset_version"],
        ingested_at_utc=payload["ingested_at_utc"],
        source_csv_paths=list(payload.get("source_csv_paths", [])),
        files=[
            ManifestFileEntry(
                symbol=f["symbol"],
                rows=int(f["rows"]),
                file_sha256=f["file_sha256"],
                session_date_min=date.fromisoformat(f["session_date_min"]),
                session_date_max=date.fromisoformat(f["session_date_max"]),
            )
            for f in payload["files"]
        ],
        quality_warnings=list(payload.get("quality_warnings", [])),
    )


def latest_dataset_dir(history_root: Path) -> Path | None:
    """Return the most recently-ingested dataset directory by mtime."""
    if not history_root.exists():
        return None
    candidates = [
        p for p in history_root.iterdir()
        if p.is_dir() and (p / "manifest.json").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


class CSVDataSource:
    """v1 adapter — SQLite-backed snapshot of CSV ingest output."""

    def __init__(self, dataset_dir: Path) -> None:
        self._dir = dataset_dir
        self._manifest = load_manifest(dataset_dir)
        # Verify dataset_version matches the directory name (defense vs tampering).
        if dataset_dir.name != self._manifest.dataset_version:
            raise ValueError(
                f"manifest dataset_version {self._manifest.dataset_version} "
                f"does not match directory name {dataset_dir.name}"
            )
        self._db = sqlite3.connect(dataset_dir / "bars.sqlite")
        self._db.row_factory = sqlite3.Row

    @property
    def dataset_version(self) -> str:
        return self._manifest.dataset_version

    @property
    def manifest(self) -> Manifest:
        return self._manifest

    def list_symbols(self) -> list[str]:
        return sorted(f.symbol for f in self._manifest.files)

    def session_dates(self, symbol: str) -> list[date]:
        rows = self._db.execute(
            "SELECT session_date FROM ohlcv_bars WHERE symbol = ? ORDER BY session_date",
            (symbol,),
        ).fetchall()
        return [date.fromisoformat(r["session_date"]) for r in rows]

    def coverage_holes(
        self, symbols: list[str], date_start: date, date_end: date
    ) -> list[tuple[str, date]]:
        """Return missing (symbol, session_date) pairs.

        Uses `exchange_calendars` (XNYS) directly to know which session
        dates SHOULD exist in the requested range. We do NOT modify
        `worker/schedule.py` (K6); we re-use the same vendor library.
        """
        expected_dates = trading_days_between(date_start, date_end)
        holes: list[tuple[str, date]] = []
        for symbol in symbols:
            have = set(self.session_dates(symbol))
            for d in expected_dates:
                if d not in have:
                    holes.append((symbol, d))
        return holes

    def read_bars(
        self, symbol: str, date_start: date, date_end: date
    ) -> list[OHLCVBar]:
        rows = self._db.execute(
            """
            SELECT symbol, session_date, open, high, low, close, volume, session_schedule_tag
            FROM ohlcv_bars
            WHERE symbol = ? AND session_date >= ? AND session_date <= ?
            ORDER BY session_date
            """,
            (symbol, date_start.isoformat(), date_end.isoformat()),
        ).fetchall()
        return [
            OHLCVBar(
                symbol=r["symbol"],
                session_date=date.fromisoformat(r["session_date"]),
                open=Decimal(r["open"]),
                high=Decimal(r["high"]),
                low=Decimal(r["low"]),
                close=Decimal(r["close"]),
                volume=int(r["volume"]),
                session_schedule_tag=r["session_schedule_tag"],
            )
            for r in rows
        ]

    def close(self) -> None:
        self._db.close()


__all__ = [
    "CSVDataSource",
    "HistoricalDataSource",
    "Manifest",
    "ManifestFileEntry",
    "latest_dataset_dir",
    "load_manifest",
]
