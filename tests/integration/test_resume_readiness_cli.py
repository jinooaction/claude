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
from auto_invest.reconciliation.runner import ReconciliationOutcome
from auto_invest.worker.halt import set_halt

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


def test_reconcile_recover_runs_fresh_check_and_clears_eligible_halt(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "auto-invest.db"
    _seed_ready_evidence(db_path)
    halt_path = tmp_path / "halt.flag"
    set_halt(halt_path, "reconciliation mismatch: 1 position(s)")
    env_path = tmp_path / ".env"
    env_path.write_text(
        "KIS_APP_KEY=k\nKIS_APP_SECRET=s\nKIS_ACCOUNT_NO=1234567801\n",
        encoding="utf-8",
    )

    async def fake_reconcile(conn, **_kwargs):
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        conn.execute(
            "INSERT INTO reconciliation_runs "
            "(started_at_utc, finished_at_utc, result) VALUES (?, ?, 'OK')",
            (now, now),
        )
        return ReconciliationOutcome(
            state="OK",
            started_at_utc=now,
            finished_at_utc=now,
        )

    monkeypatch.setattr("auto_invest.cli._run_reconcile", fake_reconcile)
    result = runner.invoke(
        app,
        [
            "reconcile-recover",
            "--confirm",
            "--db",
            str(db_path),
            "--halt-path",
            str(halt_path),
            "--env",
            str(env_path),
            "--external-holdings",
            str(ROOT / "deploy/external-holdings.toml"),
            "--opening-positions",
            str(OPENING),
            "--portfolio",
            str(PORTFOLIO),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)
    assert report["status"] == "RECOVERED"
    assert report["orders_submitted"] == 0
    assert not halt_path.exists()


def test_reconcile_recover_requires_confirmation(tmp_path: Path) -> None:
    db_path = tmp_path / "auto-invest.db"
    _seed_ready_evidence(db_path)
    result = runner.invoke(
        app,
        [
            "reconcile-recover",
            "--db",
            str(db_path),
            "--opening-positions",
            str(OPENING),
            "--portfolio",
            str(PORTFOLIO),
        ],
    )
    assert result.exit_code == 2
