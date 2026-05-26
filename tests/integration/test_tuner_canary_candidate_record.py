"""스펙 012 T014 — 캐너리 후보 기록 (US1): 감사+리포트, 멱등, dry-run 무변경."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from auto_invest.persistence import db
from auto_invest.telemetry.store import TokenUsage, append_token_usage
from auto_invest.tuner.runner import run_tuner

AS_OF = date(2026, 5, 24)
OFFHOURS = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)  # 토요일 휴장
SRC_THRESH = Path("config/llm_kpi_thresholds.toml")
SRC_TUNABLES = Path("config/judgment_tunables.toml")
KERNEL = Path(".specify/memory/kernel.toml")


def _row(ts: str) -> TokenUsage:
    # latency=3000 → latency_p95_ms Tier C (드리프트), cache_read=0 → cache_hit_rate Tier C.
    return TokenUsage(
        model="claude-opus-4-7",
        decision_class="x",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=0,
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


def test_apply_records_canary_candidate(setup):
    db_path, thresh, tunables = setup
    result = run_tuner(
        db_path=db_path,
        thresholds_path=thresh,
        tunables_path=tunables,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="apply",
        now=OFFHOURS,
        output_root=thresh.parent / "reports",
    )
    # latency_degradation → daily_summary.max_tokens 축소 후보 1건.
    assert len(result.canary_candidates) == 1
    cand = result.canary_candidates[0]
    assert cand.detection_rule == "latency_degradation"
    assert cand.config_key == "daily_summary.max_tokens"
    assert cand.old_value == "700"
    assert cand.recommended_tier == "L2"
    # 감사 기록 1건.
    assert _count(db_path, "AUTO_TUNED_CANARY_CANDIDATE") == 1
    # 리포트 파일에 섹션 존재.
    report = thresh.parent / "reports" / "2026-05-24" / "auto-tuner-report.json"
    assert report.exists()
    assert '"canary_candidates"' in report.read_text(encoding="utf-8")


def test_apply_is_idempotent(setup):
    db_path, thresh, tunables = setup
    common = dict(
        db_path=db_path,
        thresholds_path=thresh,
        tunables_path=tunables,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="apply",
        now=OFFHOURS,
    )
    run_tuner(**common)
    first = _count(db_path, "AUTO_TUNED_CANARY_CANDIDATE")
    r2 = run_tuner(**common)
    assert _count(db_path, "AUTO_TUNED_CANARY_CANDIDATE") == first  # 중복 없음
    assert any(
        reason == "already_validated_this_session" for _, reason in r2.skipped
    )


def test_dry_run_changes_nothing(setup):
    db_path, thresh, tunables = setup
    before_tunables = tunables.read_text(encoding="utf-8")
    result = run_tuner(
        db_path=db_path,
        thresholds_path=thresh,
        tunables_path=tunables,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="dry_run",
    )
    # 후보는 분석됨.
    assert len(result.canary_candidates) == 1
    # 그러나 감사·config 무변경.
    assert _count(db_path, "AUTO_TUNED_CANARY_CANDIDATE") == 0
    assert tunables.read_text(encoding="utf-8") == before_tunables


def test_cache_miss_stays_proposal_only(setup):
    # cache_miss 는 max_tokens 노브가 아니다 → 캐너리 후보로 구체화되지 않고
    # 기존 동작(L1 intent, 적용 경로 없음)대로 no_apply_path 로 스킵된다.
    db_path, thresh, tunables = setup
    result = run_tuner(
        db_path=db_path,
        thresholds_path=thresh,
        tunables_path=tunables,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="apply",
        now=OFFHOURS,
    )
    candidate_rules = {c.detection_rule for c in result.canary_candidates}
    assert "cache_miss" not in candidate_rules
    # cache_miss 후보는 스킵(적용 경로 없음)으로 남는다.
    skipped_ids = {cid for cid, _ in result.skipped}
    assert any("cache_miss" in cid for cid in skipped_ids)
