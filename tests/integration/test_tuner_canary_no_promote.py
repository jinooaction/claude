"""스펙 012 T026 — 안전 불변: 검증은 승격이 아니다 (SC-C12-03·04, FR-C12-07).

캐너리 합격 후보가 있어도 배포/승격 이벤트 0건, promoted 항상 False, 튜닝 config
working-tree 무변경.
"""

from __future__ import annotations

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

_PROMOTE_EVENTS = (
    "STRATEGY_PROMOTED",
    "DEPLOY_STARTED",
    "DEPLOY_COMPLETED",
    "DEPLOY_FAILED",
    "DEPLOY_ROLLED_BACK",
    "DEPLOY_KERNEL_TOUCHED",
)


def _row(ts: str) -> TokenUsage:
    return TokenUsage(
        model="claude-opus-4-7",
        decision_class="x",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=50,
        cache_write_tokens=0,
        cost_usd="0.001000",
        latency_ms=3000,  # Tier C → latency_degradation → L2 후보
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


def _passed_submit(candidate, *, repo_root, audit_conn, session_date, history_root):
    return CanaryValidationResult(
        candidate_id=candidate.candidate_id,
        outcome="passed",
        canary_run_id="run-xyz",
        candidate_rev="cand",
        baseline_rev="base",
        promoted=False,
    )


def test_passed_candidate_does_not_promote(setup):
    db_path, thresh, tunables = setup
    before_tunables = tunables.read_text(encoding="utf-8")

    result = run_tuner(
        db_path=db_path,
        thresholds_path=thresh,
        tunables_path=tunables,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="apply",
        now=OFFHOURS,
        submit_fn=_passed_submit,
    )

    # 합격 후보 존재.
    assert any(v.outcome == "passed" for v in result.canary_validations)
    # (a) 배포/승격 이벤트 0건.
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    try:
        for ev in _PROMOTE_EVENTS:
            n = c.execute(
                "SELECT COUNT(*) AS n FROM audit_log WHERE event_type=?", (ev,)
            ).fetchone()["n"]
            assert n == 0, f"{ev} must not be emitted"
        # (d) 모든 VALIDATED 이벤트 promoted=False.
        rows = c.execute(
            "SELECT payload_json FROM audit_log WHERE event_type='AUTO_TUNED_CANARY_VALIDATED'"
        ).fetchall()
        assert rows
        import json

        for r in rows:
            assert json.loads(r["payload_json"])["promoted"] is False
    finally:
        c.close()

    # (b) 튜닝 config working-tree 무변경.
    assert tunables.read_text(encoding="utf-8") == before_tunables
    # 결과 객체상으로도 promoted 전부 False.
    assert all(v.promoted is False for v in result.canary_validations)
