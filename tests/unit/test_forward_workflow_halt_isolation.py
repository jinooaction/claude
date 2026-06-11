"""Forward 페이퍼 워크플로의 halt 격리 회귀 (2026-06-11).

배경: 다섯 페이퍼 트랙의 rebalance-once 가 --halt-path 를 안 넘겨 모두 기본값
data/halt.flag(라이브 워커의 킬스위치)를 공유했다. 라이브 쪽에서 자동 설정된 묵은
깃발에 전 트랙 주문이 REJECTED_BY_GATE → NAV 영원히 0 → EDGE_CONFIRMED 불가 →
자동 무장 게이트(스펙 049) 영구 대기 — 돈으로 가는 경로가 입구에서 막혔다.

이 테스트는 트랙별 전용 halt 깃발(전용 DB 와 같은 격리 원칙)이 다시 사라지지 않게,
그리고 이 워크플로가 PAPER 전용이라는 안전 불변식을 CI 에서 못박는다. 워크플로는
셸 변수(${dbf}/${hlt})로 호출을 조립하므로 YAML 파싱 대신 텍스트 불변식을 검사한다.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "rebalance-paper-forward.yml"

# 다섯 페이퍼 트랙 — 전용 DB 와 전용 halt 깃발이 짝으로 선언되어야 한다.
_TRACKS = ("trend", "notrend", "rmbeta", "multiasset", "global")


def _workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def test_every_track_declares_paired_db_and_halt_flag():
    text = _workflow_text()
    for track in _TRACKS:
        assert f'dbf="data/forward_{track}.db"' in text, (
            f"{track} 트랙의 전용 DB 선언이 사라짐"
        )
        assert f'hlt="data/forward_{track}.halt.flag"' in text, (
            f"{track} 트랙의 전용 halt 깃발 선언이 사라짐 — 기본값 data/halt.flag "
            "공유로 회귀하면 라이브 깃발 하나가 전 트랙 주문을 막는다"
        )


def test_every_paper_rebalance_uses_isolated_halt_path():
    lines = [ln for ln in _workflow_text().splitlines() if "rebalance-once" in ln]
    # 주석/사용법이 아니라 실제 호출 라인만(uv run 포함).
    calls = [ln for ln in lines if "uv run" in ln]
    assert len(calls) == len(_TRACKS), (
        f"rebalance-once 호출이 {len(calls)}개 — 트랙 수({len(_TRACKS)})와 다름. "
        "트랙을 추가/삭제했다면 이 테스트와 halt 격리를 함께 갱신할 것."
    )
    for call in calls:
        assert "--mode paper" in call, f"PAPER 전용 워크플로에 비페이퍼 호출: {call}"
        assert "--halt-path ${hlt}" in call, (
            f"rebalance-once 가 전용 halt 깃발 없이 호출됨(기본 data/halt.flag 공유 "
            f"회귀 — 라이브 킬스위치가 페이퍼 검증을 막는다): {call}"
        )
        assert "data/halt.flag" not in call, (
            f"페이퍼 트랙이 라이브 halt 깃발을 직접 참조: {call}"
        )


def test_workflow_is_paper_only():
    # 안전 경계: 이 워크플로는 절대 실주문을 내지 않는다(라이브는 별도 채널).
    # 주석·설명 문구가 아니라 실제 명령 라인(uv run)만 검사한다.
    calls = [ln for ln in _workflow_text().splitlines() if "uv run" in ln]
    for call in calls:
        assert "--mode live" not in call, f"PAPER 전용 워크플로에 라이브 호출: {call}"


def test_halt_diagnostic_is_read_only_and_reports_live_flag():
    text = _workflow_text()
    # 진단 스텝이 라이브 깃발(data/halt.flag)을 *보고*한다 — 무장 후 실주문이 묵은
    # 깃발에 조용히 거부되지 않게 운영자 가시성을 보장.
    assert "halt_status" in text
    assert "data/halt.flag" in text
    # 읽기 전용: 어떤 명령 라인도 halt 깃발을 만들거나 지우지 않는다(설명 문구 제외).
    for line in text.splitlines():
        if "uv run" in line:
            assert "resume" not in line, f"halt 해제 명령이 워크플로에 들어옴: {line}"
        if "halt.flag" in line:
            assert "rm " not in line, f"halt 깃발 삭제 명령이 워크플로에 들어옴: {line}"
