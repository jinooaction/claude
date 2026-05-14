"""Daily report generator (T054, FR-010).

Reads the audit log and the position cache to build a human-readable
end-of-session summary. The same data is rendered in two formats:

  * Markdown (`daily-report.md`)  — for the operator's morning audit.
  * JSON     (`daily-report.json`) — for tooling that wants to diff
                                     or aggregate sessions.

The report's content is fully derived from persisted state, so a
rerun against the same audit log produces byte-identical output
(modulo the `generated_at` timestamp, which is exposed as a parameter
for testability).
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.persistence import positions as positions_mod
from auto_invest.telemetry.kpi import EfficiencySnapshot, compute_snapshot
from auto_invest.telemetry.thresholds import TierTable


@dataclass(frozen=True)
class RuleActivity:
    rule_id: str
    triggers: int
    submitted: int
    rejected: int


@dataclass(frozen=True)
class GateRejection:
    ts_utc: str
    rule_id: str | None
    symbol: str | None
    gate: str
    reason: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DailyReport:
    session_date: str
    generated_at: str
    counters: dict[str, int]
    rules: list[RuleActivity]
    rejections: list[GateRejection]
    positions: list[dict[str, Any]]
    reconciliation: str
    halt: dict[str, Any] | None = None
    efficiency: EfficiencySnapshot | None = None


def _utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_report(
    conn: sqlite3.Connection,
    *,
    session_date: str,
    generated_at: str | None = None,
    tiers: TierTable | None = None,
) -> DailyReport:
    """Build a DailyReport from the audit log + positions cache.

    `session_date` is matched as a UTC date-prefix on `audit_log.ts_utc`.
    """
    rows = conn.execute(
        """
        SELECT seq, ts_utc, event_type, rule_id, symbol, payload_json,
               correlation_id
        FROM audit_log
        WHERE substr(ts_utc, 1, 10) = ?
          AND event_type NOT IN ('BACKTEST_STARTED','BACKTEST_COMPLETED','LLM_CALL_STUBBED')
        ORDER BY seq
        """,
        (session_date,),
    ).fetchall()

    counter: Counter[str] = Counter()
    per_rule_triggers: dict[str, int] = defaultdict(int)
    per_rule_submitted: dict[str, int] = defaultdict(int)
    per_rule_rejected: dict[str, int] = defaultdict(int)
    rejections: list[GateRejection] = []

    for row in rows:
        event = row["event_type"]
        if event == "ORDER_INTENT":
            counter["orders_attempted"] += 1
            if row["rule_id"]:
                per_rule_triggers[row["rule_id"]] += 1
        elif event == "ORDER_SUBMITTED":
            counter["orders_submitted"] += 1
            if row["rule_id"]:
                per_rule_submitted[row["rule_id"]] += 1
        elif event == "ORDER_REJECTED_BY_GATE":
            counter["orders_rejected_by_gate"] += 1
            if row["rule_id"]:
                per_rule_rejected[row["rule_id"]] += 1
            payload = json.loads(row["payload_json"])
            rejections.append(
                GateRejection(
                    ts_utc=row["ts_utc"],
                    rule_id=row["rule_id"],
                    symbol=row["symbol"],
                    gate=payload.get("gate", "?"),
                    reason=payload.get("reason", ""),
                    metadata=payload.get("metadata", {}),
                )
            )
        elif event == "ORDER_REJECTED_BY_BROKER":
            counter["orders_rejected_by_broker"] += 1
        elif event == "FILL":
            counter["fills"] += 1

    rule_ids = sorted(set(per_rule_triggers) | set(per_rule_submitted) | set(per_rule_rejected))
    rules = [
        RuleActivity(
            rule_id=rid,
            triggers=per_rule_triggers.get(rid, 0),
            submitted=per_rule_submitted.get(rid, 0),
            rejected=per_rule_rejected.get(rid, 0),
        )
        for rid in rule_ids
    ]

    # Last reconciliation result for the session date.
    recon_row = conn.execute(
        """
        SELECT result FROM reconciliation_runs
        WHERE substr(started_at_utc, 1, 10) = ?
        ORDER BY seq DESC LIMIT 1
        """,
        (session_date,),
    ).fetchone()
    reconciliation = recon_row["result"] if recon_row else "NONE"

    # Halt state (last lifecycle event of the session date).
    halt_row = conn.execute(
        """
        SELECT event_type, payload_json FROM audit_log
        WHERE event_type IN ('HALT_SET', 'HALT_CLEARED')
          AND substr(ts_utc, 1, 10) = ?
        ORDER BY seq DESC LIMIT 1
        """,
        (session_date,),
    ).fetchone()
    if halt_row and halt_row["event_type"] == "HALT_SET":
        halt = json.loads(halt_row["payload_json"])
    else:
        halt = None

    positions_payload = [
        {
            "symbol": p.symbol,
            "qty": p.qty,
            "avg_cost_usd": str(p.avg_cost_usd),
        }
        for p in positions_mod.get_all_positions(conn)
    ]

    efficiency: EfficiencySnapshot | None = None
    if tiers is not None:
        efficiency = compute_snapshot(
            conn,
            window_start_utc=f"{session_date}T00:00:00.000Z",
            window_end_utc=f"{session_date}T23:59:59.999Z",
            tiers=tiers,
        )

    return DailyReport(
        session_date=session_date,
        generated_at=generated_at or _utcnow_iso(),
        counters=dict(counter),
        rules=rules,
        rejections=rejections,
        positions=positions_payload,
        reconciliation=reconciliation,
        halt=halt,
        efficiency=efficiency,
    )


def render_markdown(report: DailyReport) -> str:
    lines: list[str] = []
    lines.append("# auto-invest — Daily Report")
    lines.append(f"Session date: {report.session_date}")
    lines.append(f"Generated: {report.generated_at}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Reconciliation: {report.reconciliation}")
    if report.halt:
        lines.append(f"- Halt:           {report.halt.get('reason', '?')}")
    else:
        lines.append("- Halt:           not set")
    lines.append(f"- Orders attempted:        {report.counters.get('orders_attempted', 0)}")
    lines.append(f"- Orders submitted:        {report.counters.get('orders_submitted', 0)}")
    lines.append(f"- Orders rejected by gate: {report.counters.get('orders_rejected_by_gate', 0)}")
    rejected_broker = report.counters.get("orders_rejected_by_broker", 0)
    lines.append(f"- Orders rejected by broker: {rejected_broker}")
    lines.append(f"- Fills:                   {report.counters.get('fills', 0)}")
    lines.append("")

    lines.append("## Per-rule activity")
    if report.rules:
        lines.append("| rule_id | triggers | submitted | rejected |")
        lines.append("|---------|---------:|----------:|---------:|")
        for r in report.rules:
            lines.append(f"| {r.rule_id} | {r.triggers} | {r.submitted} | {r.rejected} |")
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## Risk-gate rejections")
    if report.rejections:
        for rej in report.rejections:
            lines.append(
                f"- {rej.ts_utc} rule={rej.rule_id} symbol={rej.symbol} "
                f"gate={rej.gate} reason={rej.reason}"
            )
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## Token Efficiency")
    if report.efficiency is None or report.efficiency.call_count == 0:
        lines.append("(no LLM calls today)")
    else:
        eff = report.efficiency
        lines.append(f"- LLM calls:        {eff.call_count}")
        for kpi in eff.kpis:
            lines.append(f"- {kpi.name:<28} {kpi.value} (Tier {kpi.tier})")
        if eff.per_decision_class:
            lines.append("")
            lines.append("| decision_class | count | tokens_total | cost_usd | p95_tokens |")
            lines.append("|----------------|------:|-------------:|---------:|-----------:|")
            for klass, agg in eff.per_decision_class.items():
                lines.append(
                    f"| {klass} | {agg['count']} | {agg['tokens_total']} | "
                    f"{agg['cost_usd']} | {agg['p95_tokens']} |"
                )
    lines.append("")

    lines.append("## Positions (current)")
    if report.positions:
        lines.append("| symbol | qty | avg_cost_usd |")
        lines.append("|--------|----:|-------------:|")
        for p in report.positions:
            lines.append(f"| {p['symbol']} | {p['qty']} | {p['avg_cost_usd']} |")
    else:
        lines.append("(none)")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_json(report: DailyReport) -> str:
    eff_payload: dict[str, Any] | None
    if report.efficiency is None:
        eff_payload = None
    else:
        eff = report.efficiency
        eff_payload = {
            "window_start_utc": eff.window_start_utc,
            "window_end_utc": eff.window_end_utc,
            "call_count": eff.call_count,
            "kpis": [
                {
                    "name": k.name,
                    "value": str(k.value),
                    "tier": k.tier,
                    "direction": k.direction,
                    "threshold_used": k.threshold_used,
                }
                for k in eff.kpis
            ],
            "per_decision_class": eff.per_decision_class,
            "top_n_calls": eff.top_n_calls,
        }
    payload = {
        "session_date": report.session_date,
        "generated_at": report.generated_at,
        "counters": report.counters,
        "rules": [
            {
                "rule_id": r.rule_id,
                "triggers": r.triggers,
                "submitted": r.submitted,
                "rejected": r.rejected,
            }
            for r in report.rules
        ],
        "rejections": [
            {
                "ts_utc": r.ts_utc,
                "rule_id": r.rule_id,
                "symbol": r.symbol,
                "gate": r.gate,
                "reason": r.reason,
                "metadata": r.metadata,
            }
            for r in report.rejections
        ],
        "positions": report.positions,
        "reconciliation": report.reconciliation,
        "halt": report.halt,
        "efficiency": eff_payload,
    }
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def write_report(
    report: DailyReport,
    *,
    output_root: Path,
) -> tuple[Path, Path]:
    """Write Markdown + JSON for the report under output_root/{date}/.

    Returns (md_path, json_path).
    """
    out_dir = output_root / report.session_date
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "daily-report.md"
    json_path = out_dir / "daily-report.json"
    md_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(render_json(report), encoding="utf-8")
    return md_path, json_path
