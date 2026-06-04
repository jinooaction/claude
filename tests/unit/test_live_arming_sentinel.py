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


def test_live_arming_sentinel_is_disarmed_by_default():
    text = _SENTINEL.read_text(encoding="utf-8")
    assert _field(text, "armed") == "false", (
        "라이브 무장 센티넬은 기본 armed: false 여야 한다 — 실수 무장 방지."
    )


def test_live_arming_sentinel_capital_is_small():
    text = _SENTINEL.read_text(encoding="utf-8")
    cap = _field(text, "capital_usd")
    assert cap is not None
    # 소액 캐너리 — 워크플로 하드 가드($1,000)와 정합.
    assert int(cap) <= 1000
