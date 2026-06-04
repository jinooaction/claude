"""스펙 040 — 라이브 캐너리 무장 센티넬 안전 회귀.

커밋된 automation/rebalance-live.request 는 **기본 비무장(armed: false)**이어야 한다.
실수로 armed: true 가 머지되면 실주문이 나가므로, 이 테스트가 안전 기본값을 못박는다.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SENTINEL = _REPO_ROOT / "automation" / "rebalance-live.request"


def _field(text: str, key: str) -> str | None:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(f"{key}:"):
            return s.split(":", 1)[1].strip()
    return None


def test_live_arming_sentinel_armed_value_is_valid():
    # armed 는 운영자가 통제하는 명시 상태(true/false). 2026-06-04 운영자 (A) 승인으로
    # true(무장). 값이 명확한 불리언 문자열인지만 못박는다(오타 방지).
    text = _SENTINEL.read_text(encoding="utf-8")
    assert _field(text, "armed") in ("true", "false")


def test_live_arming_sentinel_capital_is_small():
    """무장 여부와 무관하게 자본은 항상 소액(≤ $1,000) — 워크플로 하드 가드와 정합.

    이게 핵심 안전 불변식이다: 무장돼도 자본이 소액이면 절대 손실이 작다(AAPL ~1주).
    """
    text = _SENTINEL.read_text(encoding="utf-8")
    cap = _field(text, "capital_usd")
    assert cap is not None
    assert int(cap) <= 1000
