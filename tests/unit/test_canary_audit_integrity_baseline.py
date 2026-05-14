"""Spec 007 T024 — audit-integrity baseline-mean (FR-C01 #3).

The lookback computation is the canary's defence against
"slowly accumulating data-quality issues that PnL hides". We compute
the running mean of ``DATA_QUALITY_ISSUE`` rows over the previous
N calendar days and use it as the floor; the candidate's count during
window replay is then compared against that floor.

In v1 the canary's hard rule is ``audit_integrity_failures = 0`` (FR-C01
pins the band at 0), so the baseline-mean is informational. This test
suite ensures the helper returns the right numbers — a future v2 may
soften FR-C01 to ``observed <= baseline_mean`` which would make this
function load-bearing.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from auto_invest.canary.metrics import compute_audit_integrity_baseline_mean
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import DataQualityIssuePayload


def _utc_ms(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _seed_data_quality_rows(conn, *, count: int, day: date) -> None:
    """Append ``count`` DATA_QUALITY_ISSUE rows at noon UTC on ``day``."""
    ts = datetime.combine(day, datetime.min.time()).replace(
        hour=12, tzinfo=UTC
    )
    for i in range(count):
        audit.append(
            conn,
            DataQualityIssuePayload(issue="test", detail={"i": i}),
            ts_utc=_utc_ms(ts),
        )
    conn.commit()


def test_no_prior_rows_returns_zero(tmp_path: Path) -> None:
    conn = db.get_connection(tmp_path / "audit.db")
    db.migrate(conn)
    try:
        mean = compute_audit_integrity_baseline_mean(
            audit_conn=conn,
            baseline_window_end=date(2026, 5, 14),
            lookback_days=30,
        )
        assert mean == 0.0
    finally:
        conn.close()


def test_seeded_rows_produce_correct_mean(tmp_path: Path) -> None:
    """30 rows over 30 days = mean of 1.0 per day."""
    conn = db.get_connection(tmp_path / "audit.db")
    db.migrate(conn)
    try:
        anchor = date(2026, 5, 14)
        for i in range(30):
            _seed_data_quality_rows(
                conn, count=1, day=anchor - timedelta(days=i + 1)
            )

        mean = compute_audit_integrity_baseline_mean(
            audit_conn=conn,
            baseline_window_end=anchor,
            lookback_days=30,
        )
        assert mean == 1.0
    finally:
        conn.close()


def test_rows_outside_lookback_window_excluded(tmp_path: Path) -> None:
    """A spike OUTSIDE the lookback window does not bias the mean."""
    conn = db.get_connection(tmp_path / "audit.db")
    db.migrate(conn)
    try:
        anchor = date(2026, 5, 14)
        # 100 rows 60 days ago — outside a 30-day lookback.
        _seed_data_quality_rows(
            conn, count=100, day=anchor - timedelta(days=60)
        )
        # 3 rows inside the lookback.
        _seed_data_quality_rows(
            conn, count=3, day=anchor - timedelta(days=5)
        )

        mean = compute_audit_integrity_baseline_mean(
            audit_conn=conn,
            baseline_window_end=anchor,
            lookback_days=30,
        )
        # 3 rows over 30 days = 0.1
        assert mean == 0.1
    finally:
        conn.close()


def test_anchor_day_itself_excluded_from_lookback(tmp_path: Path) -> None:
    """Rows ON the baseline_window_end date are NOT counted (half-open interval)."""
    conn = db.get_connection(tmp_path / "audit.db")
    db.migrate(conn)
    try:
        anchor = date(2026, 5, 14)
        _seed_data_quality_rows(conn, count=10, day=anchor)
        mean = compute_audit_integrity_baseline_mean(
            audit_conn=conn,
            baseline_window_end=anchor,
            lookback_days=30,
        )
        assert mean == 0.0
    finally:
        conn.close()
