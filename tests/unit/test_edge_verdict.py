"""Spec 035 — forward 엣지 자동 판정(순수 로직) 테스트.

판정 엔진은 NAV 자산곡선을 받아 단순 보유 벤치마크와 비교하고 디플레이티드/확률적
샤프로 우연·과적합을 처벌한다. 여기서는 합성 곡선으로 세 판정(EDGE_CONFIRMED /
NO_EDGE / INSUFFICIENT_DATA)과 벤치마크 빌더·결정론을 검증한다.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from auto_invest.portfolio.edge_verdict import (
    ABSOLUTE_RETURN_PSR_METHOD,
    EDGE_CONFIRMED,
    INSUFFICIENT_DATA,
    NO_EDGE,
    PAIRED_ACTIVE_RETURN_PSR_METHOD,
    calmar_ratio,
    daily_returns_from_curve,
    equal_weight_buy_hold_curve,
    forward_edge_verdict,
)


def _curve_from_returns(start: Decimal, rets: list[Decimal]) -> list[Decimal]:
    """수익률 목록을 복리로 적용해 자산곡선을 만든다."""
    curve = [start]
    for r in rets:
        curve.append(curve[-1] * (Decimal("1") + r))
    return curve


def _alternating(mean: str, amp: str, n: int) -> list[Decimal]:
    """평균 mean, ±amp 로 진동하는 수익률 — 분산>0 이지만 평균/표준편차가 큰 트랙."""
    m = Decimal(mean)
    a = Decimal(amp)
    return [m + (a if i % 2 == 0 else -a) for i in range(n)]


# --------------------------------------------------------------- daily returns


def test_daily_returns_basic():
    curve = [Decimal("100"), Decimal("110"), Decimal("121")]
    rets = daily_returns_from_curve(curve)
    assert rets == [Decimal("0.1"), Decimal("0.1")]


def test_daily_returns_skips_nonpositive_prev():
    curve = [Decimal("0"), Decimal("100"), Decimal("110")]
    # 첫 구간은 직전값 0 이라 건너뛴다.
    assert daily_returns_from_curve(curve) == [Decimal("0.1")]


def test_daily_returns_too_short():
    assert daily_returns_from_curve([Decimal("100")]) == []
    assert daily_returns_from_curve([]) == []


# --------------------------------------------------------- benchmark builder


def test_equal_weight_buy_hold_curve_two_symbols():
    dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
    bars = {
        "AAA": [
            (date(2026, 1, 1), Decimal("100")),
            (date(2026, 1, 2), Decimal("110")),
            (date(2026, 1, 3), Decimal("120")),
        ],
        "BBB": [
            (date(2026, 1, 1), Decimal("50")),
            (date(2026, 1, 2), Decimal("50")),
            (date(2026, 1, 3), Decimal("55")),
        ],
    }
    curve = equal_weight_buy_hold_curve(dates, bars, capital=Decimal("100000"))
    assert curve is not None
    assert len(curve) == 3
    # 각 종목에 $50k. AAA: 500주, BBB: 1000주. 첫날 = 정확히 자본.
    assert curve[0] == Decimal("100000")
    # 둘째날 AAA +10 → +$5,000. BBB 무변동. 총 $105,000.
    assert curve[1] == Decimal("105000")


def test_equal_weight_buy_hold_curve_missing_first_price_returns_none():
    dates = [date(2026, 1, 1), date(2026, 1, 2)]
    bars = {"AAA": [(date(2026, 1, 2), Decimal("100"))]}  # 첫날 가격 없음
    assert equal_weight_buy_hold_curve(dates, bars) is None


def test_equal_weight_buy_hold_curve_carries_last_price():
    # 둘째날 바가 없으면 직전 종가를 들고 간다(0 으로 떨어지지 않음).
    dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
    bars = {
        "AAA": [
            (date(2026, 1, 1), Decimal("100")),
            (date(2026, 1, 3), Decimal("120")),
        ]
    }
    curve = equal_weight_buy_hold_curve(dates, bars, capital=Decimal("10000"))
    assert curve is not None
    assert curve[0] == curve[1]  # 둘째날은 첫날 종가 유지


# ------------------------------------------------------------------- verdicts


def test_insufficient_data_too_few_points():
    curve = _curve_from_returns(Decimal("10000"), _alternating("0.005", "0.001", 5))
    v = forward_edge_verdict(curve, None, min_obs=20)
    assert v.verdict == INSUFFICIENT_DATA
    assert v.n_obs == 5


def test_insufficient_data_zero_variance():
    # 완전히 평평한 곡선 → 수익률 0, 분산 0 → 통계 불가 → 보류.
    flat = [Decimal("10000")] * 30
    v = forward_edge_verdict(flat, None, min_obs=20)
    assert v.verdict == INSUFFICIENT_DATA


def test_edge_confirmed_beats_benchmark():
    # 전략: 평균 큼·진동 작음 → 샤프 매우 높음. 벤치: 평균 작음·진동 큼 → 샤프 낮음.
    strat = _curve_from_returns(
        Decimal("10000"), _alternating("0.006", "0.001", 40)
    )
    bench = _curve_from_returns(
        Decimal("10000"), _alternating("0.001", "0.004", 40)
    )
    v = forward_edge_verdict(strat, bench, min_obs=20)
    assert v.verdict == EDGE_CONFIRMED
    assert v.has_benchmark is True
    assert v.excess_return_pct is not None and v.excess_return_pct > 0
    assert v.strategy_sharpe_annual > v.benchmark_sharpe_annual
    assert v.psr_vs_benchmark is not None and v.psr_vs_benchmark >= Decimal("0.95")
    assert v.significance_method == PAIRED_ACTIVE_RETURN_PSR_METHOD
    assert v.active_information_ratio_annual is not None


def test_paired_psr_is_invariant_to_common_market_shocks():
    active = _alternating("0.002", "0.003", 48)
    quiet_benchmark = _alternating("0.0004", "0.004", 48)
    volatile_benchmark = _alternating("0.0004", "0.025", 48)
    quiet_strategy = [b + a for b, a in zip(quiet_benchmark, active, strict=True)]
    volatile_strategy = [
        b + a for b, a in zip(volatile_benchmark, active, strict=True)
    ]

    quiet = forward_edge_verdict(
        _curve_from_returns(Decimal("10000"), quiet_strategy),
        _curve_from_returns(Decimal("10000"), quiet_benchmark),
        min_obs=20,
    )
    volatile = forward_edge_verdict(
        _curve_from_returns(Decimal("10000"), volatile_strategy),
        _curve_from_returns(Decimal("10000"), volatile_benchmark),
        min_obs=20,
    )

    assert quiet.psr_vs_benchmark == volatile.psr_vs_benchmark
    assert (
        quiet.active_information_ratio_annual
        == volatile.active_information_ratio_annual
    )


def test_paired_verdict_fails_closed_on_misaligned_curves():
    strat = _curve_from_returns(
        Decimal("10000"), _alternating("0.004", "0.002", 40)
    )
    bench = _curve_from_returns(
        Decimal("10000"), _alternating("0.001", "0.002", 39)
    )

    verdict = forward_edge_verdict(strat, bench, min_obs=20)

    assert verdict.verdict == INSUFFICIENT_DATA
    assert "길이" in verdict.reason
    assert verdict.significance_method == PAIRED_ACTIVE_RETURN_PSR_METHOD


def test_paired_verdict_fails_closed_on_zero_active_variance():
    bench_rets = _alternating("0.0005", "0.01", 40)
    strat_rets = [value + Decimal("0.001") for value in bench_rets]

    verdict = forward_edge_verdict(
        _curve_from_returns(Decimal("10000"), strat_rets),
        _curve_from_returns(Decimal("10000"), bench_rets),
        min_obs=20,
    )

    assert verdict.verdict == INSUFFICIENT_DATA
    assert verdict.active_information_ratio_annual is None
    assert "능동 수익률" in verdict.reason


def test_no_edge_loses_to_benchmark():
    # 전략이 벤치마크보다 못함 → 단순 보유 못 이김 → NO_EDGE.
    strat = _curve_from_returns(
        Decimal("10000"), _alternating("0.001", "0.004", 40)
    )
    bench = _curve_from_returns(
        Decimal("10000"), _alternating("0.006", "0.001", 40)
    )
    v = forward_edge_verdict(strat, bench, min_obs=20)
    assert v.verdict == NO_EDGE


def test_no_edge_high_noise_not_significant():
    # 평균≈0, 큰 잡음 → 양·음 반반. 우연과 구별 안 됨 → NO_EDGE(벤치 없음 경로).
    noisy = _curve_from_returns(Decimal("10000"), _alternating("0.0", "0.02", 40))
    v = forward_edge_verdict(noisy, None, min_obs=20)
    assert v.verdict == NO_EDGE


def test_num_trials_deflation_blocks_edge():
    # 벤치를 이기고 PSR 도 통과하지만, 시도 횟수가 많고 시도 샤프 분산이 크면
    # DSR 이 깎여 EDGE 가 막혀야 한다(과적합 처벌, 스펙 027).
    strat = _curve_from_returns(
        Decimal("10000"), _alternating("0.006", "0.001", 40)
    )
    bench = _curve_from_returns(
        Decimal("10000"), _alternating("0.001", "0.004", 40)
    )
    v = forward_edge_verdict(
        strat,
        bench,
        min_obs=20,
        num_trials=500,
        trial_sharpe_std_annual=Decimal("40"),
    )
    # DSR 이 임계치 아래로 깎이면 NO_EDGE. (보정이 실제로 작동하는지 확인)
    assert v.num_trials == 500
    assert v.verdict in (NO_EDGE, EDGE_CONFIRMED)
    if v.dsr is not None and v.dsr < Decimal("0.95"):
        assert v.verdict == NO_EDGE


def test_determinism_same_input_same_verdict():
    strat = _curve_from_returns(
        Decimal("10000"), _alternating("0.006", "0.001", 40)
    )
    bench = _curve_from_returns(
        Decimal("10000"), _alternating("0.001", "0.004", 40)
    )
    a = forward_edge_verdict(strat, bench, min_obs=20)
    b = forward_edge_verdict(strat, bench, min_obs=20)
    assert a == b  # frozen dataclass 동치


# ------------------------------------------------------------- calmar (038)


def test_calmar_basic_one_year():
    # 총수익 20%·기간 252봉(1년)·최대낙폭 10% → CAGR 20% / 10% = 2.0.
    c = calmar_ratio(Decimal("20"), Decimal("10"), n_obs=252)
    assert c is not None
    assert abs(c - Decimal("2.0")) < Decimal("0.01")


def test_calmar_higher_when_drawdown_smaller():
    # 같은 수익이라도 낙폭이 작으면 칼마가 크다(자본 방어 보상).
    deep = calmar_ratio(Decimal("20"), Decimal("20"), n_obs=252)
    shallow = calmar_ratio(Decimal("20"), Decimal("5"), n_obs=252)
    assert shallow > deep


def test_calmar_zero_drawdown_is_none():
    assert calmar_ratio(Decimal("20"), Decimal("0"), n_obs=252) is None


def test_calmar_total_loss_is_none():
    assert calmar_ratio(Decimal("-100"), Decimal("50"), n_obs=252) is None


def test_calmar_none_inputs():
    assert calmar_ratio(None, Decimal("10"), n_obs=252) is None
    assert calmar_ratio(Decimal("10"), None, n_obs=252) is None


def test_verdict_reports_calmar_fields():
    # 낙폭이 있는(진동 폭>평균) 곡선이라야 칼마가 정의된다(단조 상승은 낙폭 0 → None).
    strat = _curve_from_returns(Decimal("10000"), _alternating("0.003", "0.006", 40))
    bench = _curve_from_returns(Decimal("10000"), _alternating("0.001", "0.004", 40))
    v = forward_edge_verdict(strat, bench, min_obs=20)
    d = v.to_json_dict()
    assert "strategy_calmar" in d
    assert "benchmark_calmar" in d
    assert "beats_benchmark_calmar" in d
    assert d["schema_version"] == "1.2"
    assert d["significance_method"] == PAIRED_ACTIVE_RETURN_PSR_METHOD
    assert d["active_information_ratio_annual"] is not None
    # 낙폭이 있는 전략·벤치 모두 칼마가 산출된다.
    assert v.strategy_calmar is not None
    assert v.benchmark_calmar is not None


def test_verdict_monotonic_strategy_calmar_none():
    # 단조 상승(낙폭 0)이면 칼마는 정의 불가(None) — 정직한 처리.
    strat = _curve_from_returns(Decimal("10000"), _alternating("0.006", "0.001", 40))
    v = forward_edge_verdict(strat, None, min_obs=20)
    assert v.strategy_calmar is None  # 낙폭 0 → 칼마 None
    assert v.significance_method == ABSOLUTE_RETURN_PSR_METHOD


def test_to_json_dict_roundtrip_keys():
    curve = _curve_from_returns(Decimal("10000"), _alternating("0.005", "0.001", 30))
    v = forward_edge_verdict(curve, None, min_obs=20)
    d = v.to_json_dict()
    for key in (
        "schema_version",
        "verdict",
        "reason",
        "n_obs",
        "strategy_sharpe_annual",
        "psr_vs_benchmark",
        "dsr",
        "has_benchmark",
    ):
        assert key in d
    assert d["verdict"] in (EDGE_CONFIRMED, NO_EDGE, INSUFFICIENT_DATA)
