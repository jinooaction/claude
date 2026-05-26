"""캐너리 자동 투입 (스펙 012, US2 — FR-C12-04·05·09·10).

L2/L3 캐너리 후보를 임시 git rev(작업트리 무변경·미푸시)로 구체화하고 스펙 007
하드닝 캐너리(`run_canary`)로 검증한다. 합격/불합격을 `CanaryValidationResult` 로
돌려준다.

안전 불변:
- `promoted` 는 항상 False — 합격이 곧 배포·승격이 아니다(헌법 IX.B-2).
- 후보 구체화는 `git commit-tree`(plumbing)로만 — 작업트리·실인덱스·HEAD·브랜치
  미변경, ref 미생성, **origin 미푸시**. 임시 인덱스는 finally 에서 삭제.
- 리플레이 데이터 없으면 캐너리를 건너뛰고(skipped) 안전 종료(fail-safe).
- 한 후보의 캐너리 오류가 다른 후보·전체 실행을 막지 않도록 internal_error 로 격리.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from auto_invest.canary.replay_window import ReplayWindowInputs
from auto_invest.canary.run import (
    EXIT_OK,
    CanaryOptions,
    run_canary,
)
from auto_invest.tuner.knobs import render_max_tokens
from auto_invest.tuner.models import CanaryCandidate, CanaryValidationResult

# 후보 구체화 커밋의 고정 신원(컨테이너에 git user 미설정일 수 있음 — 오류 방지).
_GIT_IDENT = {
    "GIT_AUTHOR_NAME": "auto-invest-tuner",
    "GIT_AUTHOR_EMAIL": "tuner@auto-invest.local",
    "GIT_COMMITTER_NAME": "auto-invest-tuner",
    "GIT_COMMITTER_EMAIL": "tuner@auto-invest.local",
}

ReplayFactory = Callable[
    [CanaryCandidate, Path, Path, Path], ReplayWindowInputs | None
]


def _git(
    args: list[str], *, cwd: Path, env: dict | None = None, text_input: str | None = None
) -> str:
    res = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        input=text_input,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def _materialize_candidate_rev(
    *, repo_root: Path, target_path: str, new_content: str, message: str
) -> tuple[str, str]:
    """변경된 파일 1개를 담은 임시 후보 커밋 SHA 를 만든다(작업트리 무변경).

    반환 `(candidate_sha, head_sha)`. 임시 인덱스만 사용 — 실제 인덱스·작업트리·
    HEAD·브랜치 미변경, ref 미생성, push 미호출. 임시 인덱스는 finally 에서 삭제.
    """
    head = _git(["rev-parse", "HEAD"], cwd=repo_root)
    blob = _git(["hash-object", "-w", "--stdin"], cwd=repo_root, text_input=new_content)

    tmp_dir = tempfile.mkdtemp(prefix="tuner-canary-idx-")
    idx = os.path.join(tmp_dir, "index")
    env = {**os.environ, **_GIT_IDENT, "GIT_INDEX_FILE": idx}
    try:
        _git(["read-tree", "HEAD"], cwd=repo_root, env=env)
        _git(
            ["update-index", "--add", "--cacheinfo", f"100644,{blob},{target_path}"],
            cwd=repo_root,
            env=env,
        )
        tree = _git(["write-tree"], cwd=repo_root, env=env)
        commit = _git(
            ["commit-tree", tree, "-p", head, "-m", message],
            cwd=repo_root,
            env=env,
        )
        return commit, head
    finally:
        try:
            if os.path.exists(idx):
                os.unlink(idx)
            os.rmdir(tmp_dir)
        except OSError:
            pass


def _result(
    candidate: CanaryCandidate,
    *,
    outcome: str,
    canary_run_id: str | None = None,
    candidate_rev: str | None = None,
    baseline_rev: str | None = None,
    failing_metrics: tuple[str, ...] = (),
    skip_reason: str | None = None,
) -> CanaryValidationResult:
    return CanaryValidationResult(
        candidate_id=candidate.candidate_id,
        outcome=outcome,  # type: ignore[arg-type]
        canary_run_id=canary_run_id,
        candidate_rev=candidate_rev,
        baseline_rev=baseline_rev,
        failing_metrics=failing_metrics,
        skip_reason=skip_reason,
        promoted=False,  # 불변: 자동 승격 없음(헌법 IX.B-2)
    )


def submit_to_canary(
    candidate: CanaryCandidate,
    *,
    repo_root: Path,
    audit_conn: sqlite3.Connection,
    session_date: str,
    history_root: Path,
    rules_path: Path = Path("config/rules.toml"),
    run_canary_fn: Callable[..., Any] = run_canary,
    replay_factory: ReplayFactory | None = None,
) -> CanaryValidationResult:
    """후보 1건을 하드닝 캐너리로 검증. 절대 예외를 전파하지 않는다."""
    factory = replay_factory or _default_replay_factory
    try:
        replay_inputs = factory(candidate, repo_root, history_root, rules_path)
    except Exception:
        return _result(candidate, outcome="internal_error")

    if replay_inputs is None:
        # fail-safe: 검증할 과거 데이터 없음 → 건너뜀(튜너 실행은 정상 종료).
        return _result(candidate, outcome="skipped", skip_reason="no_replay_data")

    try:
        target_abs = repo_root / candidate.target_path
        decision_class = candidate.config_key.split(".", 1)[0]
        _, new_content = render_max_tokens(
            target_abs.read_text(encoding="utf-8"),
            decision_class,
            int(candidate.new_value),
        )
        candidate_rev, head_rev = _materialize_candidate_rev(
            repo_root=repo_root,
            target_path=candidate.target_path,
            new_content=new_content,
            message=f"[ephemeral] tuner canary candidate {candidate.candidate_id}",
        )
        outcome = run_canary_fn(
            CanaryOptions(
                tier=candidate.recommended_tier,  # type: ignore[arg-type]
                candidate_rev=candidate_rev,
                baseline_rev=head_rev,
                replay_inputs=replay_inputs,
                repo_root=repo_root,
            ),
            audit_conn=audit_conn,
        )
    except Exception:
        return _result(candidate, outcome="internal_error")

    status = getattr(outcome, "outcome", None)
    run_id = getattr(outcome, "canary_run_id", None)
    run_id_s = str(run_id) if run_id is not None else None
    if status == "passed" and getattr(outcome, "exit_code", None) == EXIT_OK:
        return _result(
            candidate,
            outcome="passed",
            canary_run_id=run_id_s,
            candidate_rev=candidate_rev,
            baseline_rev=head_rev,
        )
    if status == "failed":
        return _result(
            candidate,
            outcome="failed",
            canary_run_id=run_id_s,
            candidate_rev=candidate_rev,
            baseline_rev=head_rev,
            failing_metrics=tuple(getattr(outcome, "failing_metrics", []) or []),
        )
    # in_progress / 알 수 없는 상태 / 내부 오류 코드 → 격리.
    return _result(
        candidate,
        outcome="internal_error",
        candidate_rev=candidate_rev,
        baseline_rev=head_rev,
    )


def _default_replay_factory(
    candidate: CanaryCandidate,
    repo_root: Path,
    history_root: Path,
    rules_path: Path,
) -> ReplayWindowInputs | None:
    """인제스트된 과거 데이터로 캐너리 리플레이 입력 구성(캐너리 CLI 패턴).

    데이터셋이 없으면 None(→ skipped). 데이터는 있으나 입력 구성에 실패하면
    예외를 던져 submit_to_canary 가 internal_error 로 격리한다.
    """
    from auto_invest.backtest.data_source import (
        CSVDataSource,
        latest_dataset_dir,
        trading_days_between,
    )
    from auto_invest.cli import _load_rules_for_backtest

    latest = latest_dataset_dir(history_root)
    if latest is None:
        return None

    data_source = CSVDataSource(latest)
    symbols = list(data_source.list_symbols())
    if not symbols:
        return None
    # 모든 심볼 세션일의 합집합에서 최근 N 거래일을 윈도로.
    all_dates: set = set()
    for sym in symbols:
        all_dates.update(data_source.session_dates(sym))
    if not all_dates:
        return None
    ordered = sorted(all_dates)
    date_end = ordered[-1]
    span = trading_days_between(ordered[0], date_end)
    window = span[-candidate.recommended_window_days :] or span
    date_start = window[0]

    caps, whitelist, parsed_rules, ruleset_sha256 = _load_rules_for_backtest(rules_path)
    return ReplayWindowInputs(
        rules_path=rules_path,
        rules=parsed_rules,
        ruleset_sha256=ruleset_sha256,
        data_source=data_source,
        date_start=date_start,
        date_end=date_end,
        caps=caps,
        whitelist=whitelist,
        halt_path=repo_root / "data" / "canary" / "halt.flag",
        out_root=repo_root / "data" / "canary",
    )


__all__ = ["submit_to_canary"]
