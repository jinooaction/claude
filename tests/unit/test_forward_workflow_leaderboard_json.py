"""forward 토너먼트 리더보드의 기계 판독 JSON 발행 회귀.

재지정 루프는 사람이 읽는 마크다운 설명이 아니라, 후보별 판정·관측 품질을 담은
JSON 을 단일 증거로 소비해야 한다. 이 테스트는 forward 워크플로가 리더보드 text 와
JSON 을 함께 만들고 사이드카에 JSON 블록을 남기는 불변식을 고정한다.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FORWARD = _REPO_ROOT / ".github" / "workflows" / "rebalance-paper-forward.yml"


def _workflow_text() -> str:
    return _FORWARD.read_text(encoding="utf-8")


def test_forward_workflow_writes_leaderboard_json_artifact():
    text = _workflow_text()
    assert "forward_tournament_probe.py --verdict-dir /tmp --json" in text
    assert "> /tmp/leaderboard.json" in text
    assert "echo '{}' > /tmp/leaderboard.json" in text


def test_forward_sidecar_publishes_machine_readable_leaderboard_json():
    text = _workflow_text()
    assert "리더보드 결정 JSON" in text
    assert "cat /tmp/leaderboard.json" in text
    assert "cp /tmp/leaderboard.json leaderboard.json" in text
    assert "git add LAST_RUN.md leaderboard.json" in text
    assert "observation_health" in text
    assert "unknown_count" in text


def test_forward_workflow_calibrates_and_publishes_paired_gate_evidence():
    text = _workflow_text()
    assert "scripts/forward_gate_calibration_probe.py" in text
    assert "--repetitions 5000" in text
    assert "--json-out /tmp/forward_gate_calibration.json" in text
    assert "cp /tmp/forward_gate_calibration.json forward_gate_calibration.json" in text
    assert "git add LAST_RUN.md leaderboard.json forward_gate_calibration.json" in text


def test_forward_workflow_labels_clean_unlevered_measurement_epoch():
    text = _workflow_text()
    assert "v2-clean-unlevered" in text
    assert "legacy forward PSR/counts are ineligible" in text
    assert "forward_v2_trend.db" in text
    assert "forward_v2_notrend.db" in text
    assert " / forward_trend.db" not in text
    assert " / forward_notrend.db" not in text
