"""자본 사다리 워크플로 앵커드 판정 배선 불변식.

이 워크플로는 실제 돈 경로의 느린 게이트다. 표준 20일 forward 판정은 유지하되,
깊은 OOS + 짧은 forward 지속성 앵커드 판정을 함께 넘겨 첫 자본 게이트를 가속한다.
YAML 은 셸 조립이 많으므로 텍스트 불변식으로 핵심 계약을 고정한다.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "forward-edge-autoarm.yml"


def _text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def test_autoarm_computes_anchored_verdict_read_only() -> None:
    text = _text()
    assert "Compute anchored verdict on instance" in text
    assert "bars-export" in text
    assert "ingest-history" in text
    assert "forward-verdict-anchored" in text
    assert "--trailing-years 5" in text
    assert "--min-forward-obs 5" in text
    assert "/tmp/autoarm_anchored_global" in text
    assert "/tmp/anchored_global.json" in text


def test_autoarm_anchored_failure_falls_back_to_empty_json() -> None:
    text = _text()
    fallback = (
        "if [[ ! -s /tmp/anchored_global.json ]]; then "
        "echo '{}' > /tmp/anchored_global.json; fi"
    )
    assert fallback in text
    assert "앵커드 산출 실패/공백은 미확정으로 흡수" in text


def test_ladder_decide_consumes_anchored_verdict() -> None:
    text = _text()
    assert "uv run auto-invest ladder-decide" in text
    assert "--verdict-json /tmp/verdict_global.json" in text
    assert "--anchored-verdict-json /tmp/anchored_global.json" in text


def test_sidecar_publishes_anchored_evidence_and_edge_source() -> None:
    text = _text()
    assert "edge_source=\"$(jq -r '.edge_source" in text
    assert "엣지 출처" in text
    assert "## 앵커드 판정 JSON" in text
    assert "cat /tmp/anchored_global.json" in text
