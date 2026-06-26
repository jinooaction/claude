"""재지정 워크플로가 발행된 leaderboard.json 을 직접 소비하는지 고정한다."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REASSIGN = _REPO_ROOT / ".github" / "workflows" / "reassign-on-tournament.yml"


def _workflow_text() -> str:
    return _REASSIGN.read_text(encoding="utf-8")


def test_reassign_workflow_consumes_published_leaderboard_json() -> None:
    text = _workflow_text()
    assert "origin/automation/rebalance-paper-forward-last-run:leaderboard.json" in text
    assert "reassign-challenger-path --leaderboard-json /tmp/leaderboard.json" in text
    assert "reassign-decide \\" in text
    assert "--leaderboard-json /tmp/leaderboard.json" in text


def test_reassign_workflow_consumes_opportunity_feedback_json() -> None:
    text = _workflow_text()
    assert "Read micro GTAA opportunity feedback" in text
    assert "origin/${BRANCH}:opportunity_monitor.json" in text
    assert "--execution-feedback-json /tmp/opportunity_monitor.json" in text
    assert "라이브 거부 주문 누적 평가 JSON" in text


def test_reassign_workflow_does_not_reparse_markdown_sidecar() -> None:
    text = _workflow_text()
    assert "forward_tournament_probe.py --from-sidecar" not in text
    assert "origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md" not in text
    assert "published forward sidecar leaderboard.json unavailable" in text
    assert '"observation_health":"BLOCKED"' in text
