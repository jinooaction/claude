"""스펙 040/050 — 라이브 캐너리 무장 센티넬 안전 회귀.

커밋된 automation/rebalance-live.request 의 안전 불변식:
  - armed 는 명확한 불리언 문자열(true/false)이어야 한다(오타 방지).
  - 자본 규모는 **권위가 있어야 한다**:
      · 사다리 센티넬(스펙 050 — ladder_rung + account_nav_usd 보유): 자본 = 단 비율 ×
        기록된 실계좌 NAV (사다리 공식 그대로), armed = (단 ≥ 1), 낙폭 예산 = 운영자
        위임 계약 값(20). 공식과 다른 자본이 손으로 끼어들면 여기서 잡는다.
      · 레거시/수동 센티넬(사다리 필드 없음): 종전 소액 가드(≤ $1,000) 유지 — 수동
        편집으로는 소액 이상을 무장할 수 없다(큰 자본은 사다리 공식으로만).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from auto_invest.portfolio.capital_ladder import (
    DEFAULT_DD_BUDGET_PCT,
    parse_ladder_fields,
    rung_capital_usd,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SENTINEL = _REPO_ROOT / "automation" / "rebalance-live.request"


def _field(text: str, key: str) -> str | None:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(f"{key}:"):
            return s.split(":", 1)[1].strip()
    return None


def test_live_arming_sentinel_armed_value_is_valid():
    text = _SENTINEL.read_text(encoding="utf-8")
    assert _field(text, "armed") in ("true", "false")


def test_live_arming_sentinel_capital_has_authority():
    """자본은 사다리 공식(스펙 050) 또는 소액 가드(레거시) 중 하나의 권위를 가져야 한다."""
    text = _SENTINEL.read_text(encoding="utf-8")
    cap = _field(text, "capital_usd")
    assert cap is not None
    rung, _entered, nav = parse_ladder_fields(text)

    if rung is not None and nav is not None:
        # 사다리 센티넬 — 자본은 공식 그대로, armed 는 단과 정합, 예산은 위임 계약 값.
        assert int(cap) == rung_capital_usd(rung, nav), (
            f"사다리 자본 불일치: capital_usd={cap} ≠ 단 {rung} 공식 "
            f"{rung_capital_usd(rung, nav)} (NAV {nav}) — 손으로 고친 자본은 무효."
        )
        assert _field(text, "armed") == ("true" if rung >= 1 else "false")
        budget = _field(text, "dd_budget_pct")
        assert budget is not None and Decimal(budget) == DEFAULT_DD_BUDGET_PCT, (
            f"낙폭 예산 {budget} ≠ 운영자 위임 계약 {DEFAULT_DD_BUDGET_PCT}% — "
            "예산 변경은 운영자 결정(코드/계약 함께 갱신)."
        )
    else:
        # 레거시/수동 센티넬 — 종전 소액 불변식.
        assert int(cap) <= 1000, (
            "사다리 필드 없는 수동 센티넬은 소액(≤ $1,000)만 허용 — 큰 자본은 "
            "스펙 050 사다리 공식으로만 배치된다."
        )
