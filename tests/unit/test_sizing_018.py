"""Spec 018 슬라이스 2: SizingResult + SIZING_DECISION 감사 기록 테스트."""

from __future__ import annotations

from decimal import Decimal

from auto_invest.config.rules import SizingConfig
from auto_invest.strategy.sizing import (
    SizingResult,
    sized_quantity_with_result,
)


def _cfg(mode: str = "target_vol", **kwargs) -> SizingConfig:
    defaults = dict(
        mode=mode,
        target_volatility_pct=Decimal("2.0"),
        lookback_bars=3,
        min_scale=Decimal("0"),
        max_scale=Decimal("1"),
    )
    defaults.update(kwargs)
    return SizingConfig(**defaults)


def _flat_closes(n: int = 10, val: float = 100.0) -> list[Decimal]:
    return [Decimal(str(val))] * n


def _volatile_closes(n: int = 10) -> list[Decimal]:
    # alternating values — high realized vol
    return [Decimal("100") if i % 2 == 0 else Decimal("80") for i in range(n)]


class TestSizingResultFixed:
    def test_fixed_mode_returns_base_unchanged(self):
        result = sized_quantity_with_result(
            base_qty=10,
            closes=_flat_closes(),
            sizing=None,
        )
        assert isinstance(result, SizingResult)
        assert result.final_qty == 10
        assert result.base_qty == 10
        assert result.sizing_mode == "fixed"
        assert result.realized_vol_pct is None
        assert result.vol_scale is None

    def test_fixed_sizing_config_returns_base(self):
        result = sized_quantity_with_result(
            base_qty=5,
            closes=_flat_closes(),
            sizing=_cfg(mode="fixed"),
        )
        assert result.final_qty == 5
        assert result.sizing_mode == "fixed"


class TestSizingResultTargetVol:
    def test_volatile_series_shrinks_qty(self):
        closes = _volatile_closes(10)
        result = sized_quantity_with_result(
            base_qty=100,
            closes=closes,
            sizing=_cfg(mode="target_vol", lookback_bars=3),
        )
        assert result.final_qty < 100
        assert result.realized_vol_pct is not None
        assert result.vol_scale is not None
        assert result.sizing_mode == "target_vol"

    def test_insufficient_bars_returns_base(self):
        result = sized_quantity_with_result(
            base_qty=10,
            closes=[Decimal("100")],
            sizing=_cfg(mode="target_vol", lookback_bars=20),
        )
        assert result.final_qty == 10
        assert result.realized_vol_pct is None

    def test_result_is_consistent_with_sized_quantity(self):
        from auto_invest.strategy.sizing import sized_quantity

        closes = _volatile_closes(10)
        cfg = _cfg(mode="target_vol", lookback_bars=3)
        expected = sized_quantity(base_qty=50, closes=closes, sizing=cfg)
        result = sized_quantity_with_result(base_qty=50, closes=closes, sizing=cfg)
        assert result.final_qty == expected


class TestSizingResultInverseVol:
    def test_group_scale_applied(self):
        result = sized_quantity_with_result(
            base_qty=100,
            closes=_flat_closes(),
            sizing=_cfg(mode="inverse_vol"),
            group_scale=Decimal("0.5"),
        )
        assert result.final_qty == 50
        assert result.group_scale == Decimal("0.5")
        assert result.sizing_mode == "inverse_vol"

    def test_group_scale_one_returns_base(self):
        result = sized_quantity_with_result(
            base_qty=10,
            closes=_flat_closes(),
            sizing=_cfg(mode="inverse_vol"),
            group_scale=Decimal("1"),
        )
        assert result.final_qty == 10
