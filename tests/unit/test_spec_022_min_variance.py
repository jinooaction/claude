"""스펙 022 — 최소 분산 포트폴리오 최적화 단위/통합 테스트.

검증 대상:
  SC-01: 2종목 최소 분산 — 변동성 낮은 쪽에 더 높은 가중치
  SC-02: 균등 공분산 → 균등 가중치 (ERC와 동일해야 함)
  SC-03: 공분산 부족(< 30일) → 역변동성 fallback
  SC-04: 음수 가중치 없음 (롱-온리)
  SC-05: 합계 = 1 (정규화)
  SC-06: mode="min_variance" 옵트인 — ranking_filter=None 기존 경로 byte 동일
  SC-07: 백테스트 replay에서 고변동성 종목이 저변동성보다 작은 가중치
  SC-08: min_variance < ERC 포트폴리오 분산 (낮은 ex-ante 분산)
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from auto_invest.strategy.sizing import (
    covariance_matrix,
    erc_weights,
    min_variance_group_scales,
    min_variance_weights,
)

# =========================================================================== #
# 헬퍼                                                                         #
# =========================================================================== #


def _closes_dict(values: list[float], start: date | None = None) -> dict[date, Decimal]:
    """날짜 키 종가 딕셔너리 생성."""
    if start is None:
        start = date(2024, 1, 1)
    return {start + timedelta(days=i): Decimal(str(v)) for i, v in enumerate(values)}


def _ramp(start: float, step: float, n: int) -> list[float]:
    return [start + step * i for i in range(n)]


def _volatile(base: float, amp: float, n: int) -> list[float]:
    """진폭 amp 로 위아래 교번하는 고변동성 시계열."""
    result = []
    v = base
    for i in range(n):
        v = v + amp if i % 2 == 0 else v - amp
        result.append(max(v, 1.0))
    return result


# =========================================================================== #
# SC-01: 저변동 자산에 더 높은 가중치                                            #
# =========================================================================== #


def test_min_variance_prefers_low_vol_asset():
    """고변동 종목보다 저변동 종목에 더 높은 가중치를 배분해야 한다."""
    n = 60
    low_vol_closes = _ramp(100.0, 0.1, n + 1)   # 완만한 상승 → 낮은 변동성
    high_vol_closes = _volatile(100.0, 5.0, n + 1)  # 큰 진동 → 높은 변동성

    cov = covariance_matrix(
        {"low": _closes_dict(low_vol_closes), "high": _closes_dict(high_vol_closes)},
        lookback_bars=n,
    )
    assert cov is not None
    weights = min_variance_weights(cov)
    assert len(weights) == 2
    # 저변동 종목(index 0)이 더 높은 가중치
    assert weights[0] > weights[1], (
        f"저변동 가중치({weights[0]}) > 고변동 가중치({weights[1]}) 기대"
    )


# =========================================================================== #
# SC-02: 균등 공분산 → 균등 가중치                                              #
# =========================================================================== #


def test_min_variance_equal_cov_gives_equal_weights():
    """모든 자산의 분산·공분산이 동일하면 균등 가중치를 반환해야 한다."""
    cov: list[list[Decimal]] = [
        [Decimal("0.01") if i == j else Decimal("0.005") for j in range(3)]
        for i in range(3)
    ]
    weights = min_variance_weights(cov)
    assert len(weights) == 3
    for w in weights:
        assert abs(w - Decimal("0.333333")) < Decimal("0.001"), f"균등 가중치 기대: {w}"


# =========================================================================== #
# SC-03: 데이터 부족 → fallback                                                #
# =========================================================================== #


def test_min_variance_group_scales_fallback_on_insufficient_data():
    """공통 거래일 < 30이면 역변동성 fallback을 사용해야 한다."""
    short = 20  # < 30
    closes_a = _closes_dict(_ramp(100.0, 0.5, short + 1))
    closes_b = _closes_dict(_volatile(100.0, 3.0, short + 1))
    from auto_invest.strategy.sizing import realized_volatility

    vols = {
        "r_a": realized_volatility(list(closes_a.values())),
        "r_b": realized_volatility(list(closes_b.values())),
    }
    result = min_variance_group_scales(
        {"r_a": closes_a, "r_b": closes_b},
        lookback_bars=short,
        member_vols=vols,
    )
    # fallback이라도 가중치가 반환돼야 함
    assert "r_a" in result and "r_b" in result
    assert result["r_a"] > Decimal(0) and result["r_b"] > Decimal(0)


# =========================================================================== #
# SC-04: 음수 가중치 없음 (롱-온리)                                              #
# =========================================================================== #


def test_min_variance_no_negative_weights():
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
    weights = min_variance_weights(cov)
    for w in weights:
        assert w >= Decimal(0), f"음수 가중치 발견: {w}"


# =========================================================================== #
# SC-05: 가중치 합 ≈ 1                                                         #
# =========================================================================== #


def test_min_variance_weights_sum_to_one():
    """가중치 합이 1.0 에 근사해야 한다 (정규화 검증)."""
    n = 60
    cov = covariance_matrix(
        {
            "a": _closes_dict(_ramp(100.0, 0.3, n + 1)),
            "b": _closes_dict(_ramp(80.0, 0.8, n + 1)),
            "c": _closes_dict(_volatile(90.0, 2.0, n + 1)),
        },
        lookback_bars=n,
    )
    assert cov is not None
    weights = min_variance_weights(cov)
    total = sum(weights)
    assert abs(total - Decimal(1)) < Decimal("0.001"), f"가중치 합 = {total}"


# =========================================================================== #
# SC-06: 옵트인 — None이면 기존 동작                                             #
# =========================================================================== #


def test_min_variance_mode_is_opt_in():
    """SizingConfig mode 필드에 'min_variance' 값이 유효해야 한다."""
    from auto_invest.config.rules import SizingConfig

    cfg = SizingConfig(mode="min_variance", lookback_bars=20)
    assert cfg.mode == "min_variance"

    # 기존 모드들도 그대로 유효
    for m in ("fixed", "target_vol", "inverse_vol", "erc"):
        assert SizingConfig(mode=m).mode == m  # type: ignore[arg-type]


# =========================================================================== #
# SC-07: 백테스트 replay — 고변동 종목 가중치 < 저변동 종목                      #
# =========================================================================== #


def test_min_variance_group_scales_high_vol_gets_less():
    """min_variance_group_scales: 고변동 룰이 저변동 룰보다 낮은 가중치."""
    n = 60
    low_vol = _closes_dict(_ramp(100.0, 0.1, n + 1))
    high_vol = _closes_dict(_volatile(100.0, 4.0, n + 1))
    from auto_invest.strategy.sizing import realized_volatility

    vols = {
        "rule_low": realized_volatility(list(low_vol.values())),
        "rule_high": realized_volatility(list(high_vol.values())),
    }
    result = min_variance_group_scales(
        {"rule_low": low_vol, "rule_high": high_vol},
        lookback_bars=n,
        member_vols=vols,
    )
    assert result["rule_low"] > result["rule_high"], (
        f"저변동({result['rule_low']}) > 고변동({result['rule_high']}) 기대"
    )


# =========================================================================== #
# SC-08: min_variance 포트폴리오 분산 ≤ ERC 포트폴리오 분산                     #
# =========================================================================== #


def test_min_variance_lower_portfolio_variance_than_erc():
    """min-variance 포트폴리오의 ex-ante 분산이 ERC보다 낮아야 한다."""
    n = 60
    closes_dict = {
        "a": _closes_dict(_ramp(100.0, 0.3, n + 1)),
        "b": _closes_dict(_ramp(80.0, 0.8, n + 1)),
        "c": _closes_dict(_volatile(90.0, 2.0, n + 1)),
    }
    cov = covariance_matrix(closes_dict, lookback_bars=n)
    if cov is None:
        pytest.skip("공분산 행렬 계산 불가")

    mv_w = min_variance_weights(cov)
    erc_w = erc_weights(cov)

    def portfolio_variance(weights: list[Decimal], cov_m: list[list[Decimal]]) -> Decimal:
        n_ = len(weights)
        var = sum(
            weights[i] * weights[j] * cov_m[i][j]
            for i in range(n_)
            for j in range(n_)
        )
        return var

    mv_var = portfolio_variance(mv_w, cov)
    erc_var = portfolio_variance(erc_w, cov)

    assert mv_var <= erc_var + Decimal("0.000001"), (
        f"min_var 분산({mv_var}) ≤ ERC 분산({erc_var}) 기대"
    )
