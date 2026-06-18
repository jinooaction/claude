from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from auto_invest.cli import _assert_autonomous_write_allowed
from auto_invest.persistence import db
from auto_invest.safety.autonomy import AutonomyLevel
from auto_invest.safety.boundary import SafetyBoundaryError
from auto_invest.tuner.canary_submit import submit_to_canary
from auto_invest.tuner.models import (
    CanaryCandidate,
    CandidateChange,
    Classification,
    ProposedChange,
)
from auto_invest.tuner.runner import run_tuner


def _candidate(target_path: str) -> CandidateChange:
    return CandidateChange(
        candidate_id="cand-a6",
        detection_rule="unit",
        kpi_name="latency_p95_ms",
        observed_value="2000",
        observed_tier="C",
        window="7d",
        proposed=ProposedChange(
            kind="threshold_tighten",
            target_paths=(target_path,),
            config_key="latency_p95_ms.tier_b",
            old_value="2200",
            new_value="1760",
        ),
        rationale="unit",
        measurement_sample=30,
    )


def test_tuner_blocks_a6_candidate_before_apply(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "t.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    conn.close()

    cand = _candidate("src/auto_invest/config/whitelist.py")
    classification = Classification(candidate=cand, tier="L1", reason="unit")

    monkeypatch.setattr("auto_invest.tuner.runner.load_thresholds", lambda _p: object())
    monkeypatch.setattr("auto_invest.tuner.runner.detect", lambda *a, **k: (cand,))
    monkeypatch.setattr(
        "auto_invest.tuner.runner.classify_all",
        lambda *a, **k: (classification,),
    )

    result = run_tuner(
        db_path=db_path,
        thresholds_path=tmp_path / "thresholds.toml",
        kernel_path=None,
        as_of=date(2026, 6, 18),
        mode="apply",
        now=None,
    )

    assert result.applied == ()
    assert result.skipped == (("cand-a6", "safety_boundary"),)


def test_tuner_canary_submit_blocks_a6_ephemeral_commit(tmp_path: Path) -> None:
    candidate = CanaryCandidate(
        candidate_id="cand-canary-a6",
        detection_rule="unit",
        authority_tier="L2",
        target_path="src/auto_invest/config/whitelist.py",
        config_key="x.max_tokens",
        old_value="1000",
        new_value="900",
        recommended_tier="L2",
        recommended_window_days=30,
        measurement_sample=30,
        rationale="unit",
    )

    result = submit_to_canary(
        candidate,
        repo_root=tmp_path,
        audit_conn=sqlite3.connect(":memory:"),
        session_date="2026-06-18",
        history_root=tmp_path,
        replay_factory=lambda *args: object(),  # type: ignore[return-value]
    )

    assert result.outcome == "skipped"
    assert result.skip_reason == "safety_boundary"
    assert result.candidate_rev is None


def test_cli_write_boundary_helper_blocks_protected_path() -> None:
    with pytest.raises(SafetyBoundaryError):
        _assert_autonomous_write_allowed(
            summary="unit write protected whitelist",
            paths=("src/auto_invest/config/whitelist.py",),
            requested_level=AutonomyLevel.STRATEGY_REASSIGNMENT,
        )


def test_cli_write_boundary_helper_allows_non_boundary_path() -> None:
    _assert_autonomous_write_allowed(
        summary="unit write ordinary sidecar",
        paths=("automation/reassign-last-run/LAST_RUN.md",),
        requested_level=AutonomyLevel.PROPOSAL,
    )
