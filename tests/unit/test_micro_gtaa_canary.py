"""스펙 058 — 마이크로 GTAA 실거래 캐너리 안전 회귀."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SENTINEL = _REPO_ROOT / "automation" / "rebalance-micro-gtaa.request"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "rebalance-micro-gtaa-canary.yml"


def _field(text: str, key: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}:"):
            return stripped.split(":", 1)[1].strip().strip('"')
    return None


def test_micro_gtaa_sentinel_is_disarmed_after_intent_loss():
    text = _SENTINEL.read_text(encoding="utf-8")
    assert _field(text, "armed") == "false"
    assert _field(text, "stage") == "micro-gtaa-live-canary"
    note = _field(text, "note") or ""
    assert "latest_signal=INTENT_LOSS" in note
    assert "실주문 중단" in note


def test_micro_gtaa_sentinel_capital_and_stop_policy_are_bounded():
    text = _SENTINEL.read_text(encoding="utf-8")
    capital = Decimal(_field(text, "capital_usd") or "0")
    warning = Decimal(_field(text, "warning_drawdown_pct") or "0")
    hard_stop = Decimal(_field(text, "hard_stop_drawdown_pct") or "0")
    assert Decimal("1") <= capital <= Decimal("1000")
    assert Decimal("0") < warning < hard_stop <= Decimal("5")


def test_micro_gtaa_workflow_push_can_only_preview():
    text = _WORKFLOW.read_text(encoding="utf-8")
    live_step = re.search(
        r"name: LIVE rebalance.*?(?=\n\n      - name:|\Z)",
        text,
        flags=re.DOTALL,
    )
    assert live_step is not None
    block = live_step.group(0)
    assert "steps.gate.outputs.armed == 'true'" in block
    assert "steps.gate.outputs.blocked != 'true'" in block
    assert "steps.intent_gate.outputs.ok == 'true'" in block
    assert "github.event_name != 'push'" in block
    assert "--mode live --confirm-live" in block


def test_micro_gtaa_workflow_preview_precedes_live_step():
    text = _WORKFLOW.read_text(encoding="utf-8")
    preview_idx = text.index("DRY-RUN preview")
    live_idx = text.index("LIVE rebalance")
    assert preview_idx < live_idx
    assert "--dry-run" in text[preview_idx:live_idx]
    assert "--account-wide" in text[preview_idx:live_idx]
    assert "--side both" in text[preview_idx:live_idx]


def test_micro_gtaa_workflow_checks_breaker_before_live_step():
    text = _WORKFLOW.read_text(encoding="utf-8")
    preflight_idx = text.index("Pre-live order preflight")
    breaker_idx = text.index("Pre-live circuit breaker gate")
    live_idx = text.index("LIVE rebalance")
    assert preflight_idx < breaker_idx < live_idx
    assert breaker_idx < live_idx
    assert "evaluate_from_audit" in text[breaker_idx:live_idx]
    assert "set_halt" in text[breaker_idx:live_idx]
    assert "steps.intent_gate.outputs.ok == 'true'" in text[breaker_idx:live_idx]
    assert "steps.preflight.outputs.ok == 'true'" in text[breaker_idx:live_idx]
    assert "steps.breaker.outcome == 'success'" in text[live_idx:]
    assert "steps.intent_gate.outputs.ok == 'true'" in text[live_idx:]
    assert "steps.preflight.outputs.ok == 'true'" in text[live_idx:]


def test_micro_gtaa_workflow_preflight_records_session_and_cash():
    text = _WORKFLOW.read_text(encoding="utf-8")
    preflight = re.search(
        r"name: Pre-live order preflight.*?(?=\n\n      - name:|\Z)",
        text,
        flags=re.DOTALL,
    )
    assert preflight is not None
    block = preflight.group(0)
    assert "steps.intent_gate.outputs.ok == 'true'" in block
    assert "is_session_open" in block
    assert "get_purchasable_cash_usd" in block
    assert "planned_buy_notional_usd" in block
    assert "planned_sell_notional_usd" in block
    assert "effective_side" in block
    assert "sell_first_cash_shortfall" in block
    assert "/tmp/micro_preflight.json" in block
    assert "ok=true" in block


def test_micro_gtaa_workflow_live_uses_account_wide_effective_side():
    text = _WORKFLOW.read_text(encoding="utf-8")
    live_step = re.search(
        r"name: LIVE rebalance.*?(?=\n\n      - name:|\Z)",
        text,
        flags=re.DOTALL,
    )
    assert live_step is not None
    block = live_step.group(0)
    assert "steps.preflight.outputs.effective_side" in block
    assert "--account-wide" in block
    assert "--side ${SIDE}" in block
    assert "ssh_exit=$?" in block
    assert 'exit "${ssh_exit}"' in block


def test_micro_gtaa_sidecar_publishes_preflight_evidence():
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "## 라이브 전 전략 의도 게이트" in text
    assert "## 라이브 전 주문 전제 확인" in text
    assert "## 계좌 전체 재배치 상태" in text
    assert "## 거부 주문 기회손익" in text
    assert "## 거부 주문 누적 평가" in text
    assert "cat /tmp/micro_preflight.json" in text
    assert "cat /tmp/micro_opportunity.json" in text
    assert "opportunity_history.json" in text
    assert "opportunity_monitor.json" in text


def test_micro_gtaa_workflow_manual_cap_guard_is_present():
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "capital > 1000" in text
    assert "outside micro range 1..1000" in text
    assert "BRANCH=automation/rebalance-micro-gtaa-last-run" in text


def test_micro_gtaa_workflow_has_strategy_intent_gate_before_preflight():
    text = _WORKFLOW.read_text(encoding="utf-8")
    gate_idx = text.index("Pre-live strategy-intent gate")
    preflight_idx = text.index("Pre-live order preflight")
    live_idx = text.index("LIVE rebalance")
    assert gate_idx < preflight_idx < live_idx
    block = text[gate_idx:preflight_idx]
    assert "scripts/opportunity_live_gate.py" in block
    assert "opportunity_monitor.json" in block
    assert "/tmp/micro_intent_gate.json" in block
    assert "echo \"ok=${ok}\" >> \"$GITHUB_OUTPUT\"" in block
    assert '"ok":false' in block
    assert '"reason":"gate_evaluation_unavailable"' in block
    assert "실주문 경로에서는 안전하게 차단합니다" in block


def test_micro_gtaa_workflow_does_not_append_opportunity_when_live_skipped():
    text = _WORKFLOW.read_text(encoding="utf-8")
    monitor_idx = text.index("Update rejected order opportunity monitor")
    publish_idx = text.index("Publish micro GTAA result to sidecar branch")
    block = text[monitor_idx:publish_idx]
    assert "monitor_args=(" in block
    assert "if [[ -s /tmp/micro_live.json ]]" in block
    assert "monitor_args+=(--opportunity-json /tmp/micro_opportunity.json)" in block


def test_micro_gtaa_sidecar_next_step_names_strategy_intent_block():
    text = _WORKFLOW.read_text(encoding="utf-8")
    status_idx = text.index("## 계좌 전체 재배치 상태")
    gate_idx = text.index("## 라이브 전 전략 의도 게이트")
    block = text[status_idx:gate_idx]
    assert 'intent_gate = load("/tmp/micro_intent_gate.json")' in block
    assert 'intent_gate.get("ok") is False' in block
    assert "전략 의도 게이트 차단" in block
    assert "전략 검토 전까지 실주문 0건" in block
