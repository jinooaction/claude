"""KPI tier-threshold loader (R-T4, FR-T06).

The threshold table is operator-editable TOML at
`config/llm_kpi_thresholds.toml`. KPI names and `direction` are fixed;
operators may tune the numeric bands.
"""

from __future__ import annotations

import tomllib
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

Direction = Literal["higher_is_better", "lower_is_better"]
Tier = Literal["A", "B", "C", "N/A"]

REQUIRED_KPIS = (
    "cache_hit_rate",
    "tokens_per_decision_p95",
    "usd_per_decision_mean",
    "latency_p95_ms",
)

KPI_DIRECTIONS: dict[str, Direction] = {
    "cache_hit_rate": "higher_is_better",
    "tokens_per_decision_p95": "lower_is_better",
    "usd_per_decision_mean": "lower_is_better",
    "latency_p95_ms": "lower_is_better",
}


class ThresholdEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    direction: Direction
    tier_c: Decimal
    tier_b: Decimal
    tier_a: Decimal

    @model_validator(mode="after")
    def _check_band_order(self) -> ThresholdEntry:
        if self.direction == "higher_is_better":
            if not (self.tier_c < self.tier_b < self.tier_a):
                raise ValueError(
                    "higher_is_better requires tier_c < tier_b < tier_a"
                )
        else:
            if not (self.tier_c > self.tier_b > self.tier_a):
                raise ValueError(
                    "lower_is_better requires tier_c > tier_b > tier_a"
                )
        return self


class TierTable(BaseModel):
    """Maps KPI name -> threshold entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entries: dict[str, ThresholdEntry]

    def classify(self, kpi_name: str, value: Decimal | float | int) -> Tier:
        """Classify `value` for `kpi_name`. Empty/zero windows handled by caller."""
        entry = self.entries.get(kpi_name)
        if entry is None:
            return "N/A"
        v = Decimal(str(value))
        if entry.direction == "higher_is_better":
            if v >= entry.tier_a:
                return "A"
            if v >= entry.tier_b:
                return "B"
            if v >= entry.tier_c:
                return "C"
            return "N/A"
        # lower_is_better
        if v <= entry.tier_a:
            return "A"
        if v <= entry.tier_b:
            return "B"
        if v <= entry.tier_c:
            return "C"
        return "N/A"

    def thresholds_for(self, kpi_name: str) -> dict[str, str]:
        entry = self.entries.get(kpi_name)
        if entry is None:
            return {}
        return {
            "tier_c": str(entry.tier_c),
            "tier_b": str(entry.tier_b),
            "tier_a": str(entry.tier_a),
        }


class TierTableError(ValueError):
    """Raised on missing file, missing KPI, or schema violation."""


def load_thresholds(path: Path) -> TierTable:
    if not path.exists():
        raise TierTableError(f"threshold table not found: {path}")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise TierTableError(f"threshold table {path} is not valid TOML: {exc}") from exc

    entries: dict[str, ThresholdEntry] = {}
    for kpi_name, block in raw.items():
        if kpi_name not in REQUIRED_KPIS:
            raise TierTableError(f"unknown KPI {kpi_name!r}; expected one of {REQUIRED_KPIS}")
        if not isinstance(block, dict):
            raise TierTableError(f"threshold entry for {kpi_name!r} must be a TOML table")
        try:
            entry = ThresholdEntry(**block)
        except (ValueError, TypeError) as exc:
            raise TierTableError(
                f"threshold entry for {kpi_name!r} failed validation: {exc}"
            ) from exc
        if entry.direction != KPI_DIRECTIONS[kpi_name]:
            raise TierTableError(
                f"threshold entry for {kpi_name!r} has direction {entry.direction!r}; "
                f"must be {KPI_DIRECTIONS[kpi_name]!r}"
            )
        entries[kpi_name] = entry

    missing = [name for name in REQUIRED_KPIS if name not in entries]
    if missing:
        raise TierTableError(f"threshold table {path} missing KPIs: {missing}")

    return TierTable(entries=entries)
