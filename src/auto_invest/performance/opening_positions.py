"""Verified pre-system account lots used only as performance opening state."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from auto_invest.config.loader import ConfigError


class OpeningPositionsError(ConfigError):
    """Opening-position evidence is missing required, trustworthy fields."""


@dataclass(frozen=True)
class OpeningPosition:
    symbol: str
    qty: int
    avg_cost_usd: Decimal


def load_opening_positions(path: Path) -> tuple[OpeningPosition, ...]:
    if not path.exists():
        raise OpeningPositionsError(f"opening-position file not found: {path}")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise OpeningPositionsError(f"opening-position TOML parse failed ({path}): {exc}") from exc

    if not str(raw.get("source_run_id", "")).strip():
        raise OpeningPositionsError(f"{path}: source_run_id is required")
    if not str(raw.get("observed_at_utc", "")).strip():
        raise OpeningPositionsError(f"{path}: observed_at_utc is required")

    entries = raw.get("positions")
    if not isinstance(entries, list) or not entries:
        raise OpeningPositionsError(f"{path}: [[positions]] must be a non-empty array")

    result: list[OpeningPosition] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise OpeningPositionsError(f"{path}: positions[{index}] must be a table")
        symbol_raw = entry.get("symbol")
        qty = entry.get("qty")
        avg_raw = entry.get("avg_cost_usd")
        if not isinstance(symbol_raw, str) or not symbol_raw.strip():
            raise OpeningPositionsError(f"{path}: positions[{index}].symbol is invalid")
        symbol = symbol_raw.strip().upper()
        if symbol in seen:
            raise OpeningPositionsError(f"{path}: duplicate symbol {symbol}")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            raise OpeningPositionsError(f"{path}: {symbol} qty must be a positive integer")
        try:
            avg_cost = Decimal(str(avg_raw))
        except (InvalidOperation, ValueError) as exc:
            raise OpeningPositionsError(f"{path}: {symbol} avg_cost_usd is invalid") from exc
        if not avg_cost.is_finite() or avg_cost <= 0:
            raise OpeningPositionsError(f"{path}: {symbol} avg_cost_usd must be positive")
        result.append(OpeningPosition(symbol=symbol, qty=qty, avg_cost_usd=avg_cost))
        seen.add(symbol)
    return tuple(result)
