"""스펙 012 T022 — submit_to_canary fail-safe·오류격리·결과 매핑."""

from __future__ import annotations

import sqlite3
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

from auto_invest.canary.run import EXIT_FAILED, EXIT_INTERNAL, EXIT_OK
from auto_invest.tuner.canary_submit import submit_to_canary
from auto_invest.tuner.models import CanaryCandidate


def _git(args, cwd):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    _git(["init", "-q"], tmp_path)
    _git(["config", "user.email", "t@t.local"], tmp_path)
    _git(["config", "user.name", "tester"], tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "judgment_tunables.toml").write_text(
        "[daily_summary]\nmax_tokens = 700\n", encoding="utf-8"
    )
    _git(["add", "."], tmp_path)
    _git(["-c", "commit.gpgsign=false", "commit", "-q", "-m", "init"], tmp_path)
    return tmp_path


def _candidate() -> CanaryCandidate:
    return CanaryCandidate(
        candidate_id="latency_degradation:latency_p95_ms",
        detection_rule="latency_degradation",
        authority_tier="L2",
        target_path="config/judgment_tunables.toml",
        config_key="daily_summary.max_tokens",
        old_value="700",
        new_value="560",
        recommended_tier="L2",
        recommended_window_days=30,
        measurement_sample=40,
        rationale="r",
    )


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    return c


def _sentinel_factory(*_args, **_kwargs):
    return object()  # non-None → 캐너리 호출 경로로 진입


def test_no_data_skips(tmp_path: Path):
    res = submit_to_canary(
        _candidate(),
        repo_root=_repo(tmp_path),
        audit_conn=_conn(),
        session_date="2026-05-24",
        history_root=tmp_path / "nope",
        replay_factory=lambda *a, **k: None,
        run_canary_fn=lambda *a, **k: pytest_fail(),
    )
    assert res.outcome == "skipped"
    assert res.skip_reason == "no_replay_data"
    assert res.promoted is False


def pytest_fail():
    raise AssertionError("run_canary must not be called when no replay data")


def test_run_canary_exception_is_isolated(tmp_path: Path):
    def boom(*_a, **_k):
        raise RuntimeError("canary blew up")

    res = submit_to_canary(
        _candidate(),
        repo_root=_repo(tmp_path),
        audit_conn=_conn(),
        session_date="2026-05-24",
        history_root=tmp_path,
        replay_factory=_sentinel_factory,
        run_canary_fn=boom,
    )
    assert res.outcome == "internal_error"
    assert res.promoted is False


def test_replay_factory_exception_is_isolated(tmp_path: Path):
    def boom(*_a, **_k):
        raise RuntimeError("factory blew up")

    res = submit_to_canary(
        _candidate(),
        repo_root=_repo(tmp_path),
        audit_conn=_conn(),
        session_date="2026-05-24",
        history_root=tmp_path,
        replay_factory=boom,
    )
    assert res.outcome == "internal_error"


def test_passed_outcome(tmp_path: Path):
    def ok(*_a, **_k):
        return SimpleNamespace(
            outcome="passed",
            exit_code=EXIT_OK,
            canary_run_id=uuid.uuid4(),
            failing_metrics=[],
        )

    res = submit_to_canary(
        _candidate(),
        repo_root=_repo(tmp_path),
        audit_conn=_conn(),
        session_date="2026-05-24",
        history_root=tmp_path,
        replay_factory=_sentinel_factory,
        run_canary_fn=ok,
    )
    assert res.outcome == "passed"
    assert res.promoted is False  # 합격이어도 자동 승격 없음
    assert res.candidate_rev is not None
    assert res.baseline_rev is not None
    assert res.canary_run_id is not None


def test_failed_outcome_records_failing_metrics(tmp_path: Path):
    def failed(*_a, **_k):
        return SimpleNamespace(
            outcome="failed",
            exit_code=EXIT_FAILED,
            canary_run_id=uuid.uuid4(),
            failing_metrics=["llm_cost_regression_pct"],
        )

    res = submit_to_canary(
        _candidate(),
        repo_root=_repo(tmp_path),
        audit_conn=_conn(),
        session_date="2026-05-24",
        history_root=tmp_path,
        replay_factory=_sentinel_factory,
        run_canary_fn=failed,
    )
    assert res.outcome == "failed"
    assert "llm_cost_regression_pct" in res.failing_metrics
    assert res.promoted is False


def test_internal_exit_code_isolated(tmp_path: Path):
    def internal(*_a, **_k):
        return SimpleNamespace(
            outcome="in_progress",
            exit_code=EXIT_INTERNAL,
            canary_run_id=None,
            failing_metrics=[],
        )

    res = submit_to_canary(
        _candidate(),
        repo_root=_repo(tmp_path),
        audit_conn=_conn(),
        session_date="2026-05-24",
        history_root=tmp_path,
        replay_factory=_sentinel_factory,
        run_canary_fn=internal,
    )
    assert res.outcome == "internal_error"
