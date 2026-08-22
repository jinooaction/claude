from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import _load_portfolio_for_backtest, app
from auto_invest.performance.measurement_contract import (
    build_strategy_measurement_contract,
)
from auto_invest.performance.opening_positions import load_opening_positions
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import PortfolioNavSnapshotPayload

ROOT = Path(__file__).resolve().parents[2]
OPENING = ROOT / "deploy/live-opening-positions.toml"
PORTFOLIO = ROOT / "deploy/canary-live-portfolio.toml"
runner = CliRunner()


def _seed_ready_evidence(db_path: Path) -> int:
    _caps, _whitelist, portfolio = _load_portfolio_for_backtest(PORTFOLIO)
    contract = build_strategy_measurement_contract(
        load_opening_positions(OPENING),
        strategy_universe=portfolio.universe,
    )
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    conn = db.get_connection(db_path)
    db.migrate(conn)
    conn.execute(
        "INSERT INTO reconciliation_runs "
        "(started_at_utc, finished_at_utc, result) VALUES (?, ?, 'OK')",
        (now, now),
    )
    audit.append(
        conn,
        PortfolioNavSnapshotPayload(
            mode="live",
            schema_version="1.0",
            source="broker",
            computed_at_utc=now,
            cash_usd="293",
            total_market_value_usd="0",
            total_nav_usd="293",
            total_unrealized_pnl_usd="0",
            capital_basis_usd="293",
            measurement_contract_id=contract.contract_id,
            measurement_scope="strategy",
        ),
    )
    conn.commit()
    rows = conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    conn.close()
    return rows


def test_resume_readiness_is_read_only_and_does_not_clear_halt(tmp_path: Path) -> None:
    db_path = tmp_path / "auto_invest.db"
    before = _seed_ready_evidence(db_path)
    halt_path = tmp_path / "halt.flag"
    halt_path.write_text("reconciliation mismatch")

    result = runner.invoke(
        app,
        [
            "resume-readiness",
            "--db",
            str(db_path),
            "--halt-path",
            str(halt_path),
            "--opening-positions",
            str(OPENING),
            "--portfolio",
            str(PORTFOLIO),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "RESUME_ELIGIBLE"
    assert payload["orders_submitted"] == 0
    assert payload["halt_cleared"] is False
    assert halt_path.exists()
    conn = db.get_connection(db_path)
    after = conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    conn.close()
    assert after == before


def test_resume_readiness_blocks_an_unknown_measurement_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "auto_invest.db"
    _seed_ready_evidence(db_path)
    conn = db.get_connection(db_path)
    payload = json.dumps(
        {
            "mode": "live",
            "measurement_scope": "strategy",
            "measurement_contract_id": "sha256:unknown",
        }
    )
    conn.execute(
        "INSERT INTO audit_log (ts_utc, event_type, payload_json) "
        "VALUES (strftime('%Y-%m-%dT%H:%M:%S.000Z','now'), "
        "'PORTFOLIO_NAV_SNAPSHOT', ?)",
        (payload,),
    )
    conn.commit()
    conn.close()

    result = runner.invoke(
        app,
        [
            "resume-readiness",
            "--db",
            str(db_path),
            "--halt-path",
            str(tmp_path / "halt.flag"),
            "--opening-positions",
            str(OPENING),
            "--portfolio",
            str(PORTFOLIO),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["status"] == "BLOCKED"
