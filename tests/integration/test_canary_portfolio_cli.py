"""스펙 055 ④ 게이트 — `auto-invest canary-portfolio` CLI 통합 테스트.

CSV 데이터셋을 ingest 후 챔피언 포트폴리오 설정을 캐너리로 돌려 PASS(exit 0)·JSON verdict 를
확인하고, 데이터 없을 때 coverage 종료(EXIT_COVERAGE)를 확인한다.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.backtest.data_source import trading_days_between
from auto_invest.cli import app

runner = CliRunner()

_REPO = Path(__file__).resolve().parents[2]
_BANDS = str(_REPO / "config" / "canary_bands_reassign.toml")

_SESSIONS = trading_days_between(date(2024, 1, 1), date(2024, 4, 15))[:55]

_PORTFOLIO = """\
[caps]
per_trade_pct = 60
per_symbol_pct = 65
global_exposure_pct = 100
canary_capital_pct = 1
canary_min_duration_days = 5
canary_acceptance_drawdown_pct = 80

[whitelist]
symbols = ["SPY", "IEF"]
accounts = ["BACKTEST"]
order_types = ["LIMIT"]
sessions = ["REGULAR"]

[portfolio]
id = "canary-cli-test"
universe = ["SPY", "IEF"]
weights = { momentum = "1.0" }
weight_scheme = "equal"
top_n = 2
rebalance_mode = "hold_replace"
invested_fraction = "0.99"
rebalance_every_n_sessions = 5
lookback_bars = 30
momentum_period = 10
"""


def _csv(price_of) -> str:
    rows = ["session_date,open,high,low,close,volume,session_schedule_tag"]
    for i, d in enumerate(_SESSIONS):
        c = price_of(i)
        rows.append(
            f"{d.isoformat()},{c:.4f},{c * 1.01:.4f},{c * 0.99:.4f},{c:.4f},10000000,regular"
        )
    return "\n".join(rows) + "\n"


def _ingest(tmp_path: Path) -> Path:
    csv_root = tmp_path / "history-csv"
    csv_root.mkdir()
    (csv_root / "SPY.csv").write_text(_csv(lambda i: 400.0 + i))
    (csv_root / "IEF.csv").write_text(_csv(lambda i: 95.0 + i * 0.1))
    history_root = tmp_path / "history"
    res = runner.invoke(
        app,
        ["ingest-history", "--from-dir", str(csv_root), "--out-dir", str(history_root)],
    )
    assert res.exit_code == 0, res.output
    return history_root


def test_canary_portfolio_passes_on_calm_history(tmp_path: Path) -> None:
    history_root = _ingest(tmp_path)
    portfolio = tmp_path / "challenger.toml"
    portfolio.write_text(_PORTFOLIO)

    res = runner.invoke(
        app,
        [
            "canary-portfolio",
            "--portfolio", str(portfolio),
            "--history-root", str(history_root),
            "--bands-toml", _BANDS,
            "--db", str(tmp_path / "audit.db"),
            "--halt-path", str(tmp_path / "HALT"),
            "--skip-fuzz",
            "--skip-shock",
            "--format", "json",
        ],
    )
    assert res.exit_code == 0, res.output
    out = json.loads(res.output.strip().splitlines()[-1])
    assert out["verdict"] == "PASS"
    assert out["portfolio_id"] == "canary-cli-test"
    assert out["candidate_drawdown_pct"] <= 10.0
    assert out["audit_integrity_count"] == 0


def test_canary_portfolio_coverage_exit_when_no_dataset(tmp_path: Path) -> None:
    portfolio = tmp_path / "challenger.toml"
    portfolio.write_text(_PORTFOLIO)
    res = runner.invoke(
        app,
        [
            "canary-portfolio",
            "--portfolio", str(portfolio),
            "--history-root", str(tmp_path / "empty-history"),
            "--bands-toml", _BANDS,
            "--db", str(tmp_path / "audit.db"),
        ],
    )
    assert res.exit_code == 2  # EXIT_COVERAGE — 데이터셋 없음


def test_canary_portfolio_text_format(tmp_path: Path) -> None:
    history_root = _ingest(tmp_path)
    portfolio = tmp_path / "challenger.toml"
    portfolio.write_text(_PORTFOLIO)
    res = runner.invoke(
        app,
        [
            "canary-portfolio",
            "--portfolio", str(portfolio),
            "--history-root", str(history_root),
            "--bands-toml", _BANDS,
            "--db", str(tmp_path / "audit.db"),
            "--halt-path", str(tmp_path / "HALT"),
            "--skip-fuzz",
            "--skip-shock",
            "--format", "text",
        ],
    )
    assert res.exit_code == 0, res.output
    assert "PASS" in res.output
    assert "canary-cli-test" in res.output
