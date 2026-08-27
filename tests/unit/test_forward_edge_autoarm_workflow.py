"""자본 사다리 워크플로 앵커드 판정 배선 불변식.

이 워크플로는 실제 돈 경로의 느린 게이트다. 표준 20일 forward 판정은 유지하되,
깊은 OOS + 짧은 forward 지속성 앵커드 판정을 함께 넘겨 첫 자본 게이트를 가속한다.
YAML 은 셸 조립이 많으므로 텍스트 불변식으로 핵심 계약을 고정한다.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "forward-edge-autoarm.yml"
_HELPER = _REPO_ROOT / "deploy" / "observe-on-instance.sh"


def _text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def _helper_text() -> str:
    return _HELPER.read_text(encoding="utf-8")


def test_autoarm_computes_anchored_verdict_read_only() -> None:
    text = _text()
    helper = _helper_text()
    assert "Compute anchored verdict on instance" in text
    assert "observe ladder-anchored-verdict" in text
    assert "bars-export" in helper
    assert "ingest-history" in helper
    assert "forward-verdict-anchored" in helper
    assert "--trailing-years 5" in helper
    assert "--min-forward-obs 5" in helper
    assert "/tmp/autoarm_anchored_global" in helper
    assert "/tmp/anchored_global.json" in text


def test_autoarm_anchored_failure_falls_back_to_empty_json() -> None:
    text = _text()
    fallback = (
        "if [[ ! -s /tmp/anchored_global.json ]]; then echo '{}' > /tmp/anchored_global.json; fi"
    )
    assert fallback in text
    assert "앵커드 산출 실패/공백은 미확정으로 흡수" in text


def test_ladder_decide_consumes_anchored_verdict() -> None:
    text = _text()
    assert "uv run auto-invest ladder-decide" in text
    assert "--verdict-json /tmp/verdict_global.json" in text
    assert "--anchored-verdict-json /tmp/anchored_global.json" in text
    assert "--profit-evidence-json /tmp/profit_evidence.json" in text
    assert "--factory-evidence-json /tmp/strategy_factory.json" in text
    assert "--factory-evidence-age-hours" in text
    assert "observe live-canary-preview ${research_capital}" in text
    assert "--fundability-preview-json /tmp/rung1_fundability_preview.json" in text
    assert "observe execution-proxy-parity" in text
    assert "--execution-proxy-parity-json /tmp/execution_proxy_parity.json" in text
    assert "--hardened-canary-json /tmp/exploration_canary.json" in text
    assert "live-canary-profit ${CAPITAL}" in text
    assert "--live-performance-json /tmp/live_performance.json" in text
    assert "--validated-portfolio deploy/global-trend-fixed-portfolio.toml" in text


def test_zero_capital_skips_live_strategy_performance_observation() -> None:
    text = _text()
    assert 'awk -v capital="${CAPITAL:-0}"' in text
    assert "capital + 0 > 0" in text
    assert 'if [[ -n "${CAPITAL}" ]]; then' not in text
    assert "live-canary-profit ${CAPITAL}" in text


def test_execution_proxy_parity_uses_a_clean_ephemeral_database() -> None:
    helper = _helper_text()
    start = helper.index("execution_proxy_parity()")
    end = helper.index("\nlive_canary_preview()", start)
    function = helper[start:end]

    assert 'mktemp "${REPO}/data/auto-invest-proxy-parity.XXXXXX.db"' in function
    assert 'rm -f "${parity_db}" "${parity_db}-shm" "${parity_db}-wal"' in function
    assert '--db "${parity_db}"' in function
    assert '--bars-db "${parity_db}"' in function
    assert "--token-cache" not in function
    assert "--db data/auto_invest.db" not in function


def test_exploration_canary_is_isolated_and_places_no_orders() -> None:
    text = _text()
    assert "Harden exact deployed candidate before exploration capital" in text
    assert "observe exploration-canary" in text
    assert "rebalance-once" not in text


def test_factory_winner_is_assigned_disarmed_before_exact_hardening() -> None:
    text = _text()
    assign = text.index("Assign a complete factory winner at zero capital first")
    harden = text.index("Harden exact deployed candidate before exploration capital")
    decide = text.index("Decide capital ladder")
    assert assign < harden < decide
    assert '[[ "${ARMED:-false}" == "false" ]]' in text
    assert "scripts/factory_evidence_gate.py" in text
    assert "FACTORY_CONTRACT_ELIGIBLE" in text
    assert "candidate_count // 0" not in text
    assert "selected_strategy_fingerprint" in text
    assert "deploy/canary-live-portfolio.toml" in text
    assert "steps.factory_assignment.outputs.changed != 'true'" in text
    assert "this changes the safety perimeter" in text


def test_sidecar_publishes_anchored_evidence_and_edge_source() -> None:
    text = _text()
    assert "edge_source=\"$(jq -r '.edge_source" in text
    assert "엣지 출처" in text
    assert "## 앵커드 판정 JSON" in text
    assert "cat /tmp/anchored_global.json" in text
    assert "## 전략 공장 완전성 판정 JSON" in text
    assert "cat /tmp/factory_evidence_assessment.json" in text
    assert "## 연구 단 1 구현 가능성 미리보기" in text
    assert "cat /tmp/rung1_fundability_preview.json" in text
    assert "## 실행 대체 ETF 동등성 감사" in text
    assert "cat /tmp/execution_proxy_parity.json" in text


def test_autoarm_pr_body_keeps_quality_gate_contract() -> None:
    text = _text()
    for heading in (
        "# 변경 요약",
        "## 위험 등급",
        "## 문제 정의",
        "## 탐색 근거",
        "## 변경 내용",
        "## 검증",
        "## 하네스 검증",
        "## 안전 경계",
        "## 인계",
        "## 자동 머지 준비",
    ):
        assert heading in text
    assert "agent_harness_probe.py --strict" in text
    assert "check_handoff_facts.py" in text
    assert "--delete-branch" not in text
