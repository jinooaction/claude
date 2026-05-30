"""스펙 027 — 다중검정 보정 통계(PSR·DSR·MinTRL) 단위 테스트.

합격 기준 SC-01~SC-11. Bailey & López de Prado(2014)의 수학적 성질을 결정론적으로
검증한다. 외부 라이브러리(scipy) 없이 구현한 `_norm_cdf`/`_norm_ppf` 정확도도 확인.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np

from auto_invest.backtest.metrics import sharpe_ratio
from auto_invest.backtest.significance import (
    _norm_cdf,
    _norm_ppf,
    _psr_per_period,
    _track_stats,
    _TrackStats,
    deflated_sharpe_ratio,
    deflated_sharpe_ratio_from_trial_sharpes,
    expected_max_sharpe,
    minimum_track_record_length,
    probabilistic_sharpe_ratio,
    sample_kurtosis,
    sample_skewness,
    significance_summary,
)

# ---------- 표준정규 구현 정확도 -------------------------------------------


def test_norm_cdf_known_values():
    assert abs(_norm_cdf(0.0) - 0.5) < 1e-12
    assert abs(_norm_cdf(1.959963985) - 0.975) < 1e-6
    assert abs(_norm_cdf(-1.959963985) - 0.025) < 1e-6


def test_norm_ppf_known_values():
    assert abs(_norm_ppf(0.975) - 1.959963985) < 1e-6
    assert abs(_norm_ppf(0.5)) < 1e-9
    assert abs(_norm_ppf(0.95) - 1.644853627) < 1e-6


def test_norm_ppf_cdf_round_trip():
    for p in (0.001, 0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 0.99, 0.999):
        assert abs(_norm_cdf(_norm_ppf(p)) - p) < 1e-9


# ---------- 합성 수익률 헬퍼 -----------------------------------------------


def _drifted_normal(mean: float, std: float, n: int, seed: int) -> list[float]:
    """평균/표준편차가 (근사적으로) 지정값인 결정론적 정규 표본."""
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    x = (x - x.mean()) / x.std(ddof=1)  # 정확히 평균 0·표본표준편차 1 로 정규화
    return (x * std + mean).tolist()


# ---------- SC-01: PSR(SR*=SR_hat) == 0.5 ----------------------------------


def test_sc01_psr_at_own_sharpe_is_half():
    arr = np.asarray(_drifted_normal(0.001, 0.01, 300, seed=1))
    stats = _track_stats(arr)
    # 화이트박스: 기준선이 관측 샤프와 같으면 z=0 → Φ(0)=0.5 (정확).
    assert _psr_per_period(stats, stats.sr_per_period) == 0.5
    # 블랙박스: 같은 성질을 연율 기준선 경로로도 확인(반올림 오차 내).
    annual = sharpe_ratio([Decimal(str(v)) for v in arr.tolist()])
    psr = probabilistic_sharpe_ratio(
        [Decimal(str(v)) for v in arr.tolist()], benchmark_sharpe_annual=annual
    )
    assert abs(float(psr) - 0.5) < 1e-4


# ---------- SC-02: PSR 은 샤프에 단조 증가 ---------------------------------


def test_sc02_psr_monotonic_in_sharpe():
    low = _drifted_normal(0.0005, 0.01, 300, seed=2)
    high = _drifted_normal(0.0015, 0.01, 300, seed=2)  # 같은 잡음, 높은 드리프트
    psr_low = probabilistic_sharpe_ratio(low)
    psr_high = probabilistic_sharpe_ratio(high)
    assert psr_high > psr_low


# ---------- SC-03: 대칭 정규 → 왜도≈0, 첨도≈3 ------------------------------


def test_sc03_normal_skew_kurtosis():
    arr = _drifted_normal(0.0, 1.0, 8000, seed=3)
    skew = float(sample_skewness(arr))
    kurt = float(sample_kurtosis(arr))
    assert abs(skew) < 0.15
    assert abs(kurt - 3.0) < 0.3


# ---------- SC-04: 음의 왜도·뚱뚱한 꼬리는 PSR 을 낮춘다 -------------------


def test_sc04_negative_skew_lowers_psr():
    n = 2000
    rng = np.random.default_rng(4)
    normal = rng.standard_normal(n)
    # 좌측으로 치우친 두꺼운 꼬리: 음의 지수분포.
    skewed = -rng.standard_gamma(2.0, n)

    def _standardise(x: np.ndarray) -> list[float]:
        x = (x - x.mean()) / x.std(ddof=1)
        return (x * 0.01 + 0.001).tolist()  # 동일 평균·표준편차 → 동일 SR_hat

    normal_r = _standardise(normal)
    skewed_r = _standardise(skewed)
    # 같은 샤프인지 확인(소수점 오차 내).
    assert abs(float(sharpe_ratio(normal_r)) - float(sharpe_ratio(skewed_r))) < 1e-3
    # 음의 왜도가 PSR 을 낮춘다(꼬리 위험 벌점).
    assert float(sample_skewness(skewed_r)) < -0.3
    assert probabilistic_sharpe_ratio(skewed_r) < probabilistic_sharpe_ratio(normal_r)


# ---------- SC-05: MinTRL 성질 + 라운드트립 --------------------------------


def test_sc05_min_trl_properties():
    weak = _drifted_normal(0.0004, 0.01, 400, seed=5)
    strong = _drifted_normal(0.0020, 0.01, 400, seed=5)
    trl_weak = minimum_track_record_length(weak)
    trl_strong = minimum_track_record_length(strong)
    assert trl_weak is not None and trl_strong is not None
    assert trl_weak > 1 and trl_strong > 1
    # 강한 우위는 더 짧은 트랙으로 유의해진다.
    assert trl_strong < trl_weak


def test_sc05_min_trl_none_when_no_edge():
    arr = _drifted_normal(0.001, 0.01, 300, seed=6)
    annual = float(sharpe_ratio([Decimal(str(v)) for v in arr]))
    # 기준선을 관측 샤프보다 높게 두면 우위 없음 → None.
    assert minimum_track_record_length(arr, benchmark_sharpe_annual=annual + 1.0) is None


def test_sc05_min_trl_round_trip():
    arr = np.asarray(_drifted_normal(0.0012, 0.01, 500, seed=7))
    stats = _track_stats(arr)
    m = minimum_track_record_length(arr)
    assert m is not None
    # 같은 SR/왜도/첨도에서 n=MinTRL 이면 PSR ≈ 0.95 (화이트박스, 정확).
    syn = _TrackStats(
        sr_per_period=stats.sr_per_period,
        n_obs=int(round(float(m))),
        skew=stats.skew,
        kurt=stats.kurt,
    )
    assert abs(_psr_per_period(syn, 0.0) - 0.95) < 0.02


# ---------- SC-06: expected_max_sharpe 단조 증가, N≤1 → 0 -------------------


def test_sc06_expected_max_sharpe():
    assert expected_max_sharpe(1, Decimal("0.5")) == Decimal("0.000000")
    assert expected_max_sharpe(0, Decimal("0.5")) == Decimal("0.000000")
    assert expected_max_sharpe(2, Decimal("0.5")) > 0
    sr_10 = expected_max_sharpe(10, Decimal("0.5"))
    sr_100 = expected_max_sharpe(100, Decimal("0.5"))
    sr_1000 = expected_max_sharpe(1000, Decimal("0.5"))
    assert sr_10 < sr_100 < sr_1000
    # 분산 0 이면 디플레이션 0.
    assert expected_max_sharpe(100, Decimal("0")) == Decimal("0.000000")


# ---------- SC-07: DSR(N=1)==PSR(0), DSR(N>1) < PSR ------------------------


def test_sc07_dsr_reduces_to_psr_when_single_trial():
    arr = _drifted_normal(0.0012, 0.01, 400, seed=8)
    dsr1 = deflated_sharpe_ratio(arr, num_trials=1, trial_sharpe_std_annual=Decimal("0"))
    psr0 = probabilistic_sharpe_ratio(arr)
    assert dsr1 == psr0


def test_sc07_dsr_below_psr_with_many_trials():
    arr = _drifted_normal(0.0012, 0.01, 400, seed=9)
    psr0 = probabilistic_sharpe_ratio(arr)
    dsr = deflated_sharpe_ratio(arr, num_trials=50, trial_sharpe_std_annual=Decimal("1.0"))
    assert dsr < psr0


# ---------- SC-08: from_trial_sharpes == 명시 N·V 경로 ---------------------


def test_sc08_dsr_from_trial_sharpes_matches_explicit():
    arr = _drifted_normal(0.0012, 0.01, 400, seed=10)
    trials = [0.5, 1.2, 0.8, 1.5, 0.3]
    dsr_a = deflated_sharpe_ratio_from_trial_sharpes(arr, trials)
    std = float(np.std(np.asarray(trials), ddof=1))
    dsr_b = deflated_sharpe_ratio(
        arr, num_trials=len(trials), trial_sharpe_std_annual=Decimal(str(std))
    )
    assert dsr_a == dsr_b


def test_sc08_single_trial_cross_section_no_deflation():
    arr = _drifted_normal(0.0012, 0.01, 400, seed=11)
    dsr = deflated_sharpe_ratio_from_trial_sharpes(arr, [1.0])
    assert dsr == probabilistic_sharpe_ratio(arr)


# ---------- SC-11: fail-safe (관측 < 2 / 분산 0 → None) --------------------


def test_sc11_failsafe_none():
    assert probabilistic_sharpe_ratio([Decimal("0.01")]) is None
    assert probabilistic_sharpe_ratio([]) is None
    assert sample_skewness([1.0, 1.0, 1.0]) is None  # 분산 0
    assert sample_kurtosis([1.0, 1.0, 1.0]) is None
    assert minimum_track_record_length([1.0, 1.0, 1.0]) is None
    assert deflated_sharpe_ratio([], num_trials=5, trial_sharpe_std_annual=Decimal("1")) is None
    assert significance_summary([0.01]) is None


# ---------- significance_summary 통합 --------------------------------------


def test_significance_summary_populates_dsr_when_trials_given():
    arr = _drifted_normal(0.0012, 0.01, 400, seed=12)
    res = significance_summary(
        arr, num_trials=20, trial_sharpe_std_annual=Decimal("0.8")
    )
    assert res is not None
    assert res.n_obs == 400
    assert res.psr is not None
    assert res.dsr is not None
    assert res.expected_max_sharpe_annual is not None
    # 디플레이션은 확률을 낮춘다.
    assert res.dsr < res.psr


def test_significance_summary_no_dsr_without_trials():
    arr = _drifted_normal(0.0012, 0.01, 400, seed=13)
    res = significance_summary(arr)  # num_trials 기본 1
    assert res is not None
    assert res.dsr is None
    assert res.expected_max_sharpe_annual is None
    assert res.psr is not None


# ---------- SC-09 / SC-10: 워크포워드 배선 (replay 픽스처 없이) -------------


def test_sc09_walk_forward_defaults_add_no_reasons():
    """기본값(num_trials=1, min_psr/min_dsr=None)이면 유의성 사유 0 건(회귀 무손상)."""
    from auto_invest.backtest.walk_forward import _build_report, render_walk_forward_report

    pooled = _drifted_normal(0.0012, 0.01, 250, seed=20)
    report = _build_report(
        [],  # 윈도우 없음 → WFE 사유도 안 뜸 → 유의성 사유만 검증
        mode="rolling",
        in_sample_days=10,
        out_of_sample_days=5,
        step_days=5,
        wfe_threshold=Decimal("0.5"),
        oos_pooled_returns=pooled,
    )
    assert report.overfit_reasons == []
    assert report.overfit_suspected is False
    # 통계는 정보용으로 채워진다.
    assert report.oos_n_obs == 250
    assert report.oos_psr is not None
    assert report.oos_min_track_record_obs is not None
    assert report.oos_dsr is None  # num_trials 기본 1 → DSR 미계산
    md = render_walk_forward_report(report)
    assert "통계적 유의성" in md
    assert "디플레이티드 샤프" in md


def test_sc10_min_psr_opt_in_flags_overfit():
    from auto_invest.backtest.walk_forward import _build_report

    pooled = _drifted_normal(0.0012, 0.01, 250, seed=21)
    report = _build_report(
        [],
        mode="rolling",
        in_sample_days=10,
        out_of_sample_days=5,
        step_days=5,
        wfe_threshold=Decimal("0.5"),
        oos_pooled_returns=pooled,
        min_psr=Decimal("0.999999"),  # 사실상 불가능한 임계 → 반드시 발화
    )
    assert report.overfit_suspected is True
    assert any("PSR" in r for r in report.overfit_reasons)


def test_sc10_min_dsr_opt_in_flags_overfit():
    from auto_invest.backtest.walk_forward import _build_report

    pooled = _drifted_normal(0.0012, 0.01, 250, seed=22)
    report = _build_report(
        [],
        mode="rolling",
        in_sample_days=10,
        out_of_sample_days=5,
        step_days=5,
        wfe_threshold=Decimal("0.5"),
        oos_pooled_returns=pooled,
        num_trials=50,
        trial_sharpe_std_annual=Decimal("1.0"),
        min_dsr=Decimal("0.999999"),
    )
    assert report.oos_dsr is not None
    assert report.oos_expected_max_sharpe_annual is not None
    assert report.overfit_suspected is True
    assert any("DSR" in r for r in report.overfit_reasons)
