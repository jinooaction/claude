from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path


def _load_guard():
    path = Path(__file__).resolve().parents[2] / "scripts" / "local_concurrency_guard.py"
    spec = importlib.util.spec_from_file_location("local_concurrency_guard", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_push_targets_main_detects_direct_main_push():
    guard = _load_guard()

    assert guard.push_targets_main(
        "refs/heads/topic abc123 refs/heads/main def456\n"
    )
    assert not guard.push_targets_main(
        "refs/heads/topic abc123 refs/heads/topic def456\n"
    )


def test_evaluate_blocks_commit_when_recent_session_uses_same_worktree(tmp_path):
    guard = _load_guard()
    state = guard.CurrentState(
        repo=tmp_path,
        worktree=tmp_path,
        branch="Codex/feature",
        head="abc123",
        thread_id="CODEX_THREAD_ID:this",
        dirty_paths=frozenset({"src/a.py"}),
    )
    other = guard.Lease(
        path=tmp_path / "other.json",
        thread_id="CODEX_THREAD_ID:other",
        host="host",
        worktree=str(tmp_path),
        branch="Codex/feature",
        head="def456",
        updated_at=time.time(),
        dirty_paths=frozenset({"src/a.py"}),
    )

    findings = guard.evaluate(state, [other], mode="pre-commit")

    conflict_findings = [f for f in findings if "CODEX_THREAD_ID:other" in f.message]
    assert len(conflict_findings) == 1
    assert conflict_findings[0].level == "BLOCK"
    assert "같은 worktree" in conflict_findings[0].message
    assert "같은 브랜치" in conflict_findings[0].message
    assert "src/a.py" in conflict_findings[0].message


def test_evaluate_blocks_main_commit(tmp_path):
    guard = _load_guard()
    state = guard.CurrentState(
        repo=tmp_path,
        worktree=tmp_path,
        branch="main",
        head="abc123",
        thread_id="CODEX_THREAD_ID:this",
        dirty_paths=frozenset(),
    )

    findings = guard.evaluate(state, [], mode="pre-commit")

    assert any(f.level == "BLOCK" and "`main`" in f.message for f in findings)


def test_render_report_deduplicates_same_logical_session(tmp_path):
    guard = _load_guard()
    state = guard.CurrentState(
        repo=tmp_path,
        worktree=tmp_path,
        branch="Codex/feature",
        head="abc123",
        thread_id="CODEX_THREAD_ID:this",
        dirty_paths=frozenset({"src/a.py"}),
    )
    older = guard.Lease(
        path=tmp_path / "older.json",
        thread_id="TERM_SESSION_ID:terminal",
        host="old-host",
        worktree=str(tmp_path),
        branch="Codex/feature",
        head="old111",
        updated_at=time.time() - 60,
        dirty_paths=frozenset({"old.py"}),
    )
    newer = guard.Lease(
        path=tmp_path / "newer.json",
        thread_id="TERM_SESSION_ID:terminal",
        host="new-host",
        worktree=str(tmp_path),
        branch="Codex/feature",
        head="new222",
        updated_at=time.time(),
        dirty_paths=frozenset({"src/a.py"}),
    )

    findings = guard.evaluate(state, [older, newer], mode="session-start")
    report = guard.render_report(state, [older, newer], findings)

    assert report.count("TERM_SESSION_ID:terminal") == 2
    assert "other sessions : 1 recent lease(s)" in report
    assert "new222" in report
    assert "old111" not in report
    assert "수정 파일 겹침: src/a.py" in report
