from __future__ import annotations

import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPERATOR_WORKFLOW = ROOT / ".github" / "workflows" / "operator-design.yml"
TRIGGER_WORKFLOW = ROOT / ".github" / "workflows" / "trigger-design.yml"
HELPER = ROOT / "scripts" / "operator_design.sh"
CLI = ROOT / "src" / "auto_invest" / "cli.py"


def _design_command_block() -> str:
    text = CLI.read_text(encoding="utf-8")
    start = text.index("@app.command(name=\"design\")")
    end = text.index("async def _fetch_kis_account_state", start)
    return text[start:end]


def test_operator_design_workflow_is_manual_proposal_only() -> None:
    text = OPERATOR_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "auto_ok" not in text
    assert "AUTO_OK" not in text
    assert "INTENT_B64" in text
    assert "bash -s -- '${INTENT}'" not in text
    assert "라이브 worker subprocess" not in text
    assert "PROPOSAL_ONLY" in text
    assert "운영자 의도 지문" in text
    assert "운영자 의도: ${INTENT}" not in text
    assert "set +e\n          ssh " in text
    assert "design_exit=${PIPESTATUS[0]}" in text


def test_trigger_design_workflow_cannot_auto_start_live_design() -> None:
    text = TRIGGER_WORKFLOW.read_text(encoding="utf-8")

    assert re.search(r"(?m)^  push:", text) is None
    assert "AUTO_OK" not in text
    assert "INTENT_B64" in text
    assert "operator_design.sh '${INTENT}'" not in text
    assert "라이브 worker 시작" not in text
    assert "의도 지문" in text
    assert "- 의도: `${INTENT}`" not in text


def test_operator_design_helper_has_no_auto_confirmation_or_live_check() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "AUTO_OK" not in text
    assert 'echo "OK"' not in text
    assert "design --check" not in text
    assert "라이브 worker" not in text
    assert "INTENT_B64" in text
    assert "base64" in text
    assert "의도 길이" in text
    assert "의도: ${INTENT}" not in text


def test_design_cli_has_no_direct_live_startup_call_graph() -> None:
    block = _design_command_block()

    assert "prompt_operator_ok" not in block
    assert "start_live_worker" not in block
    assert "RuleDesignDeployedPayload" not in block
    assert "PROPOSAL_ONLY" in block


def test_command_shaped_intent_is_encoded_before_remote_shell() -> None:
    payload = """자본 100달러, John's "low-risk" portfolio
$(touch /tmp/spec111-must-not-exist); echo hacked
`uname -a`
두 번째 줄: 금·채권·주식
"""
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    remote_command = f"INTENT_B64='{encoded}' bash -s"

    assert payload not in remote_command
    assert "touch /tmp/spec111-must-not-exist" not in remote_command
    assert "`uname -a`" not in remote_command
    assert ";" not in encoded
    assert "$" not in encoded
    assert "'" not in encoded
    assert "\n" not in encoded
