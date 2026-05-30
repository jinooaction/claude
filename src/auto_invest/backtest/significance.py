"""Multiple-testing / overfitting-adjusted Sharpe statistics — 스펙 027.

세계 최고 수준 측정 토대의 마지막 조각이다. 스펙 016이 백테스트를 정직(비용)·통일
(단일 잣대)·표본 외 검증(워크포워드)되게 만들었지만, **다중검정(multiple-testing)
보정**이 빠져 있었다. 알파 팩터를 계속 추가하고 튜너가 후보를 계속 시도하면 "여러 번
시도해서 우연히 좋아 보이는" 선택 편향에 노출된다 — 이 모듈이 그것을 정량화한다.

Bailey & López de Prado(2014), "The Deflated Sharpe Ratio"의 세 통계:

  * **확률적 샤프 비율(PSR)** — 표본 길이 n, 왜도 γ3, 첨도 γ4 를 감안해 "참 샤프가
    기준선 SR* 보다 클 확률"을 낸다. 비정규성(뚱뚱한 꼬리·음의 왜도)을 벌점한다.
  * **최소 트랙레코드 길이(MinTRL)** — PSR 이 목표 신뢰수준을 넘기는 데 필요한 최소
    관측 수.
  * **디플레이티드 샤프 비율(DSR)** — 기준선을 0 이 아니라 "N 개 시도의 기대 최대
    샤프 SR_0"으로 둔 PSR. 다중검정으로 부풀려진 샤프를 깎아 내린다.

입력은 `metrics.sharpe_ratio`·`sortino_ratio`와 **같은 일별 수익률 시계열**이라 잣대가
갈라지지 않는다(헌법 X.2). `SR_hat` 은 기간당(비연율) 샤프로 내부 계산하되, 외부에서
받는 기준 샤프는 연율 단위(÷√252 로 환산) — `metrics` 의 연율(√252) 규약과 단일 잣대.

안전 경계: 오프라인·읽기 전용·순수 결정론적. 라이브 주문 경로·감사 스키마 무관,
Kernel 터치 0 건. `Φ`·`Φ⁻¹` 은 scipy 없이 표준 라이브러리로 구현(공급망 표면 최소,
R-B11 정신). 모든 출력은 Decimal 6 자리 정규화(`canonicalise_decimal`).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

import numpy as np

from .data_model import canonicalise_decimal

TRADING_DAYS_PER_YEAR = 252
# 오일러-마스케로니 상수 γ — 기대 최대값의 극단값 이론(Gumbel) 근사에 쓰인다.
EULER_MASCHERONI = 0.5772156649015329


# ---------- 표준정규 분포 (scipy 없이) -------------------------------------


def _norm_cdf(x: float) -> float:
    """표준정규 누적분포 Φ(x) — `math.erfc` 기반(정확, 의존성 없음)."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


# Acklam 의 역정규 누적분포 유리근사 계수(절대오차 ~1.15e-9).
_A = (
    -3.969683028665376e01,
    2.209460984245205e02,
    -2.759285104469687e02,
    1.383577518672690e02,
    -3.066479806614716e01,
    2.506628277459239e00,
)
_B = (
    -5.447609879822406e01,
    1.615858368580409e02,
    -1.556989798598866e02,
    6.680131188771972e01,
    -1.328068155288572e01,
)
_C = (
    -7.784894002430293e-03,
    -3.223964580411365e-01,
    -2.400758277161838e00,
    -2.549732539343734e00,
    4.374664141464968e00,
    2.938163982698783e00,
)
_D = (
    7.784695709041462e-03,
    3.224671290700398e-01,
    2.445134137142996e00,
    3.754408661907416e00,
)
_P_LOW = 0.02425
_P_HIGH = 1.0 - _P_LOW


def _norm_ppf(p: float) -> float:
    """표준정규 분위수 Φ⁻¹(p) — Acklam 유리근사 + Halley 1 스텝 정밀화.

    p∈(0,1)만 유효. 경계(0/1)는 ±무한대라 호출자가 미리 거른다.
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"_norm_ppf requires 0 < p < 1, got {p}")
    if p < _P_LOW:
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / (
            (((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0
        )
    elif p <= _P_HIGH:
        q = p - 0.5
        r = q * q
        x = (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q / (
            ((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1.0
        )
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -(((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / (
            (((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0
        )
    # Halley refinement: 근사 오차를 한 스텝 더 줄인다.
    e = _norm_cdf(x) - p
    u = e * math.sqrt(2.0 * math.pi) * math.exp(x * x / 2.0)
    x = x - u / (1.0 + x * u / 2.0)
    return x


# ---------- 표본 적률 -------------------------------------------------------


def _to_float_array(values: Sequence[Decimal | float | int]) -> np.ndarray:
    return np.asarray([float(v) for v in values], dtype=np.float64)


def _central_moments(arr: np.ndarray) -> tuple[float, float, float] | None:
    """(m2, skew, kurt) — 표준화 왜도·비초과 첨도(정규=3). 분산 0 이면 None."""
    n = arr.size
    if n < 2:
        return None
    mean = float(np.mean(arr))
    dev = arr - mean
    m2 = float(np.mean(dev**2))
    if m2 <= 0.0:
        return None
    m3 = float(np.mean(dev**3))
    m4 = float(np.mean(dev**4))
    skew = m3 / (m2**1.5)
    kurt = m4 / (m2**2)
    return m2, skew, kurt


def sample_skewness(daily_returns: Sequence[Decimal | float | int]) -> Decimal | None:
    """표본 왜도 γ3(Fisher-Pearson). 관측 < 2 또는 분산 0 이면 None."""
    moments = _central_moments(_to_float_array(daily_returns))
    if moments is None:
        return None
    return Decimal(canonicalise_decimal(moments[1]))


def sample_kurtosis(daily_returns: Sequence[Decimal | float | int]) -> Decimal | None:
    """표본 첨도 γ4(비초과 — 정규분포는 3). 관측 < 2 또는 분산 0 이면 None."""
    moments = _central_moments(_to_float_array(daily_returns))
    if moments is None:
        return None
    return Decimal(canonicalise_decimal(moments[2]))


# ---------- 내부: 기간당 샤프 + 적률 ---------------------------------------


@dataclass(frozen=True)
class _TrackStats:
    sr_per_period: float  # 비연율(기간당) 샤프 SR_hat
    n_obs: int
    skew: float  # γ3
    kurt: float  # γ4 (비초과)


def _track_stats(arr: np.ndarray) -> _TrackStats | None:
    """수익률 시계열 → 기간당 샤프 + 표본 적률. ddof=1(metrics 와 동일 규약)."""
    n = arr.size
    if n < 2:
        return None
    std = float(np.std(arr, ddof=1))
    if std == 0.0:
        return None
    moments = _central_moments(arr)
    if moments is None:
        return None
    sr = float(np.mean(arr)) / std
    return _TrackStats(sr_per_period=sr, n_obs=n, skew=moments[1], kurt=moments[2])


def _sr_estimator_std(sr: float, skew: float, kurt: float) -> float:
    """샤프 추정량의 표준오차(Lo/Mertens): √(1 − γ3·SR + (γ4−1)/4·SR²).

    정규 수익률(skew=0, kurt=3)이면 √(1 + SR²/2). 비정규성(음의 왜도·뚱뚱한 꼬리)이
    이 표준오차를 키워 PSR 을 낮춘다. 수치적으로 음수가 되면(극단 입력) fail-safe 로
    정규 근사값을 쓴다.
    """
    var = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    if var <= 0.0:
        var = 1.0 + 0.5 * sr * sr
    return math.sqrt(var)


def _psr_per_period(stats: _TrackStats, benchmark_sr_pp: float) -> float:
    """기간당 기준선 SR* 에 대한 확률적 샤프 비율(0..1)."""
    se = _sr_estimator_std(stats.sr_per_period, stats.skew, stats.kurt)
    z = (stats.sr_per_period - benchmark_sr_pp) * math.sqrt(stats.n_obs - 1) / se
    return _norm_cdf(z)


# ---------- 공개 API --------------------------------------------------------


def probabilistic_sharpe_ratio(
    daily_returns: Sequence[Decimal | float | int],
    *,
    benchmark_sharpe_annual: Decimal | float | int = Decimal("0"),
) -> Decimal | None:
    """확률적 샤프 비율(PSR) — 참 샤프가 기준선보다 클 확률(0..1).

    표본 길이와 수익률 비정규성(왜도·첨도)을 감안한다. 관측 < 2 또는 분산 0 이면
    None(fail-safe). `benchmark_sharpe_annual` 은 연율 단위(÷√252 로 기간당 환산).
    """
    stats = _track_stats(_to_float_array(daily_returns))
    if stats is None:
        return None
    benchmark_pp = float(benchmark_sharpe_annual) / math.sqrt(TRADING_DAYS_PER_YEAR)
    return Decimal(canonicalise_decimal(_psr_per_period(stats, benchmark_pp)))


def minimum_track_record_length(
    daily_returns: Sequence[Decimal | float | int],
    *,
    benchmark_sharpe_annual: Decimal | float | int = Decimal("0"),
    confidence: Decimal | float = Decimal("0.95"),
) -> Decimal | None:
    """최소 트랙레코드 길이(MinTRL) — PSR 이 `confidence` 를 넘기는 최소 관측 수.

    관측 샤프가 기준선 이하면(우위 없음) None. 관측 < 2 또는 분산 0 이어도 None.
    """
    stats = _track_stats(_to_float_array(daily_returns))
    if stats is None:
        return None
    conf = float(confidence)
    if not 0.0 < conf < 1.0:
        raise ValueError(f"confidence must be in (0,1), got {confidence}")
    benchmark_pp = float(benchmark_sharpe_annual) / math.sqrt(TRADING_DAYS_PER_YEAR)
    edge = stats.sr_per_period - benchmark_pp
    if edge <= 0.0:
        return None
    se = _sr_estimator_std(stats.sr_per_period, stats.skew, stats.kurt)
    z_conf = _norm_ppf(conf)
    min_trl = 1.0 + (se * se) * (z_conf / edge) ** 2
    return Decimal(canonicalise_decimal(min_trl))


def expected_max_sharpe(
    num_trials: int,
    trial_sharpe_std_annual: Decimal | float | int,
) -> Decimal:
    """N 개 독립 시도의 기대 최대 (연율) 샤프 SR_0 — 다중검정 디플레이션 기준선.

    극단값 이론(Gumbel) 근사:
        SR_0 = √V·[(1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e))]
    γ=오일러-마스케로니, e=오일러 수, V=시도한 샤프들의 분산. N≤1 이면 0(선택 편향
    없음). 입력·출력 모두 연율 샤프 단위.
    """
    if num_trials <= 1:
        return Decimal(canonicalise_decimal("0"))
    std = float(trial_sharpe_std_annual)
    if std <= 0.0:
        return Decimal(canonicalise_decimal("0"))
    n = float(num_trials)
    term = (1.0 - EULER_MASCHERONI) * _norm_ppf(1.0 - 1.0 / n) + EULER_MASCHERONI * _norm_ppf(
        1.0 - 1.0 / (n * math.e)
    )
    return Decimal(canonicalise_decimal(std * term))


def deflated_sharpe_ratio(
    daily_returns: Sequence[Decimal | float | int],
    *,
    num_trials: int,
    trial_sharpe_std_annual: Decimal | float | int,
) -> Decimal | None:
    """디플레이티드 샤프 비율(DSR) — 다중검정 보정된 PSR.

    기준선을 0 이 아니라 `expected_max_sharpe(N, V)` 로 두어, N 개 시도로 부풀려진
    샤프를 깎는다. N=1 이면 PSR(benchmark=0)으로 환원. 관측 < 2 또는 분산 0 이면 None.
    """
    stats = _track_stats(_to_float_array(daily_returns))
    if stats is None:
        return None
    sr0_annual = expected_max_sharpe(num_trials, trial_sharpe_std_annual)
    benchmark_pp = float(sr0_annual) / math.sqrt(TRADING_DAYS_PER_YEAR)
    return Decimal(canonicalise_decimal(_psr_per_period(stats, benchmark_pp)))


def deflated_sharpe_ratio_from_trial_sharpes(
    daily_returns: Sequence[Decimal | float | int],
    trial_sharpes_annual: Sequence[Decimal | float | int],
) -> Decimal | None:
    """DSR — 시도한 모든 설정의 (연율) 샤프 횡단면에서 N·V 를 직접 계산.

    `trial_sharpes_annual` 은 운영자/튜너가 시도한 모든 설정의 연율 샤프 목록이다.
    N=len, V=표본분산(ddof=1). 시도 < 2 면 디플레이션 없이 PSR(0)로 환원. 관측 < 2
    또는 분산 0 이면 None.
    """
    arr = _to_float_array(trial_sharpes_annual)
    num_trials = int(arr.size)
    if num_trials < 2:
        return deflated_sharpe_ratio(
            daily_returns, num_trials=1, trial_sharpe_std_annual=Decimal("0")
        )
    std = float(np.std(arr, ddof=1))
    return deflated_sharpe_ratio(
        daily_returns,
        num_trials=num_trials,
        trial_sharpe_std_annual=Decimal(str(std)),
    )


@dataclass(frozen=True)
class SignificanceResult:
    """한 트랙레코드의 통계적 유의성 요약 — 운영자·리포트용."""

    n_obs: int
    sharpe_annual: Decimal
    skew: Decimal
    kurtosis: Decimal
    psr: Decimal | None
    min_track_record_obs: Decimal | None
    num_trials: int = 1
    expected_max_sharpe_annual: Decimal | None = None
    dsr: Decimal | None = None


def significance_summary(
    daily_returns: Sequence[Decimal | float | int],
    *,
    num_trials: int = 1,
    trial_sharpe_std_annual: Decimal | float | int | None = None,
    benchmark_sharpe_annual: Decimal | float | int = Decimal("0"),
    confidence: Decimal | float = Decimal("0.95"),
) -> SignificanceResult | None:
    """일별 수익률 → PSR·MinTRL·(옵션)DSR 한 번에. 관측 < 2/분산 0 이면 None."""
    arr = _to_float_array(daily_returns)
    stats = _track_stats(arr)
    if stats is None:
        return None
    sharpe_annual = Decimal(
        canonicalise_decimal(stats.sr_per_period * math.sqrt(TRADING_DAYS_PER_YEAR))
    )
    psr = probabilistic_sharpe_ratio(
        daily_returns, benchmark_sharpe_annual=benchmark_sharpe_annual
    )
    min_trl = minimum_track_record_length(
        daily_returns,
        benchmark_sharpe_annual=benchmark_sharpe_annual,
        confidence=confidence,
    )
    dsr: Decimal | None = None
    sr0: Decimal | None = None
    if num_trials > 1 and trial_sharpe_std_annual is not None:
        sr0 = expected_max_sharpe(num_trials, trial_sharpe_std_annual)
        dsr = deflated_sharpe_ratio(
            daily_returns,
            num_trials=num_trials,
            trial_sharpe_std_annual=trial_sharpe_std_annual,
        )
    return SignificanceResult(
        n_obs=stats.n_obs,
        sharpe_annual=sharpe_annual,
        skew=Decimal(canonicalise_decimal(stats.skew)),
        kurtosis=Decimal(canonicalise_decimal(stats.kurt)),
        psr=psr,
        min_track_record_obs=min_trl,
        num_trials=num_trials,
        expected_max_sharpe_annual=sr0,
        dsr=dsr,
    )


__all__ = [
    "SignificanceResult",
    "deflated_sharpe_ratio",
    "deflated_sharpe_ratio_from_trial_sharpes",
    "expected_max_sharpe",
    "minimum_track_record_length",
    "probabilistic_sharpe_ratio",
    "sample_kurtosis",
    "sample_skewness",
    "significance_summary",
]
