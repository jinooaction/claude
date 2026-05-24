"""스펙 005 — 자율 튜너 end-to-end (SC-A03·A04·A06·A07·A08)."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.persistence import db
from auto_invest.telemetry.store import TokenUsage, append_token_usage
from auto_invest.telemetry.thresholds import load_thresholds
from auto_invest.tuner.runner import run_tuner

AS_OF = date(2026, 5, 24)
OFFHOURS = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)  # 토요일, 휴장
MARKET_OPEN = datetime(2026, 5, 26, 15, 0, tzinfo=UTC)  # 화요일 장중
SRC_THRESH = Path("config/llm_kpi_thresholds.toml")
KERNEL = Path(".specify/memory/kernel.toml")


def _row(ts: str, latency: int = 1500) -> TokenUsage:
    return TokenUsage(
        model="claude-opus-4-7",
        decision_class="x",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=0,
        cache_write_tokens=0,
        cost_usd="0.001000",
        latency_ms=latency,
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
    shutil.copy(SRC_THRESH, thresh)
    return db_path, thresh


def _count_l1(db_path: Path) -> int:
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    try:
        return int(
            c.execute(
                "SELECT COUNT(*) AS n FROM audit_log WHERE event_type='AUTO_TUNED_L1'"
            ).fetchone()["n"]
        )
    finally:
        c.close()


def _count_auto_tuned(db_path: Path) -> int:
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    try:
        return int(
            c.execute(
                "SELECT COUNT(*) AS n FROM audit_log WHERE event_type LIKE 'AUTO_TUN%'"
            ).fetchone()["n"]
        )
    finally:
        c.close()


def test_dry_run_changes_nothing(setup) -> None:
    """dry-run: 설정 파일·감사 0 변경 (SC-A03)."""
    db_path, thresh = setup
    before_text = thresh.read_text(encoding="utf-8")
    before_mtime = thresh.stat().st_mtime_ns
    result = run_tuner(
        db_path=db_path,
        thresholds_path=thresh,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="dry_run",
        output_root=None,
    )
    assert thresh.read_text(encoding="utf-8") == before_text
    assert thresh.stat().st_mtime_ns == before_mtime
    assert _count_auto_tuned(db_path) == 0
    assert result.applied == ()
    # 후보는 분석됨(latency tighten 후보 존재).
    assert any(
        c.candidate.kpi_name == "latency_p95_ms" and c.tier == "L1"
        for c in result.candidates
    )


def test_apply_tightens_and_audits(setup) -> None:
    """apply(장외): tier_b 조여짐 + AUTO_TUNED_L1, applied↔감사 정합 (SC-A08)."""
    db_path, thresh = setup
    result = run_tuner(
        db_path=db_path,
        thresholds_path=thresh,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="apply",
        now=OFFHOURS,
        output_root=thresh.parent / "reports",
    )
    reloaded = load_thresholds(thresh)
    assert reloaded.entries["latency_p95_ms"].tier_b == Decimal(1760)
    assert len(result.applied) == _count_l1(db_path)
    assert len(result.applied) == 1
    assert result.applied[0].config_key == "latency_p95_ms.tier_b"
    # 리포트 파일 작성.
    report = thresh.parent / "reports" / "2026-05-24" / "auto-tuner-report.json"
    assert report.exists()


def test_apply_is_idempotent(setup) -> None:
    """같은 as-of 로 두 번 apply → 한 번만 적용·기록 (SC-A04)."""
    db_path, thresh = setup
    common = dict(
        db_path=db_path,
        thresholds_path=thresh,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="apply",
        now=OFFHOURS,
    )
    run_tuner(**common)
    first_count = _count_l1(db_path)
    first_text = thresh.read_text(encoding="utf-8")
    r2 = run_tuner(**common)
    assert _count_l1(db_path) == first_count  # 추가 기록 없음
    assert thresh.read_text(encoding="utf-8") == first_text  # 추가 변경 없음
    assert any(reason == "already_applied_this_session" for _, reason in r2.skipped)


def test_apply_blocked_during_market_hours(setup) -> None:
    """장중 apply → 적용 0, market_hours 스킵 (SC-A06)."""
    db_path, thresh = setup
    before = thresh.read_text(encoding="utf-8")
    result = run_tuner(
        db_path=db_path,
        thresholds_path=thresh,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="apply",
        now=MARKET_OPEN,
    )
    assert result.applied == ()
    assert thresh.read_text(encoding="utf-8") == before
    assert any(reason == "market_hours" for _, reason in result.skipped)


def test_apply_blocked_insufficient_measurement(setup) -> None:
    """표본 < min → 적용 0, insufficient_measurement 스킵 (SC-A07)."""
    db_path, thresh = setup
    result = run_tuner(
        db_path=db_path,
        thresholds_path=thresh,
        kernel_path=KERNEL,
        as_of=AS_OF,
        mode="apply",
        now=OFFHOURS,
        min_sample=999,
    )
    assert result.applied == ()
    assert any(reason == "insufficient_measurement" for _, reason in result.skipped)


def test_cli_dry_run_json(setup) -> None:
    """CLI dry-run --json 정상 종료 + JSON 출력."""
    db_path, thresh = setup
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "tune",
            "--dry-run",
            "--db",
            str(db_path),
            "--thresholds",
            str(thresh),
            "--kernel",
            str(KERNEL),
            "--as-of",
            "2026-05-24",
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    assert '"schema_version": "1.0"' in res.output
    assert '"mode": "dry_run"' in res.output
