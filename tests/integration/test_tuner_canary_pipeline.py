"""스펙 012 T023 — 파이프라인 통합: detect→classify→candidate→submit→audit/report."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from auto_invest.persistence import db
from auto_invest.telemetry.store import TokenUsage, append_token_usage
from auto_invest.tuner.models import CanaryValidationResult
from auto_invest.tuner.runner import run_tuner

AS_OF = date(2026, 5, 24)
OFFHOURS = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)
SRC_THRESH = Path("config/llm_kpi_thresholds.toml")
SRC_TUNABLES = Path("config/judgment_tunables.toml")
KERNEL = Path(".specify/memory/kernel.toml")


def _row(ts: str) -> TokenUsage:
    return TokenUsage(
        model="claude-opus-4-7",
        decision_class="x",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=50,  # cache_hit_rate 높게 → cache_miss 안 뜨게
        cache_write_tokens=0,
        cost_usd="0.001000",
        latency_ms=3000,  # latency_p95_ms Tier C → latency_degradation
        error_class=None,
        correlation_id=ts,
        ts_utc=ts,
    )


@pytest.fixture
def setup(tmp_path: Path):
    db_path = tmp_path / "t.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    for offset in range(25):
        d = AS_OF.fromordinal(AS_OF.toordinal() - offset)
        append_token_usage(conn, _row(f"{d.isoformat()}T15:00:00.000Z"))
    conn.commit()
    conn.close()
    thresh = tmp_path / "thresholds.toml"
    tunables = tmp_path / "judgment_tunables.toml"
    shutil.copy(SRC_THRESH, thresh)
    shutil.copy(SRC_TUNABLES, tunables)
    return db_path, thresh, tunables


def _count(db_path: Path, event_type: str) -> int:
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    try:
        return int(
            c.execute(
                "SELECT COUNT(*) AS n FROM audit_log WHERE event_type=?",
                (event_type,),
            ).fetchone()["n"]
        )
    finally:
        c.close()


def _fake_submit(outcome: str):
    def submit(candidate, *, repo_root, audit_conn, session_date, history_root):
        return CanaryValidationResult(
            candidate_id=candidate.candidate_id,
            outcome=outcome,  # type: ignore[arg-type]
            canary_run_id="run-123" if outcome in ("passed", "failed") else None,
            candidate_rev="cand" if outcome in ("passed", "failed") else None,
            baseline_rev="base" if outcome in ("passed", "failed") else None,
            failing_metrics=("llm_cost_regression_pct",) if outcome == "failed" else (),
            skip_reason="no_replay_data" if outcome == "skipped" else None,
            promoted=False,
        )

    return submit


def _run(setup, outcome):
    db_path, thresh, tunables = setup
    return run_tuner(
        db_path=db_path,
        thresholds_path=thresh,
        tunables_path=tunables,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="apply",
        now=OFFHOURS,
        output_root=thresh.parent / "reports",
        submit_fn=_fake_submit(outcome),
    ), db_path, thresh


@pytest.mark.parametrize("outcome", ["passed", "failed", "skipped"])
def test_pipeline_records_candidate_and_validation(setup, outcome):
    result, db_path, thresh = _run(setup, outcome)
    assert len(result.canary_candidates) == 1
    assert len(result.canary_validations) == 1
    assert result.canary_validations[0].outcome == outcome
    assert result.canary_validations[0].promoted is False
    # 감사: CANDIDATE + VALIDATED 각 1건.
    assert _count(db_path, "AUTO_TUNED_CANARY_CANDIDATE") == 1
    assert _count(db_path, "AUTO_TUNED_CANARY_VALIDATED") == 1
    # 리포트 검증 섹션.
    report = json.loads(
        (thresh.parent / "reports" / "2026-05-24" / "auto-tuner-report.json").read_text()
    )
    assert report["canary_validations"][0]["outcome"] == outcome
    assert report["canary_validations"][0]["promoted"] is False
    assert report["canary_validations"][0]["promotion"].startswith("operator-gated")


def test_pipeline_idempotent(setup):
    db_path, thresh, tunables = setup
    common = dict(
        db_path=db_path,
        thresholds_path=thresh,
        tunables_path=tunables,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="apply",
        now=OFFHOURS,
        submit_fn=_fake_submit("passed"),
    )
    run_tuner(**common)
    c_first = _count(db_path, "AUTO_TUNED_CANARY_CANDIDATE")
    v_first = _count(db_path, "AUTO_TUNED_CANARY_VALIDATED")
    run_tuner(**common)
    # 재실행 시 중복 후보·검증 기록 없음.
    assert _count(db_path, "AUTO_TUNED_CANARY_CANDIDATE") == c_first
    assert _count(db_path, "AUTO_TUNED_CANARY_VALIDATED") == v_first
