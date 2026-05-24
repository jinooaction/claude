"""스펙 005 — 탐지 규칙 (SC-A01 결정성, 안정성 판정, 엣지)."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from auto_invest.persistence import db
from auto_invest.telemetry.store import TokenUsage, append_token_usage
from auto_invest.telemetry.thresholds import load_thresholds
from auto_invest.tuner.detect import detect

AS_OF = date(2026, 5, 24)
THRESH = "config/llm_kpi_thresholds.toml"


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "detect.db")
    db.migrate(c)
    yield c
    c.close()


@pytest.fixture
def tiers():
    return load_thresholds(Path(THRESH))


def _row(
    ts: str, *, latency: int = 1500, cost: str = "0.001000", inp: int = 100, cr: int = 0
) -> TokenUsage:
    return TokenUsage(
        model="claude-opus-4-7",
        decision_class="x",
        input_tokens=inp,
        output_tokens=50,
        cache_read_tokens=cr,
        cache_write_tokens=0,
        cost_usd=cost,
        latency_ms=latency,
        error_class=None,
        correlation_id=ts,
        ts_utc=ts,
    )


def _seed_stable_latency_b(conn: sqlite3.Connection, n: int = 25) -> None:
    """n 일에 걸쳐 latency=1500(Tier B), 다른 KPI 는 Tier A 인 행을 심는다."""
    for offset in range(n):
        d = date(2026, 5, 24)
        d = d.fromordinal(d.toordinal() - offset)
        ts = f"{d.isoformat()}T15:00:00.000Z"
        append_token_usage(conn, _row(ts, latency=1500))


def test_threshold_tighten_fires_on_stable_b(conn, tiers) -> None:
    _seed_stable_latency_b(conn, 25)
    cands = detect(conn, as_of=AS_OF, tiers=tiers, thresholds_path=THRESH)
    tighten = [c for c in cands if c.detection_rule == "threshold_tighten"]
    assert any(c.kpi_name == "latency_p95_ms" for c in tighten)
    lat = next(c for c in tighten if c.kpi_name == "latency_p95_ms")
    assert lat.observed_tier == "B"
    assert lat.proposed.kind == "threshold_tighten"
    assert lat.proposed.config_key == "latency_p95_ms.tier_b"
    assert lat.proposed.target_paths == (THRESH,)
    # tier_b 2000 → tier_a 800 쪽으로 20% = 2000-240 = 1760
    assert lat.proposed.old_value == "2000"
    assert lat.proposed.new_value == "1760"
    assert lat.measurement_sample == 25


def test_single_tier_c_day_breaks_stability(conn, tiers) -> None:
    """단 하나의 Tier C 일이 있으면 조이기 후보 미생성 (엣지)."""
    _seed_stable_latency_b(conn, 25)
    # 한 날을 Tier C(4000ms) 로 추가.
    append_token_usage(conn, _row("2026-05-10T15:00:00.000Z", latency=4000))
    cands = detect(conn, as_of=AS_OF, tiers=tiers, thresholds_path=THRESH)
    tighten = [
        c
        for c in cands
        if c.detection_rule == "threshold_tighten" and c.kpi_name == "latency_p95_ms"
    ]
    assert tighten == []


def test_empty_window_no_candidates(conn, tiers) -> None:
    cands = detect(conn, as_of=AS_OF, tiers=tiers, thresholds_path=THRESH)
    assert cands == []


def test_drift_proposal_recorded_no_apply_path(conn, tiers) -> None:
    """7일 cache_hit_rate 가 낮으면 proposal_only 후보(적용 노브 없음)."""
    # cache_hit_rate 매우 낮게: cr=0 → ratio 0 → N/A(Tier C 이하).
    for offset in range(5):
        d = date(2026, 5, 24)
        d = d.fromordinal(d.toordinal() - offset)
        append_token_usage(conn, _row(f"{d.isoformat()}T15:00:00.000Z", cr=0))
    cands = detect(conn, as_of=AS_OF, tiers=tiers, thresholds_path=THRESH)
    cache = [c for c in cands if c.detection_rule == "cache_miss"]
    assert cache, "cache_miss drift 후보가 있어야 함"
    assert cache[0].proposed.kind == "proposal_only"
    assert cache[0].proposed.target_paths == ()


def test_detect_deterministic(conn, tiers) -> None:
    """같은 입력 → 같은 후보 (SC-A01)."""
    _seed_stable_latency_b(conn, 25)
    a = detect(conn, as_of=AS_OF, tiers=tiers, thresholds_path=THRESH)
    b = detect(conn, as_of=AS_OF, tiers=tiers, thresholds_path=THRESH)
    assert a == b
