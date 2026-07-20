"""Tests for hardened auto-tuner canary promotion gate."""

from __future__ import annotations

from datetime import UTC, datetime

from auto_invest.deploy.steps import canary_gate
from auto_invest.persistence import audit, db


def test_canary_gate_rejects_legacy_pass_without_ruleset_hash(tmp_path):
    db_path = tmp_path / "audit.sqlite"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        audit.append(
            conn,
            audit.CanaryPassedPayload(
                canary_run_id="cr1",
                candidate_rev="a" * 40,
                baseline_rev="b" * 40,
                tier="L2",
                finished_at="2026-07-21T00:00:00.000Z",
                artefact_path="/x",
            ),
            ts_utc="2026-07-21T00:00:00.000Z",
        )
        conn.commit()
    finally:
        conn.close()

    result = canary_gate(
        db_path,
        ruleset_sha256="c" * 64,
        code_sha256="a" * 40,
        now_fn=lambda: datetime(2026, 7, 21, 0, 1, tzinfo=UTC),
    )

    assert result.ok is False
    assert "candidate_rev and ruleset_sha256" in result.detail


def test_canary_gate_accepts_exact_code_and_ruleset_match(tmp_path):
    db_path = tmp_path / "audit.sqlite"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        audit.append(
            conn,
            audit.CanaryPassedPayload(
                canary_run_id="cr1",
                candidate_rev="a" * 40,
                ruleset_sha256="c" * 64,
                baseline_rev="b" * 40,
                tier="L2",
                finished_at="2026-07-21T00:00:00.000Z",
                artefact_path="/x",
            ),
            ts_utc="2026-07-21T00:00:00.000Z",
        )
        conn.commit()
    finally:
        conn.close()

    result = canary_gate(
        db_path,
        ruleset_sha256="c" * 64,
        code_sha256="a" * 40,
        now_fn=lambda: datetime(2026, 7, 21, 0, 1, tzinfo=UTC),
    )

    assert result.ok is True
