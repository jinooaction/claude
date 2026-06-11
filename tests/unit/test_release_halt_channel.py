"""halt 해제 채널(release-halt.yml)의 안전 불변식 회귀 (2026-06-11).

halt 는 스펙 014 서킷 브레이커·정합성 불일치의 킬스위치다. 해제 채널은 운영자
지시(센티넬 머지 또는 확인어 입력)로만 발화해야 하고, 해제는 반드시 감사 행
(HALT_CLEARED)을 남기는 CLI(`resume --confirm`)로만 해야 한다. 이 테스트는
그 가드가 조용히 사라지지 않게 못박는다.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "release-halt.yml"
_SENTINEL = _REPO_ROOT / "automation" / "halt-release.request"


def _workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def test_release_uses_audited_cli_not_rm():
    text = _workflow_text()
    # 해제는 감사 행을 남기는 CLI 로만 — rm 은 K4 추가 전용 감사를 우회한다.
    assert "auto-invest resume --confirm" in text
    assert "--db data/auto_invest.db" in text  # HALT_CLEARED 감사 행 목적지
    for line in text.splitlines():
        if "halt.flag" in line:
            # 명령 토큰 rm 만 잡는다(--confirm 의 'rm ' 오탐 방지).
            assert not re.search(r"(?<![\w-])rm\s", line), (
                f"halt 깃발을 감사 없이 삭제: {line}"
            )


def test_release_is_gated_by_operator_channels_only():
    text = _workflow_text()
    # 트리거는 두 가드형 채널뿐: 센티넬 머지(push paths) + 확인어 수동 실행.
    assert "automation/halt-release.request" in text
    assert "RELEASE-HALT" in text
    # 스케줄(무인 반복) 트리거 금지 — 해제가 주기적으로 반복되면 킬스위치가 무력화된다.
    assert "schedule:" not in text, "halt 해제는 절대 스케줄로 반복 실행하면 안 된다"


def test_sentinel_records_operator_instruction():
    text = _SENTINEL.read_text(encoding="utf-8")
    # 센티넬은 운영자 지시·대상 깃발 사유를 포렌식 기록으로 남긴다.
    assert "release:" in text
    assert "운영자 지시" in text
