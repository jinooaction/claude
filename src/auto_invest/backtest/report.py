"""Backtest report writer (T027).

Emits a `report.md` (human-readable) and a `metrics.json`
(machine-readable) inside the run directory. Both files derive from
the same `BacktestResult` so they cannot diverge.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from auto_invest.backtest.engine import BacktestResult


def _fmt_decimal(d: Decimal) -> str:
    return str(d)


def write_metrics_json(result: BacktestResult, path: Path) -> None:
    payload = {
        "starting_capital_usd": _fmt_decimal(result.starting_capital),
        "final_equity_usd": _fmt_decimal(result.final_equity),
        "bar_count": result.bar_count,
        "fill_count": result.fill_count,
        "rejected_by_gate": result.rejected_by_gate,
        "expired_or_cancelled": result.expired_or_cancelled,
        "metrics": result.metrics.to_dict(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_audit_jsonl(result: BacktestResult, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for entry in result.audit_log:
            row = {
                "ts_utc": entry.ts_utc,
                "event_type": entry.event_type,
                "rule_id": entry.rule_id,
                "symbol": entry.symbol,
                "payload": entry.payload,
            }
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_orders_jsonl(result: BacktestResult, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for o in result.orders:
            row = {
                "ts_utc": o.ts_utc,
                "rule_id": o.rule_id,
                "symbol": o.symbol,
                "side": o.side,
                "order_type": o.order_type,
                "requested_qty": o.requested_qty,
                "fill_qty": o.fill_qty,
                "fill_price_usd": o.fill_price_usd,
                "commission_usd": o.commission_usd,
                "half_spread_usd": o.half_spread_usd,
                "impact_usd": o.impact_usd,
                "total_cost_usd": o.total_cost_usd,
            }
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_report_md(result: BacktestResult, path: Path) -> None:
    cfg = result.config
    instrument = cfg.instruments[0]
    m = result.metrics
    lines = [
        f"# Backtest Report",
        "",
        f"- **Rule**: `{cfg.rule.path or cfg.rule.module}`",
        f"- **Snapshot hash**: `{cfg.rule.snapshot_hash}`",
        f"- **Instrument**: `{instrument.asset_class}:{instrument.venue}:{instrument.symbol}` (vendor={instrument.vendor or '<default>'})",
        f"- **Window**: `{cfg.window.from_utc.isoformat()}` → `{cfg.window.to_utc.isoformat()}`",
        f"- **As-of pin**: `{cfg.window.as_of_ts_pin_utc.isoformat()}`",
        f"- **Mode**: `{cfg.mode.kind}`",
        "",
        "## Summary",
        "",
        f"- Starting capital: `${result.starting_capital}`",
        f"- Final equity: `${result.final_equity}`",
        f"- Bar count: `{result.bar_count}`",
        f"- Fill count: `{result.fill_count}`",
        f"- Rejected by gate: `{result.rejected_by_gate}`",
        f"- Expired / cancelled: `{result.expired_or_cancelled}`",
        "",
        "## Performance metrics",
        "",
        f"| metric | value |",
        f"|---|---|",
        f"| Total return | {m.total_return_pct}% |",
        f"| CAGR | {m.cagr_pct}% |",
        f"| Volatility (ann) | {m.volatility_pct}% |",
        f"| Sharpe (rf=0) | {m.sharpe} |",
        f"| Sortino | {m.sortino} |",
        f"| Max drawdown | {m.max_drawdown_pct}% |",
        f"| Hit rate | {m.hit_rate} |",
        f"| Avg win/loss ratio | {m.avg_win_loss_ratio} |",
        f"| Exposure | {m.exposure_pct}% |",
        f"| Turnover (ann) | {m.turnover_pct}% |",
        f"| Gross transaction cost | ${m.gross_transaction_cost_usd} |",
        f"| Closed trades | {m.trade_count} |",
        "",
        "## Trustworthiness caveat",
        "",
        "Phase 3 of spec 002 emits this report; Phase 4 adds the lookahead",
        "barrier, the square-root market-impact term, the participation",
        "cap, and time-in-force semantics. Until Phase 4 lands, this",
        "report is **not yet trustworthy as a basis for promotion**.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_all(result: BacktestResult, run_dir: Path) -> None:
    """Write every artifact in the run directory layout (T028)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "inputs").mkdir(exist_ok=True)
    write_metrics_json(result, run_dir / "metrics.json")
    write_audit_jsonl(result, run_dir / "audit_log.jsonl")
    write_orders_jsonl(result, run_dir / "orders.jsonl")
    write_report_md(result, run_dir / "report.md")
