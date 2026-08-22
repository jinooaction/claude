"""Deterministic strategy-performance scope contract (spec 147)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

from auto_invest.performance.opening_positions import OpeningPosition


class MeasurementContractError(ValueError):
    """The strategy evidence scope is missing or conflicts with the strategy."""


@dataclass(frozen=True)
class MeasurementContract:
    contract_id: str
    scope: str
    excluded_symbols: tuple[str, ...]
    strategy_universe: tuple[str, ...]

    SCHEMA_VERSION = "1.0"

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "contract_id": self.contract_id,
            "scope": self.scope,
            "excluded_symbols": list(self.excluded_symbols),
            "strategy_universe": list(self.strategy_universe),
        }


def build_strategy_measurement_contract(
    opening_positions: Iterable[OpeningPosition],
    *,
    strategy_universe: Iterable[str] = (),
) -> MeasurementContract:
    excluded = tuple(sorted({row.symbol.strip().upper() for row in opening_positions}))
    universe = tuple(sorted({symbol.strip().upper() for symbol in strategy_universe}))
    if not excluded:
        raise MeasurementContractError(
            "verified opening positions are required for live strategy scope"
        )
    overlap = sorted(set(excluded) & set(universe))
    if overlap:
        raise MeasurementContractError(
            "opening-position exclusions overlap the strategy universe: " + ", ".join(overlap)
        )
    payload = {
        "schema_version": MeasurementContract.SCHEMA_VERSION,
        "scope": "strategy",
        "excluded_symbols": excluded,
        "strategy_universe": universe,
        "rule": "exclude-pre-system-symbol-fills-and-opening-lots",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return MeasurementContract(
        contract_id="sha256:" + hashlib.sha256(encoded).hexdigest(),
        scope="strategy",
        excluded_symbols=excluded,
        strategy_universe=universe,
    )
