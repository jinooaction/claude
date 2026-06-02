"""스펙 033 — 포트폴리오 로더의 ${VAR} 치환 (계좌 화이트리스트 게이트 정합)."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_invest.cli import _load_portfolio_for_backtest
from auto_invest.config.loader import ConfigError

_TOML = """
[caps]
per_trade_pct = 5.0
per_symbol_pct = 40.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL", "MSFT"]
accounts = ["${KIS_ACCOUNT_NO}"]
order_types = ["LIMIT"]
sessions = ["REGULAR"]

[portfolio]
id = "t"
universe = ["AAPL", "MSFT"]
weights = { momentum = "1.0" }
weight_scheme = "equal"
top_n = 2
lookback_bars = 30
momentum_period = 20
"""


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "pf.toml"
    p.write_text(_TOML)
    return p


def test_env_expands_account_placeholder(tmp_path: Path):
    _caps, wl, _cfg = _load_portfolio_for_backtest(
        _write(tmp_path), env={"KIS_ACCOUNT_NO": "ACC-12345"}
    )
    assert wl.accounts == frozenset({"ACC-12345"})


def test_no_env_leaves_placeholder_literal(tmp_path: Path):
    # env 미제공 시 치환하지 않음(백테스트 BACKTEST 계좌 경로 보호) — 리터럴 유지.
    _caps, wl, _cfg = _load_portfolio_for_backtest(_write(tmp_path))
    assert wl.accounts == frozenset({"${KIS_ACCOUNT_NO}"})


def test_unknown_var_raises(tmp_path: Path):
    with pytest.raises(ConfigError):
        _load_portfolio_for_backtest(_write(tmp_path), env={"OTHER": "x"})
