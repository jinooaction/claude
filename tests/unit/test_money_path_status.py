"""실주문 차단 원인이 연구 단계의 대기 사유에 가려지지 않아야 한다."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime

import pytest

from auto_invest.analytics.capital_path_readiness import build_capital_path_readiness
from auto_invest.analytics.money_gate_alignment import (
    _observation_counts,
    build_money_gate_alignment,
)
from auto_invest.analytics.operator_status import build_operator_status

NOW = datetime(2026, 10, 16, 8, 19, tzinfo=UTC)
LIVE_BLOCKER = "전역 halt 안전 게이트 차단: reconciliation recovery evidence stale"
LADDER_BLOCKER = "앵커드 OOS 실패: NO_EDGE"


def _money(status="BLOCKED", detail=LIVE_BLOCKER):
    return {
        "stage": "NO_EDGE_YET",
        "blocking_gate": LADDER_BLOCKER,
        "next_action": "독립 전략 후보를 추가 검증한다.",
        "live_money_state": {
            "status": status,
            "detail": detail,
            "can_submit_real_orders": False,
            "required_gates": ["fresh reconciliation evidence and global halt clear"],
        },
    }


def _raw(money):
    return "## 결정 JSON\n\n```json\n" + json.dumps(money) + "\n```\n"


def _reports(money):
    evidence = {"money-path": _raw(money)}
    capital = build_capital_path_readiness(evidence, now=NOW)
    evidence["capital-path-readiness"] = json.dumps(capital.to_dict())
    alignment = build_money_gate_alignment(evidence, now=NOW)
    operator = build_operator_status(evidence, now=NOW)
    surface = next(s for s in operator.surfaces if s.key == "money-path")
    return capital, alignment, surface


def test_live_blocker_survives_readiness_alignment_and_operator_reports():
    money = _money()
    original = copy.deepcopy(money)
    capital, alignment, surface = _reports(money)

    assert capital.readiness_state == "LIVE_BLOCKED"
    assert capital.blocking_gate == LIVE_BLOCKER
    assert LIVE_BLOCKER in capital.next_action_ko
    assert "유지" in capital.next_action_ko
    assert capital.capital_ladder_stage == "NO_EDGE_YET"
    assert money["live_money_state"]["required_gates"][0] in capital.required_existing_gates
    assert LIVE_BLOCKER in capital.as_markdown()
    assert alignment.blocking_gate == LIVE_BLOCKER
    assert not any(i.gate_key == "blocking_gate" for i in alignment.alignment_issues)
    issue = next(i for i in alignment.alignment_issues if i.gate_key == "money-path")
    assert issue.observed == LIVE_BLOCKER
    assert LIVE_BLOCKER in surface.summary_ko
    assert surface.status == "BLOCKED"
    assert money == original


def test_live_error_numbers_do_not_replace_forward_observation_counts():
    money = _money(detail="외부 검사 실패 1/3")
    money["blocking_gate"] = "전진 관측 부족: 38/60"
    assert _observation_counts(money, None, None) == {"money-path": (38, 60)}


@pytest.mark.parametrize("detail", [None, "", "  ", False, 123, [], {"reason": "invalid"}])
def test_invalid_or_legacy_detail_keeps_existing_ladder_blocker(detail):
    capital, alignment, surface = _reports(_money(detail=detail))
    assert capital.blocking_gate == LADDER_BLOCKER
    assert alignment.blocking_gate == LADDER_BLOCKER
    assert LADDER_BLOCKER in surface.summary_ko
    assert capital.readiness_state == "LIVE_BLOCKED"


@pytest.mark.parametrize("status", ["PREVIEW_ONLY", "REAL_ORDER_PATH_ARMED", "UNKNOWN", None])
def test_nonblocked_description_never_becomes_a_live_blocker(status):
    money = _money(status=status, detail="일반 실행 안내")
    capital, alignment, surface = _reports(money)
    assert capital.blocking_gate == LADDER_BLOCKER
    assert alignment.blocking_gate == LADDER_BLOCKER
    assert "일반 실행 안내" not in capital.next_action_ko
    assert "일반 실행 안내" not in surface.summary_ko


@pytest.mark.parametrize("live_state", [None, [], "BLOCKED", {}])
def test_malformed_live_state_preserves_legacy_fallback(live_state):
    money = _money()
    money["live_money_state"] = live_state
    capital, alignment, _ = _reports(money)
    assert capital.blocking_gate == LADDER_BLOCKER
    assert alignment.blocking_gate == LADDER_BLOCKER
