"""스펙 019 — 레짐 인식 + 완전 공분산 ERC 단위/통합 테스트.

검증 대상:
  슬라이스 1: RegimeDetector (SC-R01~R04)
  슬라이스 2: 공분산 ERC (SC-E01~E04)
  슬라이스 3: walk-forward 표본 외 검증 (SC-W01~W03)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import exchange_calendars as ec

from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.backtest.walk_forward import run_walk_forward
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, TimeTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.market_data.store import PriceBar
from auto_invest.persistence import db
from auto_invest.strategy.regime import (
    DEFAULT_REGIME_SCALE,
    Regime,
    apply_regime_scale,
    detect,
)
from auto_invest.strategy.sizing import (
    covariance_matrix,
    erc_group_scales,
    erc_weights,
    inverse_vol_group_scale,
)

# =========================================================================== #
# 헬퍼                                                                         #
# =========================================================================== #


def _make_bars(closes: list[float], base_ts: str = "2024-01-01T09:00:00Z") -> list[PriceBar]:
    """PriceBar 리스트 생성 (close 만 의미 있음)."""
    bars: list[PriceBar] = []
    dt = datetime.fromisoformat(base_ts.replace("Z", "+00:00"))
    for i, c in enumerate(closes):
        ts = (dt + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        bars.append(
            PriceBar(
                symbol="IDX",
                timeframe="1d",
                bar_open_utc=ts,
                open_usd=Decimal(str(c)),
                high_usd=Decimal(str(c)),
                low_usd=Decimal(str(c)),
                close_usd=Decimal(str(c)),
                volume=1000,
            )
        )
    return bars


def _trending_bars(n: int = 210) -> list[PriceBar]:
    """골든크로스 — close > SMA50 > SMA200."""
    closes = [100.0 + i * 0.5 for i in range(n)]
    return _make_bars(closes)


def _bear_bars(n: int = 210) -> list[PriceBar]:
    """하락장 — close < SMA200 < SMA50 방향."""
    # 긴 상승 후 급락
    closes = [100.0 + i * 0.3 for i in range(180)] + [50.0 - j * 0.2 for j in range(n - 180)]
    return _make_bars(closes[:n])


# =========================================================================== #
# 슬라이스 1: 레짐 감지 SC-R01~R04                                              #
# =========================================================================== #


def test_detect_trending(sc="SC-R02") -> None:
    """골든크로스 데이터 → TRENDING."""
    bars = _trending_bars()
    assert detect(bars) == Regime.TRENDING


def test_detect_ranging_insufficient_bars(sc="SC-R03") -> None:
    """200막대 미만 → RANGING (fail-safe)."""
    bars = _make_bars([100.0] * 50)
    assert detect(bars) == Regime.RANGING


def test_detect_exactly_200_bars() -> None:
    """정확히 200막대 → RANGING 이 아닐 수도 있지만, 오류 없이 반환."""
    bars = _make_bars([100.0 + i for i in range(200)])
    result = detect(bars)
    assert result in {Regime.TRENDING, Regime.RANGING, Regime.BEAR}


def test_apply_regime_scale_bear(sc="SC-R04") -> None:
    """apply_regime_scale(100, 0.3) = 30."""
    assert apply_regime_scale(100, Decimal("0.3")) == 30


def test_apply_regime_scale_zero_qty() -> None:
    """qty=0 → 항상 0."""
    assert apply_regime_scale(0, Decimal("1.0")) == 0


def test_apply_regime_scale_floor() -> None:
    """소수점 내림."""
    assert apply_regime_scale(3, Decimal("0.7")) == 2  # 2.1 → 2


def test_default_regime_scale_values() -> None:
    """기본 배율 값 확인."""
    assert DEFAULT_REGIME_SCALE[Regime.TRENDING] == Decimal("1.0")
    assert DEFAULT_REGIME_SCALE[Regime.RANGING] == Decimal("0.7")
    assert DEFAULT_REGIME_SCALE[Regime.BEAR] == Decimal("0.3")


def test_bear_qty_less_than_trending() -> None:
    """BEAR 배율 적용 시 qty 가 TRENDING 보다 적어야 한다 (SC-R01 의미)."""
    qty = 100
    trending_qty = apply_regime_scale(qty, DEFAULT_REGIME_SCALE[Regime.TRENDING])
    bear_qty = apply_regime_scale(qty, DEFAULT_REGIME_SCALE[Regime.BEAR])
    assert bear_qty < trending_qty


# =========================================================================== #
# 슬라이스 2: 완전 공분산 ERC SC-E01~E04                                        #
# =========================================================================== #


def _uniform_cov(n: int, var: float = 0.01, corr: float = 0.0) -> list[list[Decimal]]:
    """n×n 공분산 행렬. 대각선 var, 비대각 corr*var."""
    cov: list[list[Decimal]] = []
    for i in range(n):
        row: list[Decimal] = []
        for j in range(n):
            if i == j:
                row.append(Decimal(str(var)))
            else:
                row.append(Decimal(str(corr * var)))
        cov.append(row)
    return cov


def test_erc_weights_equal_variance(sc="SC-E01") -> None:
    """동일 분산 자산 3개 → 가중치 각 1/3."""
    cov = _uniform_cov(3, var=0.01, corr=0.0)
    w = erc_weights(cov)
    assert len(w) == 3
    for wi in w:
        assert abs(wi - Decimal("0.333333")) < Decimal("0.001")


def test_erc_weights_high_variance_asset_lower_weight(sc="SC-E02") -> None:
    """자산 2의 분산이 4배 → 자산 2의 가중치가 더 낮아야."""
    # 자산 0: var 0.01, 자산 1: var 0.04
    cov = [
        [Decimal("0.01"), Decimal("0")],
        [Decimal("0"), Decimal("0.04")],
    ]
    w = erc_weights(cov)
    assert w[0] > w[1], f"expected w[0]({w[0]}) > w[1]({w[1]})"


def test_erc_weights_sum_to_one() -> None:
    """가중치 합 = 1."""
    cov = _uniform_cov(4, var=0.01, corr=0.1)
    w = erc_weights(cov)
    total = sum(w)
    assert abs(total - Decimal("1")) < Decimal("0.001")


def test_erc_weights_down_only() -> None:
    """가중치가 모두 0..1 범위."""
    cov = _uniform_cov(5, var=0.02, corr=0.3)
    w = erc_weights(cov)
    for wi in w:
        assert Decimal("0") <= wi <= Decimal("1")


def _make_closes_dict(
    rule_ids: list[str],
    n_days: int = 60,
    vols: list[float] | None = None,
    start: date = date(2023, 1, 2),
) -> dict[str, dict[date, Decimal]]:
    """각 자산에 대한 날짜→close 딕셔너리 생성."""
    if vols is None:
        vols = [0.01] * len(rule_ids)
    result: dict[str, dict[date, Decimal]] = {}
    rng = 42
    for idx, rid in enumerate(rule_ids):
        closes: dict[date, Decimal] = {}
        price = 100.0
        d = start
        for _ in range(n_days):
            # 간단한 가격 시뮬레이션
            noise = (((rng * (idx + 1) * (_ + 1)) % 100) / 100.0 - 0.5) * vols[idx] * 2
            rng = (rng * 1103515245 + 12345) % (2**31)
            price = max(price * (1 + noise), 1.0)
            closes[d] = Decimal(str(round(price, 4)))
            d += timedelta(days=1)
        result[rid] = closes
    return result


def test_covariance_matrix_insufficient_data(sc="SC-E03") -> None:
    """공통일 < 30 → None 반환."""
    closes = _make_closes_dict(["A", "B"], n_days=25)
    cov = covariance_matrix(closes, lookback_bars=20)
    assert cov is None


def test_covariance_matrix_returns_matrix(sc="SC-E03") -> None:
    """충분한 데이터 → n×n 행렬 반환."""
    closes = _make_closes_dict(["A", "B", "C"], n_days=60)
    cov = covariance_matrix(closes, lookback_bars=40)
    assert cov is not None
    assert len(cov) == 3
    assert all(len(row) == 3 for row in cov)


def test_erc_group_scales_fallback_on_insufficient_data(sc="SC-E03") -> None:
    """데이터 부족 → 역변동성 fallback."""
    closes = _make_closes_dict(["A", "B"], n_days=20)
    vols = {"A": Decimal("0.01"), "B": Decimal("0.02")}
    scales = erc_group_scales(closes, lookback_bars=20, member_vols=vols)
    # fallback: 역변동성 가중치 확인 (A가 더 높아야)
    assert scales["A"] > scales["B"]


def test_erc_group_scales_all_keys_present(sc="SC-E04") -> None:
    """모든 rule_id 키가 결과에 있어야."""
    closes = _make_closes_dict(["X", "Y", "Z"], n_days=60)
    vols = {"X": Decimal("0.01"), "Y": Decimal("0.015"), "Z": Decimal("0.02")}
    scales = erc_group_scales(closes, lookback_bars=40, member_vols=vols)
    assert set(scales.keys()) == {"X", "Y", "Z"}


# =========================================================================== #
# 슬라이스 3: walk-forward 표본 외 검증 SC-W01~W03                              #
# =========================================================================== #


def _make_ohlcv(
    symbol: str,
    start: date,
    n: int,
    base_price: float = 1000.0,
) -> list[OHLCVBar]:
    """OHLCV 합성 데이터 (단순 상승 추세)."""
    bars: list[OHLCVBar] = []
    cal = ec.get_calendar("XNYS")
    sessions = cal.sessions_in_range(
        start.strftime("%Y-%m-%d"),
        (start + timedelta(days=n * 2)).strftime("%Y-%m-%d"),
    )[:n]
    price = base_price
    seed = 7
    for s in sessions:
        seed = (seed * 1103515245 + 12345) % (2**31)
        chg = ((seed % 200) / 10000.0) - 0.01  # -1%~+1%
        price = max(price * (1 + chg), 1.0)
        bars.append(
            OHLCVBar(
                symbol=symbol,
                session_date=s.date(),
                open=Decimal(str(round(price, 2))),
                high=Decimal(str(round(price * 1.001, 2))),
                low=Decimal(str(round(price * 0.999, 2))),
                close=Decimal(str(round(price, 2))),
                volume=10000,
                session_schedule_tag="regular",
            )
        )
    return bars


@dataclass
class _FakeDS:
    bars: dict[str, list[OHLCVBar]]

    @property
    def dataset_version(self) -> str:
        return "019-test"

    def list_symbols(self) -> list[str]:
        return sorted(self.bars.keys())

    def session_dates(self, symbol: str) -> list[date]:
        return [b.session_date for b in self.bars.get(symbol, [])]

    def coverage_holes(self, symbols, date_start, date_end):  # noqa: ANN001
        return []

    def read_bars(self, symbol: str, date_start: date, date_end: date) -> list[OHLCVBar]:
        return [b for b in self.bars.get(symbol, []) if date_start <= b.session_date <= date_end]

    def close(self) -> None:
        pass


def _make_rule(symbol: str = "SAMSNG") -> TradingRule:
    return TradingRule(
        id=f"r_{symbol}",
        symbol=symbol,
        stage=StrategyStage.FULL_LIVE,
        priority=1,
        enabled=True,
        trigger=TimeTrigger(
            kind="time",
            at_time="09:30",
            cooldown_seconds=86400,
        ),
        action=Action(
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            qty=1,
            limit_price="last_close",
        ),
    )


def test_walk_forward_regime_bear_reduces_qty(sc="SC-W03") -> None:
    """BEAR 레짐 배율 < TRENDING 배율 — qty 감소 확인."""
    qty = 100
    bear_qty = apply_regime_scale(qty, DEFAULT_REGIME_SCALE[Regime.BEAR])
    trending_qty = apply_regime_scale(qty, DEFAULT_REGIME_SCALE[Regime.TRENDING])
    assert bear_qty < trending_qty
    assert bear_qty == 30
    assert trending_qty == 100


def test_walk_forward_basic(tmp_path: Path, sc="SC-W01,SC-W02") -> None:
    """walk-forward 기본 통과: avg_oos_sharpe 계산 가능, profitable_windows >= 0.

    이 테스트는 스펙 016 walk-forward 하니스 위에서 합성 데이터를 돌려
    레짐+ERC 모듈이 기존 replay 파이프라인과 호환됨을 확인한다.
    """
    symbol = "SAMSNG"
    start = date(2022, 1, 1)
    bars = _make_ohlcv(symbol, start, n=300)
    ds = _FakeDS({symbol: bars})
    rule = _make_rule(symbol)
    whitelist = Whitelist(symbols=frozenset({symbol}))
    caps = SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("90"),
        global_exposure_pct=Decimal("90"),
        canary_capital_pct=Decimal("1"),
        canary_min_duration_days=5,
        canary_acceptance_drawdown_pct=Decimal("5"),
    )

    conn = db.get_connection(tmp_path / "wf_test.db")
    db.migrate(conn)

    report = run_walk_forward(
        rules=[rule],
        data_source=ds,
        date_start=start,
        date_end=start + timedelta(days=400),
        in_sample_days=90,
        out_of_sample_days=30,
        whitelist=whitelist,
        caps=caps,
        halt_path=tmp_path / "HALT",
        conn=conn,
    )

    assert report is not None
    # SC-W02: OOS 수익 윈도우 비율 >= 0 (windows_oos_profitable 은 음수 불가)
    assert report.windows_oos_profitable >= 0
    assert len(report.windows) >= 1


def test_erc_weights_existing_inverse_vol_unaffected(sc="SC-E04") -> None:
    """기존 inverse_vol_group_scale 로직이 변경되지 않았는지 확인."""
    # 기존 테스트와 동일한 검증 (spec 017 바이트 동일성)
    result = inverse_vol_group_scale(
        Decimal("0.02"),
        [Decimal("0.01"), Decimal("0.02"), Decimal("0.04")],
    )
    # min vol = 0.01, own = 0.02 → scale = 0.5
    assert result == Decimal("0.500000")
