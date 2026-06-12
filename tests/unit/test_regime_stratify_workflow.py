"""레짐 층화 워크플로 불변식 (연구 전용 — 격리 회귀 방지).

레짐 층화 체인(bars-export → ingest-history → backtest-portfolio → regime-stratify)은
*읽기 전용 연구*다: forward 트랙 DB 는 bars-export 가 읽기만 하고, 서버 쓰기 산출물
(데이터셋·감사 DB·halt 깃발·자본 곡선·층화 JSON)은 /tmp 아래에만 생긴다.

층화는 public-data 산출물의 소비자라서 *거래 워크플로에 넣지 않고* 전용 워크플로
(regime-stratify.yml)에 산다 — 거래 워크플로의 public-data 무소비 불변식
(test_collect_public_data_workflow.py)은 포괄 텍스트 검사라 한 줄이라도 들어가면
깨진다(의도된 강한 보호선). 이 테스트는 전용 워크플로 쪽 격리를 못박는다.
워크플로는 셸 변수로 호출을 조립하므로 텍스트 불변식을 검사한다.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "regime-stratify.yml"

_STRATIFY_TRACKS = ("global", "wide")


def _workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def test_stratify_lives_outside_trading_workflows():
    """전용 워크플로 존재 + 거래 행위 0 — 재조정/무장/실주문 *명령*이 없다.

    설명 주석이 아니라 실제 명령 라인(uv run)만 검사한다(다른 워크플로 불변식과
    동일 접근).
    """
    text = _workflow_text()
    assert "id: stratify_prep" in text
    calls = [ln for ln in text.splitlines() if "uv run" in ln]
    assert calls, "uv run 명령이 하나도 없음 — 층화 체인이 사라짐"
    for call in calls:
        for banned in ("rebalance-once", "--mode", "go-live", "armed"):
            assert banned not in call, (
                f"연구 전용 워크플로에 거래 표면이 들어옴: {banned!r} — 층화는 "
                f"측정이지 거래가 아니다: {call}"
            )


def test_stratify_steps_exist_for_both_tracks():
    text = _workflow_text()
    for track in _STRATIFY_TRACKS:
        assert f"id: stratify_{track}" in text, f"{track} 층화 스텝이 사라짐"
        assert f'wrk="/tmp/stratify_{track}"' in text, (
            f"{track} 층화 작업 디렉터리가 /tmp 밖으로 이동 — 격리 위반 위험"
        )


def test_stratify_backtest_writes_only_under_tmp():
    """backtest-portfolio 의 쓰기 표면(--db/--halt-path/--equity-out)은 전부 ${wrk}(/tmp)."""
    lines = [
        ln
        for ln in _workflow_text().splitlines()
        if "uv run" in ln and "backtest-portfolio" in ln
    ]
    assert len(lines) == len(_STRATIFY_TRACKS), (
        f"backtest-portfolio 호출이 {len(lines)}개 — 층화 트랙 수와 다름. "
        "트랙을 추가/삭제했다면 이 테스트를 함께 갱신할 것."
    )
    for call in lines:
        assert "--db ${wrk}/audit.db" in call, (
            f"백테스트 감사 DB 가 /tmp 작업 디렉터리를 벗어남(forward DB 오염 위험): {call}"
        )
        assert "--halt-path ${wrk}/halt.flag" in call, (
            f"백테스트 halt 깃발이 /tmp 를 벗어남(라이브/트랙 깃발 공유 회귀): {call}"
        )
        assert "--equity-out ${wrk}/equity.csv" in call, (
            f"자본 곡선 출력이 누락/이동 — regime-stratify 입력이 끊긴다: {call}"
        )
        assert "data/" not in call.replace("deploy/", ""), (
            f"백테스트 호출이 data/ 경로를 직접 참조(쓰기 오염 위험): {call}"
        )


def test_stratify_bars_export_reads_forward_dbs():
    """bars-export 는 forward 트랙 DB 를 *읽기만* 한다(전용 DB 격리 원칙과 정합)."""
    text = _workflow_text()
    for track in _STRATIFY_TRACKS:
        assert f'dbf="data/forward_{track}.db"' in text
    lines = [
        ln
        for ln in text.splitlines()
        if "uv run" in ln and "bars-export" in ln
    ]
    assert len(lines) == len(_STRATIFY_TRACKS)
    for call in lines:
        assert "--db ${dbf}" in call, f"bars-export 가 forward DB 를 안 읽음: {call}"
        assert "--out-dir ${wrk}/bars" in call, (
            f"bars-export 출력이 /tmp 작업 디렉터리를 벗어남: {call}"
        )


def test_stratify_consumes_public_data_timeline():
    """타임라인은 공개 데이터 채널 사이드카에서 온다 — 다른(미검증) 소스로 바꾸지 말 것."""
    text = _workflow_text()
    assert "origin automation/public-data" in text
    assert "regime_timeline.csv" in text
    lines = [
        ln
        for ln in text.splitlines()
        if "uv run" in ln and "regime-stratify" in ln
    ]
    assert len(lines) == len(_STRATIFY_TRACKS)
    for call in lines:
        assert "--returns-csv ${wrk}/equity.csv" in call
        assert "--timeline-csv /tmp/regime_timeline.csv" in call


def test_stratify_publishes_own_sidecar():
    """결과는 전용 사이드카로 — forward 사이드카/거래 표면에 얹지 않는다."""
    text = _workflow_text()
    assert "automation/regime-stratify-last-run" in text
    assert "rebalance-paper-forward-last-run" not in text


def test_stratify_push_paths_cover_chain_files():
    """체인 파일이 바뀐 머지에서 즉시 실전 검증(같은 날 검증 패턴 —
    collect-public-data 의 push paths 와 동일 접근, 2026-06-12)."""
    text = _workflow_text()
    for path in (
        ".github/workflows/regime-stratify.yml",
        "src/auto_invest/analytics/regime_stratified.py",
        "src/auto_invest/backtest/portfolio_replay.py",
    ):
        assert path in text, f"같은 날 검증 push 경로 누락: {path}"
