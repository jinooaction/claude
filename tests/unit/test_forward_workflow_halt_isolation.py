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
_HELPER = _REPO_ROOT / "deploy" / "observe-on-instance.sh"

# 페이퍼 트랙 — 전용 DB 와 전용 halt 깃발이 짝으로 선언되어야 한다(globalfixed=재지정 후보).
_TRACKS = ("trend", "notrend", "rmbeta", "multiasset", "global", "globalfixed", "wide")


def _workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def _helper_text() -> str:
    return _HELPER.read_text(encoding="utf-8")


def test_every_track_declares_paired_db_and_halt_flag():
    text = _helper_text()
    for track in _TRACKS:
        assert f'TRACK_DB="data/forward_{track}.db"' in text, (
            f"{track} 트랙의 전용 DB 선언이 사라짐"
        )
        assert f'TRACK_HALT="data/forward_{track}.halt.flag"' in text, (
            f"{track} 트랙의 전용 halt 깃발 선언이 사라짐 — 기본값 data/halt.flag "
            "공유로 회귀하면 라이브 깃발 하나가 전 트랙 주문을 막는다"
        )


def test_every_paper_rebalance_uses_isolated_halt_path():
    workflow = _workflow_text()
    helper = _helper_text()
    for track in _TRACKS:
        assert f"observe paper-track-run {track} " in workflow
    assert "rebalance-once" in helper
    assert "--mode paper" in helper
    assert '--halt-path "${TRACK_HALT}"' in helper
    assert '"data/halt.flag"' not in helper.split("paper_track_run()", 1)[1].split(
        "paper_track_verdict()", 1
    )[0]


def test_paper_track_run_repairs_only_forward_storage_writability():
    helper = _helper_text()
    repair_section = helper.split("ensure_paper_track_storage()", 1)[1].split(
        "paper_track_run()", 1
    )[0]
    paper_section = helper.split("paper_track_run()", 1)[1].split(
        "paper_track_verdict()", 1
    )[0]

    assert "ensure_paper_track_storage" in paper_section
    assert 'install -d -m 0750 -o "${APP_USER}" -g "${APP_USER}" data' in repair_section
    assert '"${TRACK_DB}" "${TRACK_DB}-wal" "${TRACK_DB}-shm" "${TRACK_HALT}"' in repair_section
    assert "data/forward_*.db" in repair_section
    assert "data/forward_*.db-wal" in repair_section
    assert "data/forward_*.db-shm" in repair_section
    assert "data/forward_*.halt.flag" in repair_section
    assert '[[ ! -L data ]] || die "unsafe data directory symlink"' in repair_section
    assert '[[ ! -L "${path}" && -f "${path}" ]]' in repair_section
    assert 'chown "${APP_USER}:${APP_USER}" "${path}"' in repair_section
    assert "chmod u+rw,go-rwx" in repair_section
    assert "data/auto_invest.db" not in repair_section
    assert "data/halt.flag" not in repair_section


def test_workflow_is_paper_only():
    # 안전 경계: 이 워크플로는 절대 실주문을 내지 않는다(라이브는 별도 채널).
    assert "observe live" not in _workflow_text()
    paper_section = _helper_text().split("paper_track_run()", 1)[1].split(
        "paper_track_verdict()", 1
    )[0]
    assert "--mode paper" in paper_section
    assert "--mode live" not in paper_section


def test_halt_diagnostic_is_read_only_and_reports_live_flag():
    text = _workflow_text()
    helper = _helper_text()
    # 진단 스텝이 라이브 깃발(data/halt.flag)을 *보고*한다 — 무장 후 실주문이 묵은
    # 깃발에 조용히 거부되지 않게 운영자 가시성을 보장.
    assert "halt_status" in text
    assert "observe halt-status" in text
    assert "data/halt.flag" in helper
    # 읽기 전용: 어떤 명령 라인도 halt 깃발을 만들거나 지우지 않는다(설명 문구 제외).
    for line in (text + "\n" + helper).splitlines():
        if "halt.flag" in line:
            assert "rm " not in line, f"halt 깃발 삭제 명령이 워크플로에 들어옴: {line}"
