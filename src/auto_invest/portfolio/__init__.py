"""Spec 029 — 라이브 포트폴리오 순자산(NAV) 추적 (읽기 전용).

현금 + 종목별 보유 평가금액을 합친 **현재 순자산(NAV = Net Asset Value)** 을 하나의
모델로 계산하고, 브로커 실제 보유(권위 출처)와 내부 장부(audit_log 재구성)의 드리프트를
측정한다. 외부 API 호출·DB 쓰기·주문 0건 — 측정 전용(슬라이스 1).
"""

from auto_invest.portfolio.nav import (
    SOURCE_BROKER,
    SOURCE_LEDGER,
    NavDrift,
    NavHolding,
    NavSnapshot,
    compute_nav,
    render_text,
)

__all__ = [
    "SOURCE_BROKER",
    "SOURCE_LEDGER",
    "NavDrift",
    "NavHolding",
    "NavSnapshot",
    "compute_nav",
    "render_text",
]
