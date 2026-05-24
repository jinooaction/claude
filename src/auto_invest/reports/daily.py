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
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from auto_invest.performance.engine import _fmt_ts, build_performance_report
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
class PerformanceSection:
    """Spec 011 T013 (FR-012) — 일일 리포트용 매매 성과 요약.

    그날의 실현 손익·수익률(당일 윈도)과 롤링 기간(기본 30일)의 위험조정 요약을
    담는다. spec 011 성과 엔진을 읽기 전용·시세 미조회(marks 없음)로 호출하므로
    네트워크 의존이 없고 같은 audit_log 에 대해 바이트 동일 출력이 보장된다
    (미실현 손익은 시세가 없어 0/N/A — 시세 기반 미실현은 `performance` CLI 전용).
    """

    mode: str  # "paper" | "live"
    rolling_window_days: int
    day_fills: int
    day_realized_pnl_usd: Decimal
    day_return_pct: Decimal | None
    rolling_closed_trades: int
    rolling_win_rate: Decimal | None
    rolling_sharpe: Decimal | None
    rolling_max_drawdown_pct: Decimal | None
    rolling_total_return_pct: Decimal | None


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
    performance: PerformanceSection | None = None


def _utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _signed_money(v: Decimal | None) -> str:
    return "N/A" if v is None else f"${v.quantize(Decimal('0.01')):+}"


def _pct1(v: Decimal | None, *, scale: int = 1) -> str:
    return "N/A" if v is None else f"{(v * Decimal(scale)).quantize(Decimal('0.1'))}%"


def _pct2(v: Decimal | None) -> str:
    return "N/A" if v is None else f"{v.quantize(Decimal('0.01'))}%"


def _ratio4(v: Decimal | None) -> str:
    return "N/A" if v is None else f"{v.quantize(Decimal('0.0001'))}"


def _detect_performance_mode(
    conn: sqlite3.Connection, since: datetime, until: datetime, *, default: str = "paper"
) -> str:
    """윈도 내 체결 이벤트 종류로 성과 모드를 자동 판별한다.

    라이브 `FILL` 과 페이퍼 `ORDER_PAPER_FILLED` 중 더 많은 쪽을 택하고, 둘 다
    없으면 `default`(현재 시스템 가동 모드 dry-run → "paper")를 쓴다.
    """
    s, u = _fmt_ts(since), _fmt_ts(until)
    live = conn.execute(
        "SELECT COUNT(*) AS c FROM audit_log "
        "WHERE event_type = 'FILL' AND ts_utc >= ? AND ts_utc < ?",
        (s, u),
    ).fetchone()["c"]
    paper = conn.execute(
        "SELECT COUNT(*) AS c FROM audit_log "
        "WHERE event_type = 'ORDER_PAPER_FILLED' AND ts_utc >= ? AND ts_utc < ?",
        (s, u),
    ).fetchone()["c"]
    if live == 0 and paper == 0:
        return default
    return "live" if live >= paper else "paper"


def build_performance_section(
    conn: sqlite3.Connection,
    *,
    session_date: str,
    window_days: int = 30,
    mode: str | None = None,
) -> PerformanceSection:
    """그날의 실현 손익 + 롤링 위험조정 요약을 spec 011 엔진으로 만든다 (읽기 전용)."""
    day_start = datetime.strptime(session_date, "%Y-%m-%d").replace(tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    rolling_start = day_end - timedelta(days=window_days)

    resolved_mode = mode or _detect_performance_mode(conn, rolling_start, day_end)

    day_rep = build_performance_report(
        conn, mode=resolved_mode, since=day_start, until=day_end
    )
    rolling_rep = build_performance_report(
        conn, mode=resolved_mode, since=rolling_start, until=day_end
    )
    risk = rolling_rep.risk

    return PerformanceSection(
        mode=resolved_mode,
        rolling_window_days=window_days,
        day_fills=day_rep.fills_count,
        day_realized_pnl_usd=day_rep.realized_pnl_usd,
        day_return_pct=day_rep.return_pct,
        rolling_closed_trades=(risk.closed_trades if risk else 0),
        rolling_win_rate=(risk.win_rate if risk else None),
        rolling_sharpe=(risk.sharpe_ratio if risk else None),
        rolling_max_drawdown_pct=(risk.max_drawdown_pct if risk else None),
        rolling_total_return_pct=(risk.total_return_pct if risk else None),
    )


def build_report(
    conn: sqlite3.Connection,
    *,
    session_date: str,
    generated_at: str | None = None,
    tiers: TierTable | None = None,
    include_performance: bool = False,
    performance_window_days: int = 30,
    performance_mode: str | None = None,
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

    performance: PerformanceSection | None = None
    if include_performance:
        performance = build_performance_section(
            conn,
            session_date=session_date,
            window_days=performance_window_days,
            mode=performance_mode,
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
        performance=performance,
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

    if report.performance is not None:
        perf = report.performance
        lines.append("## Performance (성과)")
        lines.append(f"- Mode:              {perf.mode}")
        lines.append(f"- Day fills:         {perf.day_fills}")
        lines.append(f"- Day realized PnL:  {_signed_money(perf.day_realized_pnl_usd)}")
        if perf.day_return_pct is None:
            lines.append("- Day return:        N/A (투입 자본 없음)")
        else:
            lines.append(
                f"- Day return:        {perf.day_return_pct.quantize(Decimal('0.01')):+}%"
            )
        lines.append(f"- Rolling {perf.rolling_window_days}d:")
        lines.append(f"  - Closed trades:   {perf.rolling_closed_trades}")
        lines.append(f"  - Win rate:        {_pct1(perf.rolling_win_rate, scale=100)}")
        lines.append(f"  - Sharpe (√252):   {_ratio4(perf.rolling_sharpe)}")
        lines.append(f"  - Max drawdown:    {_pct2(perf.rolling_max_drawdown_pct)}")
        lines.append(f"  - Total return:    {_pct2(perf.rolling_total_return_pct)}")
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
        "performance": _performance_json(report.performance),
    }
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def _performance_json(perf: PerformanceSection | None) -> dict[str, Any] | None:
    if perf is None:
        return None

    def _s(v: Decimal | None) -> str | None:
        return None if v is None else str(v)

    return {
        "mode": perf.mode,
        "rolling_window_days": perf.rolling_window_days,
        "day_fills": perf.day_fills,
        "day_realized_pnl_usd": str(perf.day_realized_pnl_usd),
        "day_return_pct": _s(perf.day_return_pct),
        "rolling_closed_trades": perf.rolling_closed_trades,
        "rolling_win_rate": _s(perf.rolling_win_rate),
        "rolling_sharpe": _s(perf.rolling_sharpe),
        "rolling_max_drawdown_pct": _s(perf.rolling_max_drawdown_pct),
        "rolling_total_return_pct": _s(perf.rolling_total_return_pct),
    }


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
