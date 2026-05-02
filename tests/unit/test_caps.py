"""Tests for `auto_invest.config.caps` (T018)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from auto_invest.config.caps import SizingCaps

VALID = {
    "per_trade_pct": Decimal("5.0"),
    "per_symbol_pct": Decimal("20.0"),
    "global_exposure_pct": Decimal("80.0"),
    "canary_capital_pct": Decimal("5.0"),
    "canary_min_duration_days": 10,
    "canary_acceptance_drawdown_pct": Decimal("3.0"),
}


def test_valid_caps_parse():
    caps = SizingCaps(**VALID)
    assert caps.per_trade_pct == Decimal("5.0")
    assert caps.canary_min_duration_days == 10


def test_caps_is_frozen():
    caps = SizingCaps(**VALID)
    with pytest.raises(ValidationError):
        caps.per_trade_pct = Decimal("99")  # type: ignore[misc]


def test_caps_rejects_extra_field():
    with pytest.raises(ValidationError):
        SizingCaps(**VALID, unexpected="oops")  # type: ignore[call-arg]


@pytest.mark.parametrize("field", list(VALID.keys()))
def test_caps_requires_each_field(field: str):
    payload = dict(VALID)
    del payload[field]
    with pytest.raises(ValidationError):
        SizingCaps(**payload)


@pytest.mark.parametrize(
    "field",
    [
        "per_trade_pct",
        "per_symbol_pct",
        "global_exposure_pct",
        "canary_capital_pct",
        "canary_acceptance_drawdown_pct",
    ],
)
def test_caps_pct_must_be_positive(field: str):
    payload = dict(VALID)
    payload[field] = Decimal("0")
    with pytest.raises(ValidationError):
        SizingCaps(**payload)


@pytest.mark.parametrize(
    "field",
    [
        "per_trade_pct",
        "per_symbol_pct",
        "global_exposure_pct",
        "canary_capital_pct",
        "canary_acceptance_drawdown_pct",
    ],
)
def test_caps_pct_must_be_at_most_100(field: str):
    payload = dict(VALID)
    payload[field] = Decimal("100.01")
    with pytest.raises(ValidationError):
        SizingCaps(**payload)


def test_caps_canary_duration_must_be_at_least_one():
    payload = dict(VALID)
    payload["canary_min_duration_days"] = 0
    with pytest.raises(ValidationError):
        SizingCaps(**payload)


def test_per_trade_must_not_exceed_per_symbol():
    payload = dict(VALID)
    payload["per_trade_pct"] = Decimal("25.0")  # > per_symbol_pct=20
    with pytest.raises(ValidationError, match="per_trade_pct <= per_symbol_pct"):
        SizingCaps(**payload)


def test_per_symbol_must_not_exceed_global():
    payload = dict(VALID)
    payload["per_symbol_pct"] = Decimal("90.0")  # > global_exposure_pct=80
    with pytest.raises(ValidationError, match="per_symbol_pct <= global_exposure_pct"):
        SizingCaps(**payload)


def test_canary_must_not_exceed_per_symbol():
    payload = dict(VALID)
    payload["canary_capital_pct"] = Decimal("25.0")  # > per_symbol_pct=20
    with pytest.raises(
        ValidationError, match="canary_capital_pct must not exceed caps.per_symbol_pct"
    ):
        SizingCaps(**payload)


def test_caps_boundary_values_accepted():
    # Equality at the boundary is allowed.
    caps = SizingCaps(
        per_trade_pct=Decimal("10.0"),
        per_symbol_pct=Decimal("10.0"),
        global_exposure_pct=Decimal("10.0"),
        canary_capital_pct=Decimal("10.0"),
        canary_min_duration_days=1,
        canary_acceptance_drawdown_pct=Decimal("1.0"),
    )
    assert caps.per_trade_pct == caps.per_symbol_pct == caps.global_exposure_pct
