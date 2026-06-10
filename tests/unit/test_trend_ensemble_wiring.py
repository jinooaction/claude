"""스펙 048 슬라이스 2 — 다중 속도 앙상블 *분수 노출*을 운영 리밸런서 경로에 배선.

스펙 048 슬라이스 1(`analytics/trend_ensemble.py`)은 엣지를 *측정*만 했다(샤프 2+/낙폭 3.7%,
Shiller 1871~). 이 슬라이스는 그 분수 노출을 실제 거래 경로(`strategy.trend` →
`strategy.rebalance.target_weights` → `config.rules.TrendFilterConfig` →
`execution.rebalancer._trend_spec`)에 싣는다. 순수·결정론·돈 0 이동.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from auto_invest.config.rules import PortfolioRebalanceConfig, TrendFilterConfig
from auto_invest.execution.rebalancer import _trend_spec
from auto_invest.strategy.rebalance import target_weights
from auto_invest.strategy.trend import (
    TrendEnsembleSpec,
    TrendSpec,
    apply_trend_ensemble_filter,
    ensemble_fraction,
)

_D0 = date(2024, 1, 1)


def _closes(values: list[float]) -> list[Decimal]:
    return [Decimal(str(v)) for v in values]


def _series(values: list[float]) -> dict[date, Decimal]:
    return {_D0 + timedelta(days=i): Decimal(str(v)) for i, v in enumerate(values)}


# ───────────────────────────── TrendEnsembleSpec 검증 ─────────────────────────────


def test_ensemble_spec_rejects_empty_or_short_windows():
    with pytest.raises(ValueError):
        TrendEnsembleSpec(windows=())
    with pytest.raises(ValueError):
        TrendEnsembleSpec(windows=(1, 5))  # w < 2
    with pytest.raises(ValueError):
        TrendEnsembleSpec(windows=(10,), on_insufficient="nonsense")
    # valid
    TrendEnsembleSpec(windows=(63, 126, 189, 252))


# ───────────────────────────── ensemble_fraction ─────────────────────────────


def test_fraction_all_above_is_one():
    # 마지막 종가가 모든 창의 SMA 위 → 1.0 (완전 노출).
    closes = _closes([10, 10, 10, 10, 30])
    assert ensemble_fraction(closes, TrendEnsembleSpec(windows=(2, 3, 4, 5))) == Decimal(
        "1.000000"
    )


def test_fraction_all_below_is_zero():
    closes = _closes([30, 30, 30, 30, 10])
    assert ensemble_fraction(closes, TrendEnsembleSpec(windows=(2, 3, 4, 5))) == Decimal(
        "0.000000"
    )


def test_fraction_partial_is_consensus_ratio():
    # 고점→하락→회복: 빠른 창(2,3)은 추세 위, 느린 창(6,7)은 아래 → 2/4 = 0.5.
    closes = _closes([20, 20, 20, 20, 10, 11, 12])
    frac = ensemble_fraction(closes, TrendEnsembleSpec(windows=(2, 3, 6, 7)))
    assert frac == Decimal("0.500000")


def test_fraction_insufficient_window_respects_policy():
    # n=2 < 5 인 창은 정책에 따라: hold→투자(1), cash→현금(0).
    closes = _closes([10, 11])  # 둘 다 w=2 SMA 위(11 > 10.5)
    hold = ensemble_fraction(
        closes, TrendEnsembleSpec(windows=(2, 5), on_insufficient="hold")
    )
    cash = ensemble_fraction(
        closes, TrendEnsembleSpec(windows=(2, 5), on_insufficient="cash")
    )
    assert hold == Decimal("1.000000")  # (1 + 1[hold]) / 2
    assert cash == Decimal("0.500000")  # (1 + 0[cash]) / 2


# ───────────────────────── apply_trend_ensemble_filter ─────────────────────────


def test_apply_scales_weight_by_fraction_no_renorm():
    # A 분수 0.5, B 분수 1.0 → {A:0.3, B:0.4}, 합 0.7 (나머지 현금, 재정규화 안 함).
    a = _series([20, 20, 20, 20, 10, 11, 12])  # 분수 0.5 (windows 2,3,6,7)
    b = _series([10, 10, 10, 10, 30, 31, 32])  # 모든 창 위 → 1.0
    weights = {"A": Decimal("0.6"), "B": Decimal("0.4")}
    filtered, decisions = apply_trend_ensemble_filter(
        weights,
        {"A": a, "B": b},
        TrendEnsembleSpec(windows=(2, 3, 6, 7)),
    )
    assert filtered == {"A": Decimal("0.300000"), "B": Decimal("0.400000")}
    assert sum(filtered.values()) == Decimal("0.700000")  # ≤ 1, 차이는 현금
    states = {d.symbol: d.state for d in decisions}
    assert states["A"] == "partial" and states["B"] == "above"


def test_apply_drops_fully_below_symbol():
    a = _series([30, 30, 30, 30, 10])  # 모든 창 아래 → 0
    weights = {"A": Decimal("1.0")}
    filtered, decisions = apply_trend_ensemble_filter(
        weights, {"A": a}, TrendEnsembleSpec(windows=(2, 3, 4))
    )
    assert filtered == {}  # 완전 현금
    assert decisions[0].kept is False


# ───────────────────────── target_weights 통합 ─────────────────────────


def test_target_weights_ensemble_fractional_exposure():
    # 동일 균등가중 2종목인데 추세 분수가 다르면 노출도 다르다.
    a = _series([20, 20, 20, 20, 10, 11, 12])  # 분수 0.5
    b = _series([10, 10, 10, 10, 30, 31, 32])  # 분수 1.0
    ranked = [("A", Decimal("1")), ("B", Decimal("1"))]
    w = target_weights(
        ranked_scores=ranked,
        closes_by_symbol={"A": a, "B": b},
        weight_scheme="equal",
        top_n=2,
        trend=TrendEnsembleSpec(windows=(2, 3, 6, 7)),
    )
    # 균등 0.5 each → A 0.5*0.5=0.25, B 0.5*1.0=0.5.
    assert w == {"A": Decimal("0.250000"), "B": Decimal("0.500000")}
    assert sum(w.values()) < Decimal("1")  # 나머지는 현금(방어)


def test_target_weights_trend_none_byte_identical():
    # trend=None → 가중치 손도 안 댐(합 1).
    ranked = [("A", Decimal("2")), ("B", Decimal("1"))]
    w = target_weights(
        ranked_scores=ranked, closes_by_symbol={}, weight_scheme="equal", top_n=2
    )
    assert sum(w.values()) == Decimal("1.000000")


# ───────────────────────── config + _trend_spec ─────────────────────────


def test_config_parses_and_validates_ensemble_windows():
    tf = TrendFilterConfig(ensemble_windows=(63, 126, 189, 252))
    assert tf.ensemble_windows == (63, 126, 189, 252)
    with pytest.raises(ValidationError):
        TrendFilterConfig(ensemble_windows=())
    with pytest.raises(ValidationError):
        TrendFilterConfig(ensemble_windows=(1, 5))  # w < 2


def _portfolio(trend_filter: TrendFilterConfig | None) -> PortfolioRebalanceConfig:
    return PortfolioRebalanceConfig(
        id="t",
        universe=("SPY", "IEF", "GLD"),
        weight_scheme="inverse_vol",
        weights={"momentum": Decimal("1.0")},
        top_n=3,
        trend_filter=trend_filter,
    )


def test_trend_spec_builds_ensemble_when_windows_set():
    cfg = _portfolio(
        TrendFilterConfig(ensemble_windows=(63, 126, 189, 252), on_insufficient="cash")
    )
    spec = _trend_spec(cfg)
    assert isinstance(spec, TrendEnsembleSpec)
    assert spec.windows == (63, 126, 189, 252)
    assert spec.on_insufficient == "cash"


def test_trend_spec_builds_single_speed_when_no_windows():
    cfg = _portfolio(TrendFilterConfig(method="sma", lookback=200))
    spec = _trend_spec(cfg)
    assert isinstance(spec, TrendSpec)
    assert spec.lookback == 200


def test_trend_spec_none_when_no_filter():
    assert _trend_spec(_portfolio(None)) is None
