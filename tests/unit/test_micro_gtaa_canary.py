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


def test_micro_gtaa_sentinel_is_operator_approved_live_armed():
    text = _SENTINEL.read_text(encoding="utf-8")
    assert _field(text, "armed") == "true"
    assert _field(text, "stage") == "micro-gtaa-live-canary"
    assert "운영자 2026-06-22 명시 승인" in (_field(text, "note") or "")


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
    assert "github.event_name != 'push'" in block
    assert "--mode live --confirm-live" in block


def test_micro_gtaa_workflow_preview_precedes_live_step():
    text = _WORKFLOW.read_text(encoding="utf-8")
    preview_idx = text.index("DRY-RUN preview")
    live_idx = text.index("LIVE rebalance")
    assert preview_idx < live_idx
    assert "--dry-run" in text[preview_idx:live_idx]


def test_micro_gtaa_workflow_checks_breaker_before_live_step():
    text = _WORKFLOW.read_text(encoding="utf-8")
    preflight_idx = text.index("Pre-live order preflight")
    breaker_idx = text.index("Pre-live circuit breaker gate")
    live_idx = text.index("LIVE rebalance")
    assert preflight_idx < breaker_idx < live_idx
    assert breaker_idx < live_idx
    assert "evaluate_from_audit" in text[breaker_idx:live_idx]
    assert "set_halt" in text[breaker_idx:live_idx]
    assert "steps.preflight.outputs.ok == 'true'" in text[breaker_idx:live_idx]
    assert "steps.breaker.outcome == 'success'" in text[live_idx:]
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
    assert "is_session_open" in block
    assert "get_purchasable_cash_usd" in block
    assert "planned_buy_notional_usd" in block
    assert "/tmp/micro_preflight.json" in block
    assert "ok=true" in block


def test_micro_gtaa_sidecar_publishes_preflight_evidence():
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "## 라이브 전 주문 전제 확인" in text
    assert "cat /tmp/micro_preflight.json" in text


def test_micro_gtaa_workflow_manual_cap_guard_is_present():
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "capital > 1000" in text
    assert "outside micro range 1..1000" in text
    assert "BRANCH=automation/rebalance-micro-gtaa-last-run" in text
