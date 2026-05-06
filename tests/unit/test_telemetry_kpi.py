"""Tests for `auto_invest.telemetry.kpi` (T201)."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.persistence import db
from auto_invest.telemetry.kpi import compute_snapshot
from auto_invest.telemetry.store import TokenUsage, _utcnow_iso_ms, append_token_usage
from auto_invest.telemetry.thresholds import load_thresholds


@pytest.fixture
def conn(tmp_path: Path):
    path = tmp_path / "kpi.db"
    c = db.get_connection(path)
    db.migrate(c)
    yield c
    c.close()


@pytest.fixture
def tiers():
    return load_thresholds(Path("config/llm_kpi_thresholds.toml"))


def _seed(conn: sqlite3.Connection, *usages: TokenUsage) -> None:
    for u in usages:
        append_token_usage(conn, u)


def _u(
    *,
    ts: str,
    decision_class: str | None = "x",
    inp: int = 100,
    out: int = 50,
    cr: int = 0,
    cw: int = 0,
    cost: str | None = "0.001000",
    latency: int = 1000,
) -> TokenUsage:
    return TokenUsage(
        model="claude-opus-4-7",
        decision_class=decision_class,
        input_tokens=inp,
        output_tokens=out,
        cache_read_tokens=cr,
        cache_write_tokens=cw,
        cost_usd=cost,
        latency_ms=latency,
        error_class=None,
        correlation_id=ts,
        ts_utc=ts,
    )


def test_empty_window_returns_zero_counters(conn: sqlite3.Connection, tiers):
    snap = compute_snapshot(
        conn,
        window_start_utc="2026-05-01T00:00:00.000Z",
        window_end_utc="2026-05-02T00:00:00.000Z",
        tiers=tiers,
    )
    assert snap.call_count == 0
    assert snap.per_decision_class == {}
    assert snap.top_n_calls == []
    for k in snap.kpis:
        assert k.tier == "N/A"
        assert k.value == Decimal(0)


def test_cache_hit_rate_math(conn: sqlite3.Connection, tiers):
    # Two calls: total cache_read=900, total input=100 -> hit rate = 900/1000 = 0.9 -> Tier A
    _seed(
        conn,
        _u(ts="2026-05-01T10:00:00.000Z", inp=50, cr=450),
        _u(ts="2026-05-01T11:00:00.000Z", inp=50, cr=450),
    )
    snap = compute_snapshot(
        conn,
        window_start_utc="2026-05-01T00:00:00.000Z",
        window_end_utc="2026-05-02T00:00:00.000Z",
        tiers=tiers,
    )
    assert snap.call_count == 2
    cache_kpi = next(k for k in snap.kpis if k.name == "cache_hit_rate")
    assert cache_kpi.value == Decimal("0.9000")
    assert cache_kpi.tier == "A"


def test_per_decision_class_aggregation(conn: sqlite3.Connection, tiers):
    _seed(
        conn,
        _u(ts="2026-05-01T10:00:00.000Z", decision_class="news", inp=100),
        _u(ts="2026-05-01T11:00:00.000Z", decision_class="news", inp=200),
        _u(ts="2026-05-01T12:00:00.000Z", decision_class=None, inp=50),
    )
    snap = compute_snapshot(
        conn,
        window_start_utc="2026-05-01T00:00:00.000Z",
        window_end_utc="2026-05-02T00:00:00.000Z",
        tiers=tiers,
    )
    assert "news" in snap.per_decision_class
    assert "(unclassified)" in snap.per_decision_class
    assert snap.per_decision_class["news"]["count"] == 2
    assert snap.per_decision_class["(unclassified)"]["count"] == 1


def test_top_n_ordered_by_cost_desc(conn: sqlite3.Connection, tiers):
    _seed(
        conn,
        _u(ts="2026-05-01T10:00:00.000Z", cost="0.001"),
        _u(ts="2026-05-01T11:00:00.000Z", cost="0.010"),
        _u(ts="2026-05-01T12:00:00.000Z", cost="0.005"),
    )
    snap = compute_snapshot(
        conn,
        window_start_utc="2026-05-01T00:00:00.000Z",
        window_end_utc="2026-05-02T00:00:00.000Z",
        tiers=tiers,
        top_n=3,
    )
    costs = [c["cost_usd"] for c in snap.top_n_calls]
    assert costs == ["0.010", "0.005", "0.001"]


def test_window_excludes_outside_rows(conn: sqlite3.Connection, tiers):
    _seed(
        conn,
        _u(ts="2026-04-30T23:59:59.999Z"),  # before
        _u(ts="2026-05-01T00:00:00.000Z"),  # inside (>= start)
        _u(ts="2026-05-02T00:00:00.000Z"),  # outside (>= end)
    )
    snap = compute_snapshot(
        conn,
        window_start_utc="2026-05-01T00:00:00.000Z",
        window_end_utc="2026-05-02T00:00:00.000Z",
        tiers=tiers,
    )
    assert snap.call_count == 1


def test_deterministic_for_same_input(conn: sqlite3.Connection, tiers):
    _seed(
        conn,
        _u(ts="2026-05-01T10:00:00.000Z", cost="0.001000"),
        _u(ts="2026-05-01T11:00:00.000Z", cost="0.002000"),
    )
    a = compute_snapshot(
        conn,
        window_start_utc="2026-05-01T00:00:00.000Z",
        window_end_utc="2026-05-02T00:00:00.000Z",
        tiers=tiers,
    )
    b = compute_snapshot(
        conn,
        window_start_utc="2026-05-01T00:00:00.000Z",
        window_end_utc="2026-05-02T00:00:00.000Z",
        tiers=tiers,
    )
    assert a.kpis == b.kpis
    assert a.per_decision_class == b.per_decision_class
    assert a.top_n_calls == b.top_n_calls


def _utcnow_test_ts():
    """Used by ad-hoc seeding when ts ordering is irrelevant."""
    return _utcnow_iso_ms()
