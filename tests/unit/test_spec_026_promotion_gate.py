"""스펙 026 — 캐너리 → 풀라이브 승격 게이트 테스트.

SC-01: 모든 조건 충족 → ready=True.
SC-02: 기간 미달 → not ready.
SC-03: 트랙레코드(청산 0건) → not ready.
SC-04: 최대 낙폭 허용 초과 → not ready.
SC-05: 총수익률 음수(순손실) → not ready.
SC-06: 서킷브레이커 트립 이력 → not ready.
SC-07: 정합성 불일치 이력 → not ready.
SC-08: 지표 None(측정 불가) → 보수적 불합격.
SC-09: 경계값(기간==최소, 낙폭==허용, 수익률==0) → 합격(이상/이하 포함).
"""

from __future__ import annotations

from decimal import Decimal

from auto_invest.promotion.gate import evaluate_promotion_readiness

_BASE = dict(
    canary_days_elapsed=12,
    closed_trades=3,
    max_drawdown_pct=Decimal("1.5"),
    total_return_pct=Decimal("2.0"),
    breaker_tripped=False,
    reconciliation_mismatch=False,
    min_duration_days=10,
    acceptance_drawdown_pct=Decimal("3.0"),
)


def test_sc01_all_pass_ready():
    r = evaluate_promotion_readiness(**_BASE)
    assert r.ready is True
    assert all(r.checks.values())


def test_sc02_duration_short_not_ready():
    r = evaluate_promotion_readiness(**{**_BASE, "canary_days_elapsed": 9})
    assert r.ready is False
    assert r.checks["min_duration"] is False


def test_sc03_no_track_record_not_ready():
    r = evaluate_promotion_readiness(**{**_BASE, "closed_trades": 0})
    assert r.ready is False
    assert r.checks["track_record"] is False


def test_sc04_drawdown_exceeds_not_ready():
    r = evaluate_promotion_readiness(**{**_BASE, "max_drawdown_pct": Decimal("3.01")})
    assert r.ready is False
    assert r.checks["drawdown_within_acceptance"] is False


def test_sc05_negative_return_not_ready():
    r = evaluate_promotion_readiness(**{**_BASE, "total_return_pct": Decimal("-0.5")})
    assert r.ready is False
    assert r.checks["non_negative_return"] is False


def test_sc06_breaker_tripped_not_ready():
    r = evaluate_promotion_readiness(**{**_BASE, "breaker_tripped": True})
    assert r.ready is False
    assert r.checks["circuit_breaker_clear"] is False


def test_sc07_reconciliation_mismatch_not_ready():
    r = evaluate_promotion_readiness(**{**_BASE, "reconciliation_mismatch": True})
    assert r.ready is False
    assert r.checks["reconciliation_clear"] is False


def test_sc08_none_metrics_conservative_fail():
    r1 = evaluate_promotion_readiness(**{**_BASE, "max_drawdown_pct": None})
    assert r1.ready is False
    assert r1.checks["drawdown_within_acceptance"] is False

    r2 = evaluate_promotion_readiness(**{**_BASE, "total_return_pct": None})
    assert r2.ready is False
    assert r2.checks["non_negative_return"] is False


def test_sc09_boundary_values_pass():
    # 기간 == 최소, 낙폭 == 허용, 수익률 == 0 → 전부 충족(≥/≤/≥0).
    r = evaluate_promotion_readiness(
        **{
            **_BASE,
            "canary_days_elapsed": 10,
            "max_drawdown_pct": Decimal("3.0"),
            "total_return_pct": Decimal("0"),
        }
    )
    assert r.ready is True


def test_reasons_present_for_every_check():
    r = evaluate_promotion_readiness(**_BASE)
    # 사유는 6개 조건 각각에 대해 최소 1줄씩.
    assert len(r.reasons) >= len(r.checks)
    assert isinstance(r.to_json_dict()["ready"], bool)
