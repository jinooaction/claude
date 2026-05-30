"""스펙 025 — 다요인 합성 알파 점수 필터 테스트.

SC-01: 모멘텀 가중치만 → 모멘텀 높은 종목이 상위.
SC-02: 모멘텀+저변동성 합성 → 매끄러운(저변동성) 종목이 변동성 큰 1위 종목을 추월
       (합성의 핵심 동작 — 여러 면에서 두루 좋은 종목 선호).
SC-03: z-점수 성질(평균 0, 동일값이면 전부 0).
SC-04: 활성 팩터 데이터 부족 심볼은 센티넬로 맨 뒤.
SC-05: composite_filter=None → 라우터 경로 byte 동일(PAPER_FILLED).
SC-06: top_n 밖 심볼 → SKIPPED_BY_COMPOSITE.
SC-08: KNOWN_FACTORS == KNOWN_COMPOSITE_FACTORS 동기화.
SC-09: 알 수 없는 팩터 / 전부 0 가중치 → 검증 오류.
SC-10: 결정론 — 같은 입력이면 같은 순위.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import (
    KNOWN_COMPOSITE_FACTORS,
    Action,
    CompositeFactorFilter,
    TimeTrigger,
    TradingRule,
)
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.order_router import OrderRouter
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import db as _db_mod
from auto_invest.strategy.factors import KNOWN_FACTORS, composite_scores, zscore

# =========================================================================== #
# helpers                                                                      #
# =========================================================================== #


def _open_db(path: Path) -> sqlite3.Connection:
    conn = _db_mod.get_connection(path)
    _db_mod.migrate(conn)
    return conn


def _make_bars(symbol: str, closes: list[float]) -> list[PriceBar]:
    bars = []
    base = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)
    for i, c in enumerate(closes):
        ts = (base + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        p = Decimal(str(c))
        bars.append(
            PriceBar(
                symbol=symbol,
                timeframe="1d",
                bar_open_utc=ts,
                open_usd=p,
                high_usd=p,
                low_usd=p,
                close_usd=p,
                volume=1000,
            )
        )
    return bars


def _insert_bars(conn: sqlite3.Connection, bars: list[PriceBar]) -> None:
    for b in bars:
        insert_bar(conn, b)


def _smooth(start: float, step: float, n: int) -> list[float]:
    return [start + i * step for i in range(n)]


def _jagged(start: float, up: float, down: float, n: int) -> list[float]:
    prices = [start]
    for i in range(1, n):
        prices.append(prices[-1] + (up if i % 2 == 1 else -down))
    return prices


def _make_rule(
    symbol: str, *, composite_filter: CompositeFactorFilter | None = None
) -> TradingRule:
    return TradingRule(
        id=f"rule-{symbol.lower()}",
        symbol=symbol,
        stage=StrategyStage.FULL_LIVE,
        priority=1,
        trigger=TimeTrigger(at_time="14:30", cooldown_seconds=0),
        action=Action(side=Side.BUY, order_type=OrderType.MARKET, qty=10, limit_price="100"),
        composite_filter=composite_filter,
    )


def _make_router(conn: sqlite3.Connection, *symbols: str, tmp_path: Path) -> OrderRouter:
    return OrderRouter(
        conn=conn,
        broker=MagicMock(),
        access_token="x",
        app_key="x",
        app_secret="x",
        account_no="x",
        whitelist=Whitelist(symbols=list(symbols), order_types=["MARKET"], accounts=["x"]),
        caps=SizingCaps(
            per_trade_pct=Decimal("10"),
            per_symbol_pct=Decimal("20"),
            global_exposure_pct=Decimal("80"),
            canary_capital_pct=Decimal("5"),
            canary_min_duration_days=10,
            canary_acceptance_drawdown_pct=Decimal("3"),
        ),
        halt_path=tmp_path / "halt",
        paper_mode=True,
    )


async def _submit(router: OrderRouter, rule: TradingRule):
    return await router.submit_order(
        rule=rule,
        quote_price_usd=Decimal("100"),
        total_capital_usd=Decimal("100000"),
        current_symbol_exposure_usd=Decimal("0"),
        current_global_exposure_usd=Decimal("0"),
    )


# =========================================================================== #
# SC-08: 팩터 이름 동기화                                                       #
# =========================================================================== #


def test_sc08_known_factors_in_sync():
    assert KNOWN_FACTORS == KNOWN_COMPOSITE_FACTORS


# =========================================================================== #
# SC-03: z-점수 성질                                                            #
# =========================================================================== #


def test_sc03_zscore_mean_zero():
    z = zscore({"A": Decimal("1"), "B": Decimal("2"), "C": Decimal("3")})
    total = sum(z.values())
    assert abs(total) < Decimal("0.00001")
    # B is the mean → z ≈ 0; A < mean < C.
    assert z["A"] < 0 < z["C"]


def test_sc03_zscore_equal_values_all_zero():
    z = zscore({"A": Decimal("5"), "B": Decimal("5"), "C": Decimal("5")})
    assert all(v == Decimal("0") for v in z.values())


# =========================================================================== #
# SC-01: 모멘텀 단일 가중치 → 모멘텀 순                                         #
# =========================================================================== #


def test_sc01_momentum_only_ranks_by_momentum():
    universe = {
        "AAA": _make_bars("AAA", [100, 110]),  # +10%
        "BBB": _make_bars("BBB", [100, 105]),  # +5%
        "CCC": _make_bars("CCC", [100, 102]),  # +2%
    }
    ranked = composite_scores(universe, weights={"momentum": Decimal(1)}, momentum_period=1)
    assert [s for s, _ in ranked] == ["AAA", "BBB", "CCC"]


# =========================================================================== #
# SC-02: 합성이 단일 팩터 순위를 바꾼다 (핵심 동작)                             #
# =========================================================================== #


def test_sc02_composite_blends_momentum_and_low_vol():
    n = 31
    # X: 매끄러운 상승(중간 모멘텀, 매우 낮은 변동성).
    x_closes = _smooth(100.0, 1.0, n)  # 100 → 130, +30%
    # Y: 급등락하며 강하게 상승(최고 모멘텀, 매우 높은 변동성).
    y_closes = _jagged(100.0, 12.0, 8.0, n)  # net +60%, 큰 변동성
    # Z: 거의 평탄(최저 모멘텀, 낮은 변동성).
    z_closes = _smooth(100.0, 0.3, n)  # 100 → 109, +9%
    universe = {
        "X": _make_bars("X", x_closes),
        "Y": _make_bars("Y", y_closes),
        "Z": _make_bars("Z", z_closes),
    }

    # 모멘텀만: Y(+60%)가 1위.
    mom_only = composite_scores(
        universe, weights={"momentum": Decimal(1)}, lookback_bars=30, momentum_period=30
    )
    assert mom_only[0][0] == "Y"
    assert mom_only[-1][0] == "Z"

    # 모멘텀 + 저변동성: 매끄러운 X가 변동성 큰 Y를 추월해 1위.
    blend = composite_scores(
        universe,
        weights={"momentum": Decimal(1), "low_volatility": Decimal(1)},
        lookback_bars=30,
        momentum_period=30,
    )
    assert blend[0][0] == "X"


# =========================================================================== #
# SC-04: 활성 팩터 데이터 부족 심볼은 센티넬로 맨 뒤                            #
# =========================================================================== #


def test_sc04_insufficient_data_sentinel_last():
    universe = {
        "RICH": _make_bars("RICH", [100, 110]),  # 2 bars, momentum period=1 OK
        "POOR": _make_bars("POOR", [100]),        # 1 bar → momentum 불가
    }
    ranked = composite_scores(universe, weights={"momentum": Decimal(1)}, momentum_period=1)
    assert ranked[0][0] == "RICH"
    assert ranked[-1] == ("POOR", Decimal("-Inf"))


# =========================================================================== #
# SC-10: 결정론                                                                 #
# =========================================================================== #


def test_sc10_deterministic():
    universe = {
        "A": _make_bars("A", _smooth(100.0, 1.0, 31)),
        "B": _make_bars("B", _jagged(100.0, 5.0, 3.0, 31)),
        "C": _make_bars("C", _smooth(100.0, 0.5, 31)),
    }
    w = {"momentum": Decimal(1), "low_volatility": Decimal("0.5"), "mean_reversion": Decimal("0.3")}
    r1 = composite_scores(universe, weights=w, lookback_bars=30, momentum_period=20)
    r2 = composite_scores(universe, weights=w, lookback_bars=30, momentum_period=20)
    assert r1 == r2


# =========================================================================== #
# SC-09: 가중치 검증                                                            #
# =========================================================================== #


def test_sc09_unknown_factor_rejected():
    with pytest.raises(ValidationError):
        CompositeFactorFilter(
            universe=("A", "B"), weights={"bogus": Decimal(1)}, top_n=1
        )


def test_sc09_all_zero_weights_rejected():
    with pytest.raises(ValidationError):
        CompositeFactorFilter(
            universe=("A", "B"), weights={"momentum": Decimal(0)}, top_n=1
        )


def test_exactly_one_top_required():
    with pytest.raises(ValidationError):
        CompositeFactorFilter(universe=("A", "B"), weights={"momentum": Decimal(1)})
    with pytest.raises(ValidationError):
        CompositeFactorFilter(
            universe=("A", "B"), weights={"momentum": Decimal(1)}, top_n=1, top_pct=50.0
        )


# =========================================================================== #
# SC-06: 라우터 통합 — top_n 밖 심볼 차단                                       #
# =========================================================================== #


@pytest.mark.asyncio
async def test_sc06_router_top_passes_bottom_skipped(tmp_path):
    conn = _open_db(tmp_path / "db.sqlite3")
    # 21 bars (momentum_period=20 기본) — AAA 최고, CCC 최저 모멘텀.
    _insert_bars(conn, _make_bars("AAA", _smooth(100.0, 2.0, 21)))  # +40%
    _insert_bars(conn, _make_bars("BBB", _smooth(100.0, 1.0, 21)))  # +20%
    _insert_bars(conn, _make_bars("CCC", _smooth(100.0, 0.2, 21)))  # +4%

    cf = CompositeFactorFilter(
        universe=("AAA", "BBB", "CCC"), weights={"momentum": Decimal(1)}, top_n=1
    )
    router = _make_router(conn, "AAA", "BBB", "CCC", tmp_path=tmp_path)

    top = await _submit(router, _make_rule("AAA", composite_filter=cf))
    assert top.state == "PAPER_FILLED", top

    bottom = await _submit(router, _make_rule("CCC", composite_filter=cf))
    assert bottom.state == "SKIPPED_BY_COMPOSITE"
    assert bottom.reason == "not_in_top_composite"


# =========================================================================== #
# SC-05: composite_filter=None → 기존 경로 동일                                 #
# =========================================================================== #


@pytest.mark.asyncio
async def test_sc05_no_filter_passthrough(tmp_path):
    conn = _open_db(tmp_path / "db.sqlite3")
    router = _make_router(conn, "SPY", tmp_path=tmp_path)
    outcome = await _submit(router, _make_rule("SPY"))  # no composite_filter
    assert outcome.state == "PAPER_FILLED"
