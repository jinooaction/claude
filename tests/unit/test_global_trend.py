"""스펙 047 — 글로벌 분산 추세추종(+금) 단위 테스트.

순수·결정론·미래 누출 0 을 못 박는다. 실데이터(네트워크) 없이 합성 시계열로 *수학*을 검증.
"""

from __future__ import annotations

import math

from auto_invest.analytics.global_trend import (
    GOLD_FLOAT_YEAR,
    _classify_gold,
    align_gold_levels,
    compare_global_trend,
    global_trend_factors,
    gold_total_return_factors,
    parse_gold,
    risk_parity_global_factors,
)
from auto_invest.analytics.risk_managed_beta import LegStats, MonthlyRow


def _rows(prices: list[float], *, div: float = 0.0, rate: float = 0.0) -> list[MonthlyRow]:
    return [
        MonthlyRow(
            date=f"20{1 + i // 12:02d}-{1 + i % 12:02d}-01",
            price=p,
            dividend=div,
            long_rate=rate,
        )
        for i, p in enumerate(prices)
    ]


def _gold_for_rows(rows: list[MonthlyRow], prices: list[float]) -> dict[str, float]:
    """rows 와 1:1 정렬되는 {YYYY-MM: price} 금 매핑."""
    return {r.date[:7]: p for r, p in zip(rows, prices, strict=True)}


# ───────────────────────────── 금 데이터 파싱 ─────────────────────────────


def test_parse_gold_basic():
    csv = "Date,Price\n1971-01,37.500\n1971-02,38.900\n1980-01,675.300\n"
    g = parse_gold(csv)
    assert g["1971-01"] == 37.5
    assert g["1980-01"] == 675.3
    assert len(g) == 3


def test_parse_gold_skips_bad_and_nonpositive():
    csv = "Date,Price\n1971-01,37.5\nbadline\n1971-03,0\n1971-04,-5\n1971-05,40\n"
    g = parse_gold(csv)
    assert set(g) == {"1971-01", "1971-05"}  # 0/음수/불량 행 제외


# ─────────────────────────────── 금 정렬 ───────────────────────────────


def test_align_gold_levels_matches_year_month():
    rows = _rows([10, 11, 12])  # 2001-01, 2001-02, 2001-03
    gold = _gold_for_rows(rows, [100.0, 110.0, 120.0])
    assert align_gold_levels(rows, gold) == [100.0, 110.0, 120.0]


def test_align_gold_levels_carries_forward_missing_month():
    rows = _rows([10, 11, 12])
    # 가운데 달(2001-02) 금 데이터 비어 있음 → 직전 값 캐리.
    gold = {rows[0].date[:7]: 100.0, rows[2].date[:7]: 120.0}
    assert align_gold_levels(rows, gold) == [100.0, 100.0, 120.0]


def test_align_gold_levels_raises_when_no_prior_gold():
    rows = _rows([10, 11])
    gold = {rows[1].date[:7]: 120.0}  # 첫 행 달엔 금 없음
    try:
        align_gold_levels(rows, gold)
    except ValueError as e:
        assert "no gold price" in str(e)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


# ─────────────────────────── 금 총수익 팩터 ───────────────────────────


def test_gold_total_return_factors_pure_price_return():
    # 금은 쿠폰/배당 0 → factor_t = P_t/P_{t-1}. 길이 N-1.
    levels = [100.0, 110.0, 99.0]
    f = gold_total_return_factors(levels)
    assert len(f) == 2
    assert math.isclose(f[0], 1.1)
    assert math.isclose(f[1], 0.9)


# ─────────────────────── 3자산 비교(고정 가중) ───────────────────────


def test_compare_global_trend_structure_and_determinism():
    # 상승 추세 주식 + 완만한 채권금리 + 변동 큰 금.
    prices = [100 + i for i in range(60)]
    rows = _rows(prices, div=2.0, rate=4.0)
    gold = _gold_for_rows(
        rows, [50 + 8 * math.sin(i / 3) + i * 0.3 for i in range(60)]
    )
    gl = align_gold_levels(rows, gold)
    a = compare_global_trend(rows, gl, window=10)
    b = compare_global_trend(rows, gl, window=10)
    assert a.as_dict() == b.as_dict()  # 결정론
    # 다리들이 모두 채워진다.
    assert a.diversified_2asset.n_months == a.diversified_3asset.n_months
    assert a.verdict in ("GOLD_DIVERSIFICATION_EDGE", "NO_GOLD_BENEFIT", "INSUFFICIENT")
    assert a.verdict_rp in (
        "GOLD_DIVERSIFICATION_EDGE", "NO_GOLD_BENEFIT", "INSUFFICIENT"
    )
    # 금 상관이 계산된다(주식·채권 둘 다).
    assert a.gold_corr_equity is not None or a.diversified_3asset.n_months < 2


def test_compare_global_trend_weights_normalized():
    rows = _rows([100 + i for i in range(40)], div=1.0, rate=3.0)
    gl = align_gold_levels(rows, _gold_for_rows(rows, [40 + i for i in range(40)]))
    # 1:1:1 = 1/3 씩, 정규화 후 합 1.
    cmp = compare_global_trend(
        rows, gl, equity_weight=1, bond_weight=1, gold_weight=1
    )
    s = cmp.equity_weight + cmp.bond_weight + cmp.gold_weight
    assert math.isclose(s, 1.0)
    assert math.isclose(cmp.gold_weight, 1 / 3)


# ─────────────────────── 역변동성(리스크 패리티) ───────────────────────


def test_risk_parity_global_factors_length_and_determinism():
    rows = _rows([100 + i for i in range(48)], div=1.0, rate=4.0)
    gl = align_gold_levels(rows, _gold_for_rows(rows, [60 + 5 * (i % 7) for i in range(48)]))
    f1 = risk_parity_global_factors(rows, gl, window=10)
    f2 = risk_parity_global_factors(rows, gl, window=10)
    assert f1 == f2  # 결정론
    assert len(f1) == len(rows) - 1


def test_risk_parity_underweights_high_vol_sleeve():
    """변동성 큰 금이 역변동성 가중에서 더 작은 비중을 받는지(원칙적 사이징)를 *간접* 검증.

    금 다리만 변동성을 매우 크게(롤러코스터) 만들면, 역변동성 3자산의 실현 변동성이 고정
    1/3 균등 3자산보다 낮아야 한다(고변동 자산을 덜 담으니까). 채권 슬리브가 0 변동성으로
    폴백하지 않도록 금리를 *변동*시킨다(아니면 역변동성이 1/3 균등으로 되돌아간다).
    """
    n = 60
    prices = [100.0 + i for i in range(n)]
    rates = [4.0 + 0.5 * math.sin(i / 4) for i in range(n)]  # 변동 금리 → 채권 변동성>0
    rows = [
        MonthlyRow(
            date=f"20{1 + i // 12:02d}-{1 + i % 12:02d}-01",
            price=p,
            dividend=1.0,
            long_rate=rt,
        )
        for i, (p, rt) in enumerate(zip(prices, rates, strict=True))
    ]
    # 금: 큰 진폭의 톱니(고변동).
    gold_prices = [80.0 * (1.5 if i % 2 == 0 else 0.7) + i for i in range(n)]
    gl = align_gold_levels(rows, _gold_for_rows(rows, gold_prices))
    rp = risk_parity_global_factors(rows, gl, window=10)
    eq3 = global_trend_factors(rows, gl, equity_weight=1, bond_weight=1, gold_weight=1)
    assert rp != eq3  # 역변동성이 실제로 1/3 균등과 달라야(폴백 아님)

    def vol(fs: list[float]) -> float:
        rets = [f - 1.0 for f in fs]
        m = sum(rets) / len(rets)
        return (sum((r - m) ** 2 for r in rets) / (len(rets) - 1)) ** 0.5

    assert vol(rp) < vol(eq3)  # 역변동성이 고변동 금을 덜 담아 포트폴리오 변동성↓


# ─────────────────────────── 분류 게이트 로직 ───────────────────────────


def _leg(sharpe: float, calmar: float, dd: float) -> LegStats:
    return LegStats(
        cagr_pct=5.0,
        vol_pct=10.0,
        sharpe=sharpe,
        max_dd_pct=dd,
        calmar=calmar,
        psr_gt0=0.9,
        pct_in_market=1.0,
        n_months=120,
    )


def test_classify_gold_edge_requires_all_three():
    two = _leg(1.50, 0.40, 18.0)
    # 3자산이 샤프·칼마↑ + 낙폭 비악화 → EDGE.
    three_good = _leg(1.60, 0.55, 14.0)
    v, _ = _classify_gold(two, three_good)
    assert v == "GOLD_DIVERSIFICATION_EDGE"


def test_classify_gold_no_benefit_when_drawdown_worse():
    two = _leg(1.50, 0.40, 7.0)
    # 샤프·칼마는 올라도 낙폭이 악화하면 NO_BENEFIT(자본 방어 우선).
    three = _leg(1.70, 0.50, 10.0)
    v, reason = _classify_gold(two, three)
    assert v == "NO_GOLD_BENEFIT"
    assert "낙폭 악화" in reason


def test_classify_gold_insufficient_when_calmar_none():
    two = _leg(1.5, 0.4, 10.0)
    none_calmar = LegStats(5, 10, 1.6, 0.0, None, 0.9, 1.0, 120)
    v, _ = _classify_gold(two, none_calmar)
    assert v == "INSUFFICIENT"


# ─────────────────────────────── 상수 ───────────────────────────────


def test_gold_float_year_is_bretton_woods():
    assert GOLD_FLOAT_YEAR == 1971


# ─────────────────── 거래비용 반영 (cost_bps — 스펙 044×047 후속) ───────────────────


def _switchy_3asset(n: int = 48):
    prices: list[float] = []
    p = 100.0
    for i in range(n):
        phase = (i // 8) % 2
        p *= 1.04 if phase == 0 else 0.97
        prices.append(p)
    rows = _rows(prices, div=0.0, rate=4.0)
    gold_prices = [50.0 * (1.0 + 0.003 * i + 0.04 * ((i % 6) - 3)) for i in range(n)]
    gold = align_gold_levels(rows, _gold_for_rows(rows, gold_prices))
    return rows, gold


def _terminal(factors: list[float]) -> float:
    out = 1.0
    for f in factors:
        out *= f
    return out


def test_cost_bps_zero_matches_no_cost_default_global() -> None:
    rows, gold = _switchy_3asset()
    assert global_trend_factors(rows, gold, window=10) == global_trend_factors(
        rows, gold, window=10, cost_bps=0.0
    )
    assert risk_parity_global_factors(rows, gold, window=10) == risk_parity_global_factors(
        rows, gold, window=10, cost_bps=0.0
    )


def test_cost_bps_positive_reduces_terminal_growth_global() -> None:
    # 고정가중 3자산은 가중 되먹임이 없어 비용>0 이 최종 복리를 직접 낮춘다.
    rows, gold = _switchy_3asset()
    free = _terminal(global_trend_factors(rows, gold, window=10, cost_bps=0.0))
    costed = _terminal(global_trend_factors(rows, gold, window=10, cost_bps=20.0))
    assert costed < free


def test_cost_bps_affects_risk_parity_global_output() -> None:
    # 역변동성 3자산은 비용이 가중치로 되먹임 → 합성에선 방향 불확정, *효과 있음*만 확정.
    rows, gold = _switchy_3asset()
    free = risk_parity_global_factors(rows, gold, window=10, cost_bps=0.0)
    costed = risk_parity_global_factors(rows, gold, window=10, cost_bps=20.0)
    assert costed != free
