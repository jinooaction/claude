"""Spec 011 — `auto-invest performance` CLI 통합 테스트.

검증:
  - 합성 페이퍼 체결 DB 로 실현 손익이 정확히 출력 (--no-marks).
  - JSON 출력이 스키마 버전을 포함.
  - DB 없을 때 exit 1, 잘못된 시각 exit 2.
  - read-only — 명령 실행 후 audit_log row 수 불변 (SC-005).
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    OrderPaperFilledPayload,
    PaperRunStartedPayload,
)

runner = CliRunner()


def _seed_paper_round(db_path: Path) -> int:
    conn = db.get_connection(db_path)
    db.migrate(conn)
    sid = audit.append(
        conn,
        PaperRunStartedPayload(
            pid=1, config_path="/x", ruleset_sha256="a" * 64,
            started_at_utc="2026-05-20T00:00:00.000Z", host="t",
        ),
    )
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="R", symbol="AAPL", side="BUY", qty=1,
            simulated_fill_price_usd="100.00", quote_source="ask",
            correlation_id="c1", paper_session_id=sid,
        ),
        rule_id="R", symbol="AAPL", correlation_id="c1",
    )
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="R", symbol="AAPL", side="SELL", qty=1,
            simulated_fill_price_usd="115.00", quote_source="bid",
            correlation_id="c2", paper_session_id=sid,
        ),
        rule_id="R", symbol="AAPL", correlation_id="c2",
    )
    count = conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    conn.close()
    return count


def test_realized_pnl_json(tmp_path: Path):
    db_path = tmp_path / "perf.db"
    before = _seed_paper_round(db_path)
    result = runner.invoke(
        app,
        [
            "performance", "--db", str(db_path),
            "--since", "2000-01-01T00:00:00Z",
            "--mode", "paper", "--no-marks", "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1.2"
    assert payload["mode"] == "paper"
    assert payload["realized_pnl_usd"] == "15.00"  # (115-100)*1
    assert payload["total_pnl_usd"] == "15.00"
    # read-only: row 수 불변
    conn = db.get_connection(db_path)
    after = conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    conn.close()
    assert after == before


def test_text_output(tmp_path: Path):
    db_path = tmp_path / "perf.db"
    _seed_paper_round(db_path)
    result = runner.invoke(
        app,
        [
            "performance", "--db", str(db_path),
            "--since", "2000-01-01T00:00:00Z", "--no-marks",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "auto-invest performance" in result.stdout
    assert "Realized" in result.stdout


def test_missing_db_exits_1(tmp_path: Path):
    result = runner.invoke(
        app,
        ["performance", "--db", str(tmp_path / "nope.db"), "--since", "2000-01-01T00:00:00Z"],
    )
    assert result.exit_code == 1


def test_bad_timestamp_exits_2(tmp_path: Path):
    db_path = tmp_path / "perf.db"
    _seed_paper_round(db_path)
    result = runner.invoke(
        app,
        ["performance", "--db", str(db_path), "--since", "not-a-time"],
    )
    assert result.exit_code == 2


def test_bad_mode_exits_2(tmp_path: Path):
    db_path = tmp_path / "perf.db"
    _seed_paper_round(db_path)
    result = runner.invoke(
        app,
        ["performance", "--db", str(db_path), "--since", "2000-01-01T00:00:00Z", "--mode", "x"],
    )
    assert result.exit_code == 2


def test_empty_period_no_crash(tmp_path: Path):
    db_path = tmp_path / "perf.db"
    _seed_paper_round(db_path)
    # 체결이 없는 미래 구간.
    result = runner.invoke(
        app,
        [
            "performance", "--db", str(db_path),
            "--since", "2099-01-01T00:00:00Z", "--no-marks", "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["fills_count"] == 0
    assert payload["return_pct"] is None
    assert payload["risk"] is None  # 청산 없음 → 위험조정 N/A


def test_window_option_json_has_risk(tmp_path: Path):
    """--window 로 롤링 기간을 지정하면 위험조정 지표가 JSON 에 채워진다 (US2)."""
    db_path = tmp_path / "perf.db"
    _seed_paper_round(db_path)
    # 시드 체결의 ts_utc 는 삽입 시각(now). 종료=now, 넉넉한 윈도우로 전부 포함.
    result = runner.invoke(
        app,
        [
            "performance", "--db", str(db_path),
            "--window", "3650d",
            "--no-marks", "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    risk = payload["risk"]
    assert risk is not None
    assert risk["closed_trades"] == 1
    assert risk["win_rate"] == "1"  # 1승 0패
    assert risk["starting_capital_usd"] == "100.00"  # gross_invested 대용


def test_capital_override_in_json(tmp_path: Path):
    db_path = tmp_path / "perf.db"
    _seed_paper_round(db_path)
    result = runner.invoke(
        app,
        [
            "performance", "--db", str(db_path),
            "--since", "2000-01-01T00:00:00Z", "--capital", "1000",
            "--no-marks", "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["risk"]["starting_capital_usd"] == "1000.0"


def test_since_and_window_conflict_exits_2(tmp_path: Path):
    db_path = tmp_path / "perf.db"
    _seed_paper_round(db_path)
    result = runner.invoke(
        app,
        [
            "performance", "--db", str(db_path),
            "--since", "2000-01-01T00:00:00Z", "--window", "30d",
        ],
    )
    assert result.exit_code == 2


def test_neither_since_nor_window_exits_2(tmp_path: Path):
    db_path = tmp_path / "perf.db"
    _seed_paper_round(db_path)
    result = runner.invoke(app, ["performance", "--db", str(db_path)])
    assert result.exit_code == 2
