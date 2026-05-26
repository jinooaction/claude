"""스펙 012 T027 — 결정론·dry-run 무변경 (SC-C12-05)."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from auto_invest.persistence import db
from auto_invest.telemetry.store import TokenUsage, append_token_usage
from auto_invest.tuner.runner import run_tuner

AS_OF = date(2026, 5, 24)
SRC_THRESH = Path("config/llm_kpi_thresholds.toml")
SRC_TUNABLES = Path("config/judgment_tunables.toml")
KERNEL = Path(".specify/memory/kernel.toml")


def _row(ts: str) -> TokenUsage:
    return TokenUsage(
        model="claude-opus-4-7",
        decision_class="x",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=50,
        cache_write_tokens=0,
        cost_usd="0.001000",
        latency_ms=3000,
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


def _ids(result):
    return sorted(c.candidate_id for c in result.canary_candidates)


def test_dry_run_deterministic_and_no_change(setup):
    db_path, thresh, tunables = setup
    before_tunables = tunables.read_text(encoding="utf-8")
    common = dict(
        db_path=db_path,
        thresholds_path=thresh,
        tunables_path=tunables,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="dry_run",
    )

    r1 = run_tuner(**common)
    r2 = run_tuner(**common)

    # 결정론: 같은 후보 집합.
    assert _ids(r1) == _ids(r2)
    assert len(r1.canary_candidates) >= 1
    # dry-run 무변경: config 불변, 감사 0건.
    assert tunables.read_text(encoding="utf-8") == before_tunables
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    try:
        n = c.execute(
            "SELECT COUNT(*) AS n FROM audit_log WHERE event_type LIKE 'AUTO_TUN%'"
        ).fetchone()["n"]
        assert n == 0
    finally:
        c.close()
    # 검증도 0건(dry-run 은 캐너리 미투입).
    assert r1.canary_validations == ()
