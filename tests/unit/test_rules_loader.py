"""Tests for `auto_invest.config.loader` (T020).

These cover every "refuse to start" rule listed in
`specs/001-automated-trading-mvp/contracts/rules-config.md`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from auto_invest import logging_config
from auto_invest.config.enums import StrategyStage
from auto_invest.config.loader import ConfigError, load_config

SAMPLE_RULES_PATH = Path("tests/fixtures/rules/sample-canary.toml")


@pytest.fixture(autouse=True)
def _reset_secrets() -> Iterator[None]:
    logging_config._secrets.clear()
    yield
    logging_config._secrets.clear()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIS_APP_KEY", "test-app-key-1234567")
    monkeypatch.setenv("KIS_APP_SECRET", "test-app-secret-7654321")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678")


# ------------------------------------------------------------ happy path


def test_loads_sample_canary_fixture(env, tmp_path: Path):
    cfg = load_config(SAMPLE_RULES_PATH)
    assert {r.id for r in cfg.rules} == {"spy-morning-dip", "msft-ema-cross"}
    assert cfg.whitelist.symbols == frozenset({"AAPL", "MSFT", "SPY"})
    assert "12345678" in cfg.whitelist.accounts
    assert all(r.stage is StrategyStage.CANARY for r in cfg.rules)


def test_loaded_config_is_frozen(env):
    cfg = load_config(SAMPLE_RULES_PATH)
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        cfg.rules = ()  # type: ignore[misc]


def test_loader_registers_secrets(env):
    load_config(SAMPLE_RULES_PATH)
    assert "test-app-key-1234567" in logging_config._secrets
    assert "test-app-secret-7654321" in logging_config._secrets
    assert "12345678" in logging_config._secrets


# ------------------------------------------------------------ refusal cases


def _write_rules(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "rules.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_refuses_when_required_secret_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    monkeypatch.delenv("KIS_ACCOUNT_NO", raising=False)

    p = _write_rules(tmp_path, "[caps]\n")
    with pytest.raises(ConfigError, match="required secret"):
        load_config(p)


def test_refuses_when_file_missing(env, tmp_path: Path):
    p = tmp_path / "does-not-exist.toml"
    with pytest.raises(ConfigError, match="not found"):
        load_config(p)


def test_refuses_invalid_toml(env, tmp_path: Path):
    p = _write_rules(tmp_path, "this is = not = valid = toml = oops")
    with pytest.raises(ConfigError, match="not valid TOML"):
        load_config(p)


def test_refuses_undefined_env_var(env, tmp_path: Path):
    p = _write_rules(
        tmp_path,
        """
[caps]
per_trade_pct = 5.0
per_symbol_pct = 20.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL"]
accounts = ["${THIS_VAR_DOES_NOT_EXIST}"]
""",
    )
    with pytest.raises(ConfigError, match="THIS_VAR_DOES_NOT_EXIST"):
        load_config(p)


def test_refuses_caps_with_bad_ordering(env, tmp_path: Path):
    p = _write_rules(
        tmp_path,
        """
[caps]
per_trade_pct = 30.0
per_symbol_pct = 20.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL"]
""",
    )
    with pytest.raises(ConfigError, match="caps"):
        load_config(p)


def test_refuses_lowercase_symbol_in_whitelist(env, tmp_path: Path):
    # Lowercase becomes uppercase, but illegal characters fail. Use '!' to
    # explicitly trip the symbol pattern.
    p = _write_rules(
        tmp_path,
        """
[caps]
per_trade_pct = 5.0
per_symbol_pct = 20.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL!"]
""",
    )
    with pytest.raises(ConfigError, match="whitelist"):
        load_config(p)


def test_refuses_rule_for_symbol_not_on_whitelist(env, tmp_path: Path):
    p = _write_rules(
        tmp_path,
        """
[caps]
per_trade_pct = 5.0
per_symbol_pct = 20.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL"]

[[rules]]
id = "tsla-rule"
symbol = "TSLA"
stage = "CANARY"
priority = 1
enabled = true

  [rules.trigger]
  kind = "price"
  direction = "<="
  threshold = 100.0
  cooldown_seconds = 60

  [rules.action]
  side = "BUY"
  order_type = "LIMIT"
  qty = 1
  limit_price = "100.00"
""",
    )
    with pytest.raises(ConfigError, match="not on the whitelist"):
        load_config(p)


def test_refuses_rule_with_order_type_outside_whitelist(env, tmp_path: Path):
    p = _write_rules(
        tmp_path,
        """
[caps]
per_trade_pct = 5.0
per_symbol_pct = 20.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL"]
order_types = ["LIMIT"]   # MARKET deliberately excluded

[[rules]]
id = "aapl-market"
symbol = "AAPL"
stage = "CANARY"
priority = 1
enabled = true

  [rules.trigger]
  kind = "price"
  direction = "<="
  threshold = 100.0
  cooldown_seconds = 60

  [rules.action]
  side = "BUY"
  order_type = "MARKET"
  qty = 1
  limit_price = "0"
""",
    )
    with pytest.raises(ConfigError, match="not on the whitelist"):
        load_config(p)


def test_refuses_duplicate_rule_id(env, tmp_path: Path):
    p = _write_rules(
        tmp_path,
        """
[caps]
per_trade_pct = 5.0
per_symbol_pct = 20.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL"]

[[rules]]
id = "dup"
symbol = "AAPL"
stage = "CANARY"
priority = 1
enabled = true

  [rules.trigger]
  kind = "price"
  direction = "<="
  threshold = 100.0
  cooldown_seconds = 60

  [rules.action]
  side = "BUY"
  order_type = "LIMIT"
  qty = 1
  limit_price = "100.00"

[[rules]]
id = "dup"
symbol = "AAPL"
stage = "CANARY"
priority = 2
enabled = true

  [rules.trigger]
  kind = "price"
  direction = ">="
  threshold = 200.0
  cooldown_seconds = 60

  [rules.action]
  side = "SELL"
  order_type = "LIMIT"
  qty = 1
  limit_price = "200.00"
""",
    )
    with pytest.raises(ConfigError, match="duplicate rule id"):
        load_config(p)


def test_refuses_unknown_trigger_kind(env, tmp_path: Path):
    p = _write_rules(
        tmp_path,
        """
[caps]
per_trade_pct = 5.0
per_symbol_pct = 20.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL"]

[[rules]]
id = "bad-kind"
symbol = "AAPL"
stage = "CANARY"
priority = 1
enabled = true

  [rules.trigger]
  kind = "telepathy"
  cooldown_seconds = 60

  [rules.action]
  side = "BUY"
  order_type = "LIMIT"
  qty = 1
  limit_price = "100.00"
""",
    )
    with pytest.raises(ConfigError, match="rules"):
        load_config(p)


def test_loads_dotenv_file_when_provided(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    monkeypatch.delenv("KIS_ACCOUNT_NO", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "KIS_APP_KEY=from-dotenv-key-1234\n"
        "KIS_APP_SECRET=from-dotenv-secret-1234\n"
        "KIS_ACCOUNT_NO=99887766\n",
        encoding="utf-8",
    )
    rules_path = _write_rules(
        tmp_path,
        """
[caps]
per_trade_pct = 5.0
per_symbol_pct = 20.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL"]
accounts = ["${KIS_ACCOUNT_NO}"]
""",
    )
    cfg = load_config(rules_path, env_path=env_file)
    assert "99887766" in cfg.whitelist.accounts
    assert "from-dotenv-key-1234" in logging_config._secrets


def test_os_env_overrides_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("KIS_APP_KEY", "from-os-env-key-1234")
    monkeypatch.setenv("KIS_APP_SECRET", "from-os-env-secret-1234")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "11112222")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "KIS_APP_KEY=from-dotenv-key-1234\n"
        "KIS_APP_SECRET=from-dotenv-secret-1234\n"
        "KIS_ACCOUNT_NO=99887766\n",
        encoding="utf-8",
    )
    rules_path = _write_rules(
        tmp_path,
        """
[caps]
per_trade_pct = 5.0
per_symbol_pct = 20.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL"]
accounts = ["${KIS_ACCOUNT_NO}"]
""",
    )
    cfg = load_config(rules_path, env_path=env_file)
    assert "11112222" in cfg.whitelist.accounts
    assert "99887766" not in cfg.whitelist.accounts
