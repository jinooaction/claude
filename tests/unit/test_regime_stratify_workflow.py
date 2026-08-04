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
_OBSERVE_HELPER = _REPO_ROOT / "deploy" / "observe-on-instance.sh"

_STRATIFY_TRACKS = ("global", "wide")


def _workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def _observe_text() -> str:
    return _OBSERVE_HELPER.read_text(encoding="utf-8")


def _regime_helper_block() -> str:
    body = _observe_text()
    return body.split("regime_stratify_track()", 1)[1].split(
        "candidate_history_dataset()", 1
    )[0]


def test_stratify_lives_outside_trading_workflows():
    """전용 워크플로 존재 + 거래 행위 0 — 재조정/무장/실주문 *명령*이 없다.

    워크플로는 forced-command gateway의 고정 observe 명령만 부른다. 실제
    bars-export → backtest → regime-stratify 체인은 서버 헬퍼 안에 고정한다.
    """
    text = _workflow_text()
    assert "id: stratify_prep" in text
    assert "observe regime-stratify global" in text
    assert "observe regime-stratify wide" in text
    assert "scp " not in text
    assert "cd /opt/auto-invest" not in text
    assert "/usr/local/bin/uv run" not in text

    helper_block = _regime_helper_block()
    for banned in ("rebalance-once", "--mode live", "go-live", "armed"):
        assert banned not in helper_block, (
            f"연구 전용 층화 헬퍼에 거래 표면이 들어옴: {banned!r} — 층화는 "
            f"측정이지 거래가 아니다."
        )


def test_stratify_steps_exist_for_both_tracks():
    text = _workflow_text()
    for track in _STRATIFY_TRACKS:
        assert f"id: stratify_{track}" in text, f"{track} 층화 스텝이 사라짐"
        assert f"observe regime-stratify {track}" in text

    helper = _observe_text()
    assert "global|wide" in helper
    assert 'local wrk="/tmp/stratify_${track}"' in helper


def test_stratify_backtest_writes_only_under_tmp():
    """backtest-portfolio 의 쓰기 표면(--db/--halt-path/--equity-out)은 전부 ${wrk}(/tmp)."""
    helper_block = _regime_helper_block()
    assert helper_block.count("run_cli backtest-portfolio") == 1
    call = helper_block.split("run_cli backtest-portfolio", 1)[1].split(
        "run_cli regime-stratify", 1
    )[0]

    assert '--db "${wrk}/audit.db"' in call
    assert '--halt-path "${wrk}/halt.flag"' in call
    assert '--equity-out "${wrk}/equity.csv"' in call
    assert '"${TRACK_DB}"' not in call


def test_stratify_bars_export_reads_forward_dbs():
    """bars-export 는 forward 트랙 DB 를 *읽기만* 한다(전용 DB 격리 원칙과 정합)."""
    text = _observe_text()
    for track in _STRATIFY_TRACKS:
        assert f'TRACK_DB="data/forward_{track}.db"' in text

    helper_block = _regime_helper_block()
    assert helper_block.count("run_cli bars-export") == 1
    call = helper_block.split("run_cli bars-export", 1)[1].split(
        "run_cli ingest-history", 1
    )[0]
    assert '--db "${TRACK_DB}"' in call
    assert '--out-dir "${wrk}/bars"' in call


def test_stratify_consumes_public_data_timeline():
    """타임라인은 공개 데이터 채널 사이드카에서 온다 — 다른(미검증) 소스로 바꾸지 말 것."""
    text = _workflow_text()
    assert "automation/public-data:refs/remotes/origin/automation/public-data" in text
    assert "regime_timeline.csv" in text

    helper = _observe_text()
    assert "origin/automation/public-data:regime_timeline.csv" in helper
    assert 'local timeline="/tmp/regime_timeline.csv"' in helper
    helper_block = _regime_helper_block()
    assert '--returns-csv "${wrk}/equity.csv"' in helper_block
    assert '--timeline-csv "${timeline}"' in helper_block


def test_stratify_retries_if_gateway_has_not_refreshed_yet():
    """머지 직후 deploy-on-merge와 경합해도 새 observe 명령을 짧게 재시도한다."""
    text = _workflow_text()
    assert "refused command: observe regime-stratify" in text
    assert "sleep 90" in text


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
        "deploy/observe-on-instance.sh",
        "deploy/repair-ssh-boundary.sh",
        "src/auto_invest/analytics/regime_stratified.py",
        "src/auto_invest/backtest/portfolio_replay.py",
    ):
        assert path in text, f"같은 날 검증 push 경로 누락: {path}"
