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


def _session_date_of(bar_open_utc: str) -> date:
    """price_bars.bar_open_utc(ISO 타임스탬프) → 세션 날짜."""
    return date.fromisoformat(bar_open_utc[:10])


class SqliteBarDataSource:
    """라이브/페이퍼 워커의 ``price_bars`` 테이블을 HistoricalDataSource 로 노출.

    스펙 008 백테스트 엔진(``CSVDataSource``)은 ingest-history 가 만든 CSV 데이터셋을 읽지만,
    라이브 인스턴스가 backfill-bars 로 채우는 일봉은 SQLite ``price_bars`` 에 있다. 이 어댑터로
    재지정 캐너리(스펙 055 ④ 게이트)가 *토너먼트·라이브 워커와 같은 바*로 챔피언을 검증한다 —
    별도 CSV ingest 없이 폐회로가 인스턴스 데이터로 실제로 닫힌다. 읽기 전용(바를 쓰지 않음).
    """

    def __init__(self, conn: sqlite3.Connection, *, timeframe: str = "1d") -> None:
        self._conn = conn
        self._timeframe = timeframe

    @property
    def dataset_version(self) -> str:
        return f"sqlite-price_bars-{self._timeframe}"

    def list_symbols(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT symbol FROM price_bars WHERE timeframe = ? ORDER BY symbol",
            (self._timeframe,),
        ).fetchall()
        return [r[0] for r in rows]

    def _bars_for(self, symbol: str) -> list:
        from auto_invest.market_data.store import get_bars

        return get_bars(self._conn, symbol=symbol, timeframe=self._timeframe)

    def session_dates(self, symbol: str) -> list[date]:
        return [_session_date_of(b.bar_open_utc) for b in self._bars_for(symbol)]

    def coverage_holes(
        self, symbols: list[str], date_start: date, date_end: date
    ) -> list[tuple[str, date]]:
        """기대 거래일(XNYS) 중 저장된 바가 없는 (심볼, 날짜) — CSVDataSource 와 같은 의미."""
        expected = set(trading_days_between(date_start, date_end))
        holes: list[tuple[str, date]] = []
        for s in symbols:
            present = {_session_date_of(b.bar_open_utc) for b in self._bars_for(s)}
            holes.extend((s, d) for d in sorted(expected - present))
        return holes

    def read_bars(
        self, symbol: str, date_start: date, date_end: date
    ) -> list[OHLCVBar]:
        out: list[OHLCVBar] = []
        for b in self._bars_for(symbol):
            d = _session_date_of(b.bar_open_utc)
            if date_start <= d <= date_end:
                out.append(
                    OHLCVBar(
                        symbol=b.symbol,
                        session_date=d,
                        open=b.open_usd,
                        high=b.high_usd,
                        low=b.low_usd,
                        close=b.close_usd,
                        volume=max(0, int(b.volume)),
                        session_schedule_tag="regular",
                    )
                )
        return out


__all__ = [
    "CSVDataSource",
    "HistoricalDataSource",
    "Manifest",
    "ManifestFileEntry",
    "SqliteBarDataSource",
    "latest_dataset_dir",
    "load_manifest",
]
