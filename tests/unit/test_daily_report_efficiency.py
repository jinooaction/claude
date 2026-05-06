"""Tests for the daily-report Token Efficiency section (T205)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from auto_invest.persistence import db
from auto_invest.reports.daily import build_report, render_json, render_markdown
from auto_invest.telemetry.store import TokenUsage, append_token_usage
from auto_invest.telemetry.thresholds import load_thresholds


@pytest.fixture
def conn(tmp_path: Path):
    path = tmp_path / "test.db"
    c = db.get_connection(path)
    db.migrate(c)
    yield c
    c.close()


@pytest.fixture
def tiers():
    return load_thresholds(Path("config/llm_kpi_thresholds.toml"))


def _u(ts: str, **kw) -> TokenUsage:
    return TokenUsage(
        model=kw.pop("model", "claude-opus-4-7"),
        decision_class=kw.pop("decision_class", "news"),
        input_tokens=kw.pop("inp", 100),
        output_tokens=kw.pop("out", 50),
        cache_read_tokens=kw.pop("cr", 200),
        cache_write_tokens=kw.pop("cw", 0),
        cost_usd=kw.pop("cost", "0.001000"),
        latency_ms=kw.pop("latency", 500),
        error_class=None,
        correlation_id=ts,
        ts_utc=ts,
    )


def test_zero_calls_renders_no_llm_section(conn: sqlite3.Connection, tiers):
    rep = build_report(conn, session_date="2026-05-01", tiers=tiers)
    md = render_markdown(rep)
    assert "## Token Efficiency" in md
    assert "(no LLM calls today)" in md


def test_no_tiers_omits_section_payload(conn: sqlite3.Connection):
    rep = build_report(conn, session_date="2026-05-01")
    assert rep.efficiency is None


def test_populated_session_renders_kpis(conn: sqlite3.Connection, tiers):
    append_token_usage(conn, _u("2026-05-01T10:00:00.000Z", inp=50, cr=450))
    append_token_usage(conn, _u("2026-05-01T11:00:00.000Z", inp=50, cr=450))
    rep = build_report(conn, session_date="2026-05-01", tiers=tiers)
    md = render_markdown(rep)
    assert "cache_hit_rate" in md
    assert "Tier" in md
    # JSON sibling carries the structured KPIs
    j = json.loads(render_json(rep))
    assert j["efficiency"] is not None
    kpi_names = {k["name"] for k in j["efficiency"]["kpis"]}
    assert "cache_hit_rate" in kpi_names
    assert "tokens_per_decision_p95" in kpi_names


def test_per_decision_class_listed(conn: sqlite3.Connection, tiers):
    append_token_usage(conn, _u("2026-05-01T10:00:00.000Z", decision_class="news"))
    append_token_usage(
        conn, _u("2026-05-01T11:00:00.000Z", decision_class="volatility")
    )
    rep = build_report(conn, session_date="2026-05-01", tiers=tiers)
    md = render_markdown(rep)
    assert "news" in md
    assert "volatility" in md
