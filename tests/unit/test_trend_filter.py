"""스펙 036 — 절대 모멘텀 추세 필터(드로다운 방어 오버레이) 테스트.

추세 위 종목은 가중치 유지, 추세 아래는 현금(0)으로, 데이터 부족은 정책대로.
재정규화하지 않으므로 합이 1 미만이 될 수 있다(나머지=현금). 결정론 검증.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from auto_invest.strategy.rebalance import target_weights
from auto_invest.strategy.trend import (
    METHOD_ABSOLUTE_MOMENTUM,
    METHOD_SMA,
    ON_INSUFFICIENT_CASH,
    ON_INSUFFICIENT_HOLD,
    TrendSpec,
    above_trend,
    apply_trend_filter,
)


def _closes(values: list[str]) -> list[Decimal]:
    return [Decimal(v) for v in values]


def _by_date(values: list[str]) -> dict[date, Decimal]:
    d0 = date(2026, 1, 1)
    return {d0 + timedelta(days=i): Decimal(v) for i, v in enumerate(values)}


# --------------------------------------------------------------- above_trend


def test_above_trend_sma_above():
    # 상승 추세: 마지막 종가가 SMA(3) 위.
    closes = _closes(["10", "11", "12"])
    assert above_trend(closes, TrendSpec(method=METHOD_SMA, lookback=3)) is True


def test_above_trend_sma_below():
    # 하락: 마지막 종가가 SMA(3) 아래.
    closes = _closes(["12", "11", "9"])
    assert above_trend(closes, TrendSpec(method=METHOD_SMA, lookback=3)) is False


def test_above_trend_sma_insufficient():
    closes = _closes(["10", "11"])
    assert above_trend(closes, TrendSpec(method=METHOD_SMA, lookback=3)) is None


def test_above_trend_absolute_momentum_positive():
    # lookback=2: 마지막/2전 − 1 > 0 → 상승.
    closes = _closes(["10", "11", "12"])
    spec = TrendSpec(method=METHOD_ABSOLUTE_MOMENTUM, lookback=2)
    assert above_trend(closes, spec) is True


def test_above_trend_absolute_momentum_negative():
    closes = _closes(["12", "11", "10"])
    spec = TrendSpec(method=METHOD_ABSOLUTE_MOMENTUM, lookback=2)
    assert above_trend(closes, spec) is False


def test_above_trend_absolute_momentum_insufficient():
    closes = _closes(["10", "11"])  # lookback+1=3 필요
    spec = TrendSpec(method=METHOD_ABSOLUTE_MOMENTUM, lookback=2)
    assert above_trend(closes, spec) is None


def test_above_trend_absolute_momentum_nonpositive_past():
    closes = [Decimal("0"), Decimal("5"), Decimal("6")]
    spec = TrendSpec(method=METHOD_ABSOLUTE_MOMENTUM, lookback=2)
    assert above_trend(closes, spec) is None  # 과거가 0 이하 → 측정 불가


# --------------------------------------------------------- spec validation


def test_trend_spec_rejects_bad_method():
    with pytest.raises(ValueError, match="unknown trend method"):
        TrendSpec(method="bogus")


def test_trend_spec_rejects_small_lookback():
    with pytest.raises(ValueError, match="lookback must be"):
        TrendSpec(lookback=1)


def test_trend_spec_rejects_bad_on_insufficient():
    with pytest.raises(ValueError, match="on_insufficient"):
        TrendSpec(on_insufficient="bogus")


# --------------------------------------------------------- apply_trend_filter


def test_filter_drops_below_trend_to_cash():
    weights = {"UP": Decimal("0.5"), "DOWN": Decimal("0.5")}
    closes = {
        "UP": _by_date(["10", "11", "12", "13"]),  # 추세 위
        "DOWN": _by_date(["13", "12", "11", "9"]),  # 추세 아래
    }
    spec = TrendSpec(method=METHOD_SMA, lookback=3)
    filtered, decisions = apply_trend_filter(weights, closes, spec)
    assert filtered == {"UP": Decimal("0.5")}  # DOWN 은 현금으로 빠짐
    # 합이 1 미만(나머지 0.5 는 현금) — 재정규화 안 함.
    assert sum(filtered.values()) == Decimal("0.5")
    states = {d.symbol: d.state for d in decisions}
    assert states == {"UP": "above", "DOWN": "below"}


def test_filter_all_below_goes_all_cash():
    weights = {"A": Decimal("0.5"), "B": Decimal("0.5")}
    closes = {
        "A": _by_date(["13", "12", "11", "9"]),
        "B": _by_date(["20", "18", "15", "10"]),
    }
    spec = TrendSpec(method=METHOD_SMA, lookback=3)
    filtered, _ = apply_trend_filter(weights, closes, spec)
    assert filtered == {}  # 전량 현금(완전 방어)


def test_filter_insufficient_hold_keeps():
    weights = {"NEW": Decimal("1.0")}
    closes = {"NEW": _by_date(["10", "11"])}  # lookback 3 미만
    spec = TrendSpec(method=METHOD_SMA, lookback=3, on_insufficient=ON_INSUFFICIENT_HOLD)
    filtered, decisions = apply_trend_filter(weights, closes, spec)
    assert filtered == {"NEW": Decimal("1.0")}
    assert decisions[0].state == "insufficient" and decisions[0].kept is True


def test_filter_insufficient_cash_drops():
    weights = {"NEW": Decimal("1.0")}
    closes = {"NEW": _by_date(["10", "11"])}
    spec = TrendSpec(method=METHOD_SMA, lookback=3, on_insufficient=ON_INSUFFICIENT_CASH)
    filtered, decisions = apply_trend_filter(weights, closes, spec)
    assert filtered == {}
    assert decisions[0].kept is False


def test_filter_preserves_key_order_deterministic():
    weights = {"C": Decimal("0.3"), "A": Decimal("0.3"), "B": Decimal("0.4")}
    closes = {s: _by_date(["10", "11", "12", "13"]) for s in weights}
    spec = TrendSpec(method=METHOD_SMA, lookback=3)
    a, _ = apply_trend_filter(weights, closes, spec)
    b, _ = apply_trend_filter(weights, closes, spec)
    assert list(a.keys()) == ["C", "A", "B"]  # 입력 순서 보존
    assert a == b  # 결정론


# ------------------------------------------------ target_weights integration


def _ranked(symbols: list[str]) -> list[tuple[str, Decimal]]:
    # 동일 점수(순위 무관) — 선택만 되게.
    return [(s, Decimal("1.0")) for s in symbols]


def test_target_weights_trend_none_is_byte_identical():
    closes = {s: _by_date(["10", "11", "12", "13"]) for s in ("A", "B")}
    base = target_weights(
        ranked_scores=_ranked(["A", "B"]),
        closes_by_symbol=closes,
        weight_scheme="equal",
        top_n=2,
    )
    assert base == {"A": Decimal("0.5"), "B": Decimal("0.5")}  # 합 1.0 그대로


def test_portfolio_config_parses_trend_filter_subtable():
    from auto_invest.config.rules import PortfolioRebalanceConfig

    cfg = PortfolioRebalanceConfig.model_validate(
        {
            "id": "p",
            "universe": ["AAA", "BBB"],
            "weights": {"momentum": "1.0"},
            "top_n": 2,
            "trend_filter": {
                "method": "absolute_momentum",
                "lookback": 120,
                "on_insufficient": "cash",
            },
        }
    )
    assert cfg.trend_filter is not None
    assert cfg.trend_filter.method == "absolute_momentum"
    assert cfg.trend_filter.lookback == 120
    assert cfg.trend_filter.on_insufficient == "cash"


def test_portfolio_config_trend_filter_defaults_off():
    from auto_invest.config.rules import PortfolioRebalanceConfig

    cfg = PortfolioRebalanceConfig.model_validate(
        {"id": "p", "universe": ["AAA", "BBB"], "weights": {"momentum": "1.0"}, "top_n": 2}
    )
    assert cfg.trend_filter is None  # 생략 시 미적용


def test_portfolio_config_trend_filter_rejects_unknown_key():
    import pytest as _pytest

    from auto_invest.config.rules import PortfolioRebalanceConfig

    with _pytest.raises(ValueError, match="extra"):
        PortfolioRebalanceConfig.model_validate(
            {
                "id": "p",
                "universe": ["AAA", "BBB"],
                "weights": {"momentum": "1.0"},
                "top_n": 2,
                "trend_filter": {"method": "sma", "bogus": 1},
            }
        )


def test_target_weights_with_trend_moves_loser_to_cash():
    closes = {
        "A": _by_date(["10", "11", "12", "13"]),  # 추세 위
        "B": _by_date(["13", "12", "11", "9"]),  # 추세 아래
    }
    out = target_weights(
        ranked_scores=_ranked(["A", "B"]),
        closes_by_symbol=closes,
        weight_scheme="equal",
        top_n=2,
        trend=TrendSpec(method=METHOD_SMA, lookback=3),
    )
    assert out == {"A": Decimal("0.5")}  # B 는 현금, 합 0.5(나머지 현금 방어)
