"""Backtest run orchestration (T028 + T029).

Glues together: config resolution, run-id computation, run-dir
layout, engine invocation, report writing, and the `backtest_runs`
mirror row in SQLite.
"""

from __future__ import annotations

import json
import sqlite3
import tomllib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from auto_invest.backtest import determinism
from auto_invest.backtest.engine import EngineInputs, run_backtest
from auto_invest.backtest.report import write_all
from auto_invest.config.backtest import BacktestConfig, load_backtest_config
from auto_invest.config.caps import SizingCaps
from auto_invest.config.data import DataSourcesConfig
from auto_invest.config.rules import TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.market_data.revisions import latest_as_of


def _utcnow_iso_ms() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _canonicalise_toml_text(text: str) -> str:
    return determinism.canonicalise(text)


def resolve_run(
    *,
    conn: sqlite3.Connection,
    config_text: str,
    rule_text: str,
    data_sources: DataSourcesConfig,
) -> tuple[BacktestConfig, str, str, str, str]:
    """Resolve config + rule + data pin → (config, rule_hash, config_hash, pin_hash, run_id).

    The `BacktestConfig` returned has its `instruments` rewritten so
    each `vendor` is non-None (resolved against `data_sources` when
    not pinned in the config text).
    """
    raw = tomllib.loads(config_text)
    cfg = BacktestConfig.model_validate(raw)
    instruments = []
    for inst in cfg.instruments:
        vendor = inst.vendor or data_sources.vendor_for(inst.asset_class, _kind_for_timeframe(_resolve_timeframe(rule_text)))
        if vendor is None:
            raise ValueError(
                f"no vendor pinned and no default for ({inst.asset_class}, {inst.symbol}); "
                f"add `vendor=` to [[instruments]] or set default_vendor_per_kind"
            )
        instruments.append(inst.model_copy(update={"vendor": vendor}))
    cfg = cfg.model_copy(update={"instruments": tuple(instruments)})

    rule_hash = determinism.rule_snapshot_hash(rule_text)
    # Hash the canonicalised raw TOML (whitespace/key-order/decimal-format
    # invariant) so two textually-different but semantically-identical
    # config files map to the same `run_id`.
    config_hash = determinism.config_hash(config_text)
    pin_hash = determinism.data_pin_hash(
        [
            {
                "asset_class": i.asset_class,
                "venue": i.venue,
                "symbol": i.symbol,
                "vendor": i.vendor,
                "as_of_ts_pin_utc": cfg.window.as_of_ts_pin_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
            for i in cfg.instruments
        ]
    )
    run_id = determinism.run_id(rule_hash=rule_hash, config_hash_=config_hash, data_pin_hash=pin_hash)
    return cfg, rule_hash, config_hash, pin_hash, run_id


def _resolve_timeframe(rule_text: str) -> str:
    """Best-effort: pull `timeframe` from the [trigger] table."""
    raw = tomllib.loads(rule_text)
    trig = raw.get("trigger", {})
    return trig.get("timeframe", "1d")


def _kind_for_timeframe(tf: str) -> str:
    return {"1m": "ohlcv_1m", "1h": "ohlcv_1h", "1d": "ohlcv_1d"}.get(tf, "ohlcv_1d")


def _dump_toml_canon_for_hash(cfg: BacktestConfig) -> str:
    """Stable text form for hashing — JSON dump sorted by keys."""
    payload = cfg.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, default=str)


def execute_run(
    *,
    conn: sqlite3.Connection,
    config_text: str,
    rule_text: str,
    rule: TradingRule,
    data_sources: DataSourcesConfig,
    whitelist: Whitelist,
    caps: SizingCaps,
    starting_capital_usd: Decimal,
    backtests_root: Path,
    instrument_idx: int = 0,
) -> tuple[Path, str]:
    """Resolve, run, write artifacts, mirror to SQLite. Returns (run_dir, run_id).

    Idempotent: a re-run with bit-identical inputs returns the existing
    run_dir without re-executing the engine.
    """
    cfg, rule_hash, config_hash, pin_hash, run_id = resolve_run(
        conn=conn,
        config_text=config_text,
        rule_text=rule_text,
        data_sources=data_sources,
    )
    run_dir = backtests_root / run_id
    if run_dir.exists() and (run_dir / "metrics.json").exists():
        return run_dir, run_id

    inputs = EngineInputs(
        rule=rule,
        rule_snapshot_hash=rule_hash,
        config=cfg,
        whitelist=whitelist,
        caps=caps,
        starting_capital_usd=starting_capital_usd,
    )
    result = run_backtest(conn=conn, inputs=inputs, instrument_idx=instrument_idx)

    run_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(exist_ok=True)
    (inputs_dir / "run.toml").write_text(config_text, encoding="utf-8")
    (inputs_dir / "rule_snapshot.toml").write_text(rule_text, encoding="utf-8")
    (inputs_dir / "data_pin.json").write_text(
        json.dumps(
            {
                "as_of_ts_pin_utc": cfg.window.as_of_ts_pin_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "instruments": [
                    {
                        "asset_class": i.asset_class,
                        "venue": i.venue,
                        "symbol": i.symbol,
                        "vendor": i.vendor,
                    }
                    for i in cfg.instruments
                ],
                "config_hash": config_hash,
                "data_pin_hash": pin_hash,
                "rule_snapshot_hash": rule_hash,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    write_all(result, run_dir)

    # Mirror row in backtest_runs.
    instruments_json = json.dumps(
        [(i.asset_class, i.venue, i.symbol, i.vendor) for i in cfg.instruments]
    )
    conn.execute(
        """
        INSERT INTO backtest_runs
            (run_id, created_ts_utc, rule_snapshot_hash, config_hash,
             instruments_json, window_from_utc, window_to_utc,
             as_of_ts_pin_utc, mode, result_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            _utcnow_iso_ms(),
            rule_hash,
            config_hash,
            instruments_json,
            cfg.window.from_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            cfg.window.to_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            cfg.window.as_of_ts_pin_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            cfg.mode.kind,
            "succeeded",
        ),
    )
    return run_dir, run_id
