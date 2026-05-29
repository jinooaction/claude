"""스펙 024 — 최대 샤프 포트폴리오 최적화 단위/통합 테스트.

검증 대상:
  SC-01: 고기대수익률 자산에 더 높은 가중치
  SC-02: 균등 수익률·분산 → 균등 가중치
  SC-03: 데이터 부족(< 30일) → 역변동성 fallback
  SC-04: 음수 가중치 없음 (롱-온리)
  SC-05: 가중치 합 ≈ 1 (정규화 검증)
  SC-06: mode="max_sharpe" 옵트인 검증
  SC-07: 모든 μ ≤ 0이면 균등 가중치 반환
  SC-08: max_sharpe 포트폴리오 샤프 ≥ min_variance 포트폴리오 샤프 (ex-ante)
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from auto_invest.strategy.sizing import (
    covariance_matrix,
    expected_returns_from_closes,
    max_sharpe_weights,
    min_variance_weights,
)

# =========================================================================== #
# 헬퍼                                                                         #
# =========================================================================== #


def _closes_dict(values: list[float], start: date | None = None) -> dict[date, Decimal]:
    if start is None:
        start = date(2024, 1, 1)
    return {start + timedelta(days=i): Decimal(str(v)) for i, v in enumerate(values)}


def _ramp(start: float, step: float, n: int) -> list[float]:
    return [start + step * i for i in range(n)]


def _volatile(base: float, amp: float, n: int) -> list[float]:
    result = []
    v = base
    for i in range(n):
        v = v + amp if i % 2 == 0 else v - amp
        result.append(max(v, 1.0))
    return result


# =========================================================================== #
# SC-01: 고기대수익률 자산에 더 높은 가중치                                      #
# =========================================================================== #


def test_max_sharpe_prefers_high_expected_return():
    """같은 분산이면 기대 수익률 높은 자산에 더 높은 가중치를 배분해야 한다.

    균등 공분산 행렬에서 μ 비율이 그대로 가중치 비율로 반영된다.
    """
    # 균등 공분산 — 분산 구조 동일, μ만 다름
    cov: list[list[Decimal]] = [
        [Decimal("0.01") if i == j else Decimal("0.002") for j in range(2)]
        for i in range(2)
    ]
    # high=0.3, low=0.1 → Σ^{-1}μ에서 high 쪽이 더 큼
    mu_list = [0.3, 0.1]

    weights = max_sharpe_weights(cov, mu_list)
    assert weights[0] > weights[1], (
        f"고기대수익 가중치({weights[0]}) > 저기대수익 가중치({weights[1]}) 기대"
    )


# =========================================================================== #
# SC-02: 균등 수익률·분산 → 균등 가중치                                         #
# =========================================================================== #


def test_max_sharpe_equal_returns_equal_cov_gives_equal_weights():
    """균등 공분산 + 균등 기대 수익률이면 균등 가중치를 반환해야 한다."""
    cov: list[list[Decimal]] = [
        [Decimal("0.01") if i == j else Decimal("0.005") for j in range(3)]
        for i in range(3)
    ]
    mu_list = [0.1, 0.1, 0.1]
    weights = max_sharpe_weights(cov, mu_list)
    assert len(weights) == 3
    for w in weights:
        assert abs(w - Decimal("0.333333")) < Decimal("0.001"), f"균등 가중치 기대: {w}"


# =========================================================================== #
# SC-03: 데이터 부족 → fallback                                                #
# =========================================================================== #


def test_max_sharpe_group_scales_fallback_on_insufficient_data():
    """공통 거래일 < 30이면 역변동성 fallback을 사용해야 한다."""
    from auto_invest.strategy.sizing import max_sharpe_group_scales, realized_volatility

    short = 20
    closes_a = _closes_dict(_ramp(100.0, 0.5, short + 1))
    closes_b = _closes_dict(_volatile(100.0, 3.0, short + 1))
    vols = {
        "r_a": realized_volatility(list(closes_a.values())),
        "r_b": realized_volatility(list(closes_b.values())),
    }
    result = max_sharpe_group_scales(
        {"r_a": closes_a, "r_b": closes_b},
        lookback_bars=short,
        member_vols=vols,
    )
    assert "r_a" in result and "r_b" in result
    assert result["r_a"] > Decimal(0) and result["r_b"] > Decimal(0)


# =========================================================================== #
# SC-04: 음수 가중치 없음 (롱-온리)                                              #
# =========================================================================== #


def test_max_sharpe_no_negative_weights():
    """모든 반환 가중치 >= 0 이어야 한다 (롱-온리 제약)."""
    import random

    rng = random.Random(42)
    n = 60
    closes_dict = {
        f"asset_{k}": _closes_dict([rng.uniform(50, 150) + i * 0.2 for i in range(n + 1)])
        for k in range(5)
    }
    cov = covariance_matrix(closes_dict, lookback_bars=n)
    if cov is None:
        pytest.skip("공분산 행렬 계산 불가 — 스킵")
    mu = expected_returns_from_closes(closes_dict, lookback_bars=n)
    if mu is None:
        pytest.skip("기대 수익률 계산 불가 — 스킵")
    mu_list = [mu[k] for k in closes_dict]
    weights = max_sharpe_weights(cov, mu_list)
    for w in weights:
        assert w >= Decimal(0), f"음수 가중치 발견: {w}"


# =========================================================================== #
# SC-05: 가중치 합 ≈ 1                                                         #
# =========================================================================== #


def test_max_sharpe_weights_sum_to_one():
    """가중치 합이 1.0 에 근사해야 한다."""
    n = 60
    closes = {
        "a": _closes_dict(_ramp(100.0, 0.8, n + 1)),
        "b": _closes_dict(_ramp(80.0, 0.3, n + 1)),
        "c": _closes_dict(_volatile(90.0, 2.0, n + 1)),
    }
    cov = covariance_matrix(closes, lookback_bars=n)
    assert cov is not None
    mu = expected_returns_from_closes(closes, lookback_bars=n)
    assert mu is not None
    mu_list = [mu[k] for k in closes]
    weights = max_sharpe_weights(cov, mu_list)
    total = sum(weights)
    assert abs(total - Decimal(1)) < Decimal("0.001"), f"가중치 합 = {total}"


# =========================================================================== #
# SC-06: 옵트인 — mode="max_sharpe" 유효                                       #
# =========================================================================== #


def test_max_sharpe_mode_is_opt_in():
    """SizingConfig mode 필드에 'max_sharpe' 값이 유효해야 한다."""
    from auto_invest.config.rules import SizingConfig

    cfg = SizingConfig(mode="max_sharpe", lookback_bars=20)
    assert cfg.mode == "max_sharpe"

    for m in ("fixed", "target_vol", "inverse_vol", "erc", "min_variance"):
        assert SizingConfig(mode=m).mode == m  # type: ignore[arg-type]


# =========================================================================== #
# SC-07: 모든 μ ≤ 0이면 균등 가중치                                             #
# =========================================================================== #


def test_max_sharpe_all_non_positive_mu_returns_equal_weights():
    """기대 수익률이 전부 0 이하이면 균등 가중치를 반환해야 한다."""
    cov: list[list[Decimal]] = [
        [Decimal("0.01") if i == j else Decimal("0.002") for j in range(3)]
        for i in range(3)
    ]
    mu_list = [-0.1, -0.2, 0.0]  # 전부 비양수
    weights = max_sharpe_weights(cov, mu_list)
    assert len(weights) == 3
    for w in weights:
        assert abs(w - Decimal("0.333333")) < Decimal("0.001"), f"균등 가중치 기대: {w}"


# =========================================================================== #
# SC-08: max_sharpe 샤프 ≥ min_variance 샤프 (ex-ante)                        #
# =========================================================================== #


def test_max_sharpe_portfolio_return_exceeds_min_variance():
    """max_sharpe 포트폴리오의 기대 수익률이 min_variance보다 높아야 한다.

    max_sharpe는 Σ^{-1}·μ 방향으로 기울어져 수익률을 반영한다.
    롱-온리 제약 후에도 기대 수익률이 더 높아야 한다.
    균등 공분산 행렬을 써서 수치 안정성을 보장한다.
    """
    # 균등 공분산 — 3자산, 수익률 격차가 뚜렷함
    cov: list[list[Decimal]] = [
        [Decimal("0.01") if i == j else Decimal("0.001") for j in range(3)]
        for i in range(3)
    ]
    # a가 가장 높은 수익률, c가 가장 낮음
    mu_list = [0.4, 0.1, 0.02]

    ms_w = max_sharpe_weights(cov, mu_list)
    mv_w = min_variance_weights(cov)

    ms_ret = sum(float(w) * m for w, m in zip(ms_w, mu_list, strict=True))
    mv_ret = sum(float(w) * m for w, m in zip(mv_w, mu_list, strict=True))

    assert ms_ret >= mv_ret - 1e-6, (
        f"max_sharpe 기대 수익률({ms_ret:.4f}) ≥ min_variance 기대 수익률({mv_ret:.4f}) 기대"
    )
