"""Loader for `config/canary_bands.toml` (T008).

Contract: see `specs/007-canary-hardening/contracts/canary-bands-toml.md`.

Hard constraints the loader enforces (beyond pydantic schema):

  - `risk_gate_violations` MUST equal 0 (FR-C01 #2 — pinned, not amendable).
  - `audit_integrity_failures` MUST equal 0 (FR-C01 #3 — pinned).
  - `trading_days >= 30` for L2 (FR-C02 minimum).
  - `trading_days >= 45` for L3 (FR-C02 minimum).
  - All rate metrics (`pnl_drawdown_pct`, `latency_p95_regression_pct`,
    `llm_cost_regression_pct`) MUST be >= 0; a negative band would mean
    "regression to the baseline is OK", which violates the spec.
  - Unknown tier names other than L2 / L3 / L4 are rejected (L4 is
    accepted forward-compatibly per R-C10 even though spec 005's L4 is
    still a stub).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import ValidationError

from auto_invest.canary.data_model import TierBands

DEFAULT_PATH = Path("config/canary_bands.toml")

_TIER_MIN_TRADING_DAYS: dict[str, int] = {
    "L2": 30,
    "L3": 45,
}

_ALLOWED_TIERS = frozenset({"L2", "L3", "L4"})


class CanaryBandsConfigError(ValueError):
    """Raised on any violation of `canary_bands.toml`'s contract."""


def load_bands(path: Path | str = DEFAULT_PATH) -> dict[str, TierBands]:
    """Parse + validate `canary_bands.toml`.

    Returns ``{tier_name: TierBands}`` with every value frozen. Raises
    ``CanaryBandsConfigError`` on any contract violation.
    """

    p = Path(path)
    if not p.exists():
        raise CanaryBandsConfigError(f"canary bands file not found: {p}")

    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise CanaryBandsConfigError(f"invalid TOML in {p}: {exc}") from exc

    if not raw:
        raise CanaryBandsConfigError(f"empty bands file: {p} — at least one tier required")

    bands: dict[str, TierBands] = {}
    for tier_name, body in raw.items():
        if tier_name not in _ALLOWED_TIERS:
            raise CanaryBandsConfigError(
                f"unknown tier '{tier_name}' in {p}; "
                f"allowed: {sorted(_ALLOWED_TIERS)}"
            )
        if not isinstance(body, dict):
            raise CanaryBandsConfigError(
                f"tier '{tier_name}' must be a TOML table; got {type(body).__name__}"
            )
        try:
            tier = TierBands.model_validate(body)
        except ValidationError as exc:
            raise CanaryBandsConfigError(
                f"tier '{tier_name}' in {p} failed validation: {exc}"
            ) from exc

        _enforce_hard_constraints(tier_name, tier, source=p)
        bands[tier_name] = tier

    if not bands:
        raise CanaryBandsConfigError(f"no valid tiers parsed from {p}")
    return bands


def _enforce_hard_constraints(tier_name: str, tier: TierBands, *, source: Path) -> None:
    if tier.risk_gate_violations != 0:
        raise CanaryBandsConfigError(
            f"{source}:[{tier_name}].risk_gate_violations must equal 0 "
            f"(FR-C01 #2; got {tier.risk_gate_violations}). "
            f"Softening this is a spec amendment, not a config edit."
        )
    if tier.audit_integrity_failures != 0:
        raise CanaryBandsConfigError(
            f"{source}:[{tier_name}].audit_integrity_failures must equal 0 "
            f"(FR-C01 #3; got {tier.audit_integrity_failures})."
        )

    min_days = _TIER_MIN_TRADING_DAYS.get(tier_name)
    if min_days is not None and tier.trading_days < min_days:
        raise CanaryBandsConfigError(
            f"{source}:[{tier_name}].trading_days={tier.trading_days} "
            f"below FR-C02 minimum ({min_days})."
        )

    for field_name in (
        "pnl_drawdown_pct",
        "latency_p95_regression_pct",
        "llm_cost_regression_pct",
    ):
        value: float = getattr(tier, field_name)
        if value < 0:
            raise CanaryBandsConfigError(
                f"{source}:[{tier_name}].{field_name}={value} "
                f"must be >= 0 (negative bands would accept any regression)."
            )
