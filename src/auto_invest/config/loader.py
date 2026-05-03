"""Configuration loader: TOML -> validated, frozen LoadedConfig.

Implements the validation contract declared in
`contracts/rules-config.md`. Every "refuse to start" rule listed there
is enforced here and surfaces as a `ConfigError`. The CLI translates
that into exit code 2 (FR-011, FR-015).
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, ValidationError

from auto_invest.config.caps import SizingCaps
from auto_invest.config.rules import TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.logging_config import register_secret

REQUIRED_SECRETS: tuple[str, ...] = ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO")
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


class ConfigError(ValueError):
    """Raised when configuration cannot be loaded or validated."""


class LoadedConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    caps: SizingCaps
    whitelist: Whitelist
    rules: tuple[TradingRule, ...]


def load_secrets(env_path: Path | None = None) -> dict[str, str]:
    """Load secrets from `.env` (if present) merged with `os.environ`.

    Every required secret is registered with the logging redaction
    filter the moment it is loaded so it can never leak.
    """
    merged: dict[str, str] = {}
    if env_path is not None and env_path.exists():
        for k, v in dotenv_values(env_path).items():
            if v is not None:
                merged[k] = v
    for k, v in os.environ.items():
        merged[k] = v

    missing = [name for name in REQUIRED_SECRETS if not merged.get(name, "").strip()]
    if missing:
        raise ConfigError(f"required secret(s) missing from environment: {sorted(missing)}")

    for name in REQUIRED_SECRETS:
        register_secret(merged[name])

    return merged


def _expand_env(value: Any, env: dict[str, str]) -> Any:
    """Recursively expand ${VAR} placeholders in string values."""
    if isinstance(value, str):

        def replace(m: re.Match[str]) -> str:
            name = m.group(1)
            if name not in env:
                raise ConfigError(f"unknown environment variable referenced in config: ${{{name}}}")
            return env[name]

        return ENV_VAR_PATTERN.sub(replace, value)
    if isinstance(value, dict):
        return {k: _expand_env(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v, env) for v in value]
    return value


def load_config(rules_path: Path, env_path: Path | None = None) -> LoadedConfig:
    """Load and validate the operator's configuration into a frozen value.

    Order of operations:
      1. Load secrets (refuses on missing required values).
      2. Read TOML file.
      3. Expand ${VAR} placeholders in any string value.
      4. Validate caps section.
      5. Validate whitelist section.
      6. Validate each rule and check cross-section invariants
         (symbol whitelisted, order_type whitelisted, no duplicate ids).
    """
    if not rules_path.exists():
        raise ConfigError(f"rules file not found: {rules_path}")

    secrets = load_secrets(env_path)

    try:
        raw = tomllib.loads(rules_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"rules file is not valid TOML: {e}") from e

    expanded = _expand_env(raw, secrets)

    try:
        caps = SizingCaps.model_validate(expanded.get("caps", {}))
    except ValidationError as e:
        raise ConfigError(f"[caps] section invalid: {e}") from e

    try:
        whitelist = Whitelist.model_validate(expanded.get("whitelist", {}))
    except ValidationError as e:
        raise ConfigError(f"[whitelist] section invalid: {e}") from e

    rules_raw = expanded.get("rules", [])
    rules: list[TradingRule] = []
    seen_ids: set[str] = set()
    for i, rule_data in enumerate(rules_raw):
        try:
            rule = TradingRule.model_validate(rule_data)
        except ValidationError as e:
            raise ConfigError(f"[[rules]] entry {i} invalid: {e}") from e

        if rule.id in seen_ids:
            raise ConfigError(f"duplicate rule id: {rule.id!r}")
        seen_ids.add(rule.id)

        if rule.symbol not in whitelist.symbols:
            raise ConfigError(f"rule {rule.id!r}: symbol {rule.symbol!r} is not on the whitelist")

        if rule.action.order_type not in whitelist.order_types:
            raise ConfigError(
                f"rule {rule.id!r}: order_type {rule.action.order_type!r} is not on the whitelist"
            )

        rules.append(rule)

    return LoadedConfig(caps=caps, whitelist=whitelist, rules=tuple(rules))
