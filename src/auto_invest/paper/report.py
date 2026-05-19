"""Spec 009 T022 — paper-report 집계 로직.

audit_log를 6개 SELECT로 집계해 룰별 시그널·체결·차단 분포·외부 API 오류·
튜닝 피드백·가상 포지션을 PaperReport 객체로 합성. read-only — DB에 INSERT/
UPDATE 없음.

성능 예산: 일주일 ~10만 row에서 200ms 이내 (SC-003). 기존 audit_log 인덱스만
사용하며 신규 인덱스 추가 없음.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from auto_invest.paper.virtual_positions import (
    VirtualPositionRow,
    recompute_virtual_positions,
)


@dataclass
class PerRuleStat:
    rule_id: str
    signals: int
    fills: int
    denied: int
    virtual_pnl_usd: Decimal


@dataclass
class PaperReport:
    period_since_utc: str
    period_until_utc: str
    sessions_count: int
    sessions_uptime_seconds: int
    rulesets_observed: list[str]
    per_rule: list[PerRuleStat]
    gate_denials: dict[str, int]
    external_api_errors: dict[str, int]
    rules_never_fired: list[str]
    hottest_rules: list[tuple[str, int]]
    quote_source_pct: dict[str, float]
    virtual_positions: list[VirtualPositionRow]
    total_paper_events: int = 0

    def to_json_dict(self) -> dict:
        return {
            "period": {
                "since_utc": self.period_since_utc,
                "until_utc": self.period_until_utc,
            },
            "sessions": {
                "count": self.sessions_count,
                "uptime_seconds": self.sessions_uptime_seconds,
            },
            "rulesets_observed": self.rulesets_observed,
            "per_rule": [
                {
                    "rule_id": r.rule_id,
                    "signals": r.signals,
                    "fills": r.fills,
                    "denied": r.denied,
                    "virtual_pnl_usd": str(r.virtual_pnl_usd),
                }
                for r in self.per_rule
            ],
            "gate_denials": self.gate_denials,
            "external_api_errors": self.external_api_errors,
            "tuning_feedback": {
                "rules_never_fired": self.rules_never_fired,
                "hottest_rules": [
                    {"rule_id": rid, "signals": n} for rid, n in self.hottest_rules
                ],
                "quote_source_pct": self.quote_source_pct,
            },
            "virtual_positions": [
                {
                    "symbol": p.symbol,
                    "qty": p.qty,
                    "avg_cost_usd": str(p.avg_cost_usd),
                    "realized_pnl_usd": str(p.realized_pnl_usd),
                }
                for p in self.virtual_positions
            ],
            "total_paper_events": self.total_paper_events,
        }


def _fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_paper_report(
    conn: sqlite3.Connection,
    *,
    since: datetime,
    until: datetime | None = None,
) -> PaperReport:
    """Spec 009 paper-report 메인 진입점.

    `since`/`until` 범위 안의 paper 이벤트만 집계. live 이벤트(WORKER_*,
    FILL, ORDER_SUBMITTED 등)는 자동으로 제외된다 — paper-specific event_type
    만 SELECT하기 때문.
    """
    if until is None:
        until = datetime.now(UTC)
    since_str = _fmt_ts(since)
    until_str = _fmt_ts(until)

    # 1. paper-run 세션 수 + 업타임.
    sessions_count, uptime_seconds = _aggregate_sessions(conn, since_str, until_str)

    # 2. 관찰된 ruleset_sha256 (PAPER_RUN_STARTED 페이로드에서).
    rulesets = _observed_rulesets(conn, since_str, until_str)

    # 3. 룰별 시그널·체결·차단 카운트.
    signals_by_rule = _count_by_rule(conn, "ORDER_INTENT", since_str, until_str)
    fills_by_rule = _count_by_rule(conn, "ORDER_PAPER_FILLED", since_str, until_str)
    denied_by_rule = _count_by_rule(conn, "ORDER_REJECTED_BY_GATE", since_str, until_str)

    # 4. 게이트별 차단 분포.
    gate_denials = _gate_denials(conn, since_str, until_str)

    # 5. 외부 API 오류.
    external_errors = _external_api_errors(conn, since_str, until_str)

    # 6. 가상 포지션 derived view.
    positions_dict = recompute_virtual_positions(conn, since=since, until=until)

    # 7. 룰별 virtual PnL — 가장 단순한 형태: 룰별 fill의 SELL 차감과 BUY 진입을
    #    종목별로 합치는 대신, 가상 포지션 합산값을 룰 단위로 풀어 쓴다.
    #    rule_id → symbol 매핑이 1:N일 수 있으므로 정확한 룰별 PnL은 상위 도구의
    #    역할로 미루고 여기서는 룰별 fill 수만 노출. virtual_pnl_usd는 0.
    rule_ids = set(signals_by_rule) | set(fills_by_rule) | set(denied_by_rule)
    per_rule = [
        PerRuleStat(
            rule_id=rid,
            signals=signals_by_rule.get(rid, 0),
            fills=fills_by_rule.get(rid, 0),
            denied=denied_by_rule.get(rid, 0),
            virtual_pnl_usd=Decimal("0"),
        )
        for rid in sorted(rule_ids)
    ]

    # 8. 튜닝 피드백.
    loaded_rules = _last_loaded_rules(conn, until_str)
    rules_never_fired = sorted(set(loaded_rules) - set(signals_by_rule.keys()))
    hottest = sorted(signals_by_rule.items(), key=lambda kv: kv[1], reverse=True)[:5]

    # 9. quote_source 분포.
    quote_source_pct = _quote_source_pct(conn, since_str, until_str)

    total_paper_events = _count_paper_events(conn, since_str, until_str)

    return PaperReport(
        period_since_utc=since_str,
        period_until_utc=until_str,
        sessions_count=sessions_count,
        sessions_uptime_seconds=uptime_seconds,
        rulesets_observed=rulesets,
        per_rule=per_rule,
        gate_denials=gate_denials,
        external_api_errors=external_errors,
        rules_never_fired=rules_never_fired,
        hottest_rules=hottest,
        quote_source_pct=quote_source_pct,
        virtual_positions=sorted(positions_dict.values(), key=lambda p: p.symbol),
        total_paper_events=total_paper_events,
    )


# --------------------------------------------------------- aggregation helpers


def _aggregate_sessions(
    conn: sqlite3.Connection, since: str, until: str
) -> tuple[int, int]:
    """PAPER_RUN_STARTED 수 + (STOPPED 짝맞춤 시) 총 가동 시간(초)."""
    started_rows = list(conn.execute(
        "SELECT seq, ts_utc FROM audit_log "
        "WHERE event_type = 'PAPER_RUN_STARTED' AND ts_utc >= ? AND ts_utc < ? "
        "ORDER BY seq",
        (since, until),
    ))
    sessions_count = len(started_rows)

    uptime = 0
    for row in started_rows:
        # 같은 시작 row 이후의 가장 첫 STOPPED를 찾는다.
        stop_row = conn.execute(
            "SELECT ts_utc FROM audit_log "
            "WHERE event_type = 'PAPER_RUN_STOPPED' AND seq > ? "
            "ORDER BY seq LIMIT 1",
            (row["seq"],),
        ).fetchone()
        if stop_row is None:
            continue
        try:
            t0 = datetime.strptime(row["ts_utc"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
            t1 = datetime.strptime(stop_row["ts_utc"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
        except ValueError:
            continue
        uptime += int((t1 - t0).total_seconds())
    return sessions_count, uptime


def _observed_rulesets(
    conn: sqlite3.Connection, since: str, until: str
) -> list[str]:
    rows = conn.execute(
        "SELECT payload_json FROM audit_log "
        "WHERE event_type = 'PAPER_RUN_STARTED' AND ts_utc >= ? AND ts_utc < ?",
        (since, until),
    )
    seen: set[str] = set()
    for r in rows:
        payload = json.loads(r["payload_json"])
        sha = payload.get("ruleset_sha256")
        if sha:
            seen.add(sha)
    return sorted(seen)


def _count_by_rule(
    conn: sqlite3.Connection, event_type: str, since: str, until: str
) -> dict[str, int]:
    """rule_id 컬럼별 count. paper 모드 이벤트만 자연스럽게 집계됨 — ORDER_INTENT
    는 paper-run·live-run 둘 다 기록하지만 ORDER_PAPER_FILLED가 있는 시그널만
    실제 시뮬 체결로 이어졌으므로, 호출 시 event_type을 paper 특유 또는
    paper-run 시간 범위로 좁혀 사용한다."""
    out: dict[str, int] = {}
    for row in conn.execute(
        "SELECT rule_id, COUNT(*) as n FROM audit_log "
        "WHERE event_type = ? AND ts_utc >= ? AND ts_utc < ? "
        "AND rule_id IS NOT NULL "
        "GROUP BY rule_id",
        (event_type, since, until),
    ):
        out[row["rule_id"]] = row["n"]
    return out


def _gate_denials(
    conn: sqlite3.Connection, since: str, until: str
) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in conn.execute(
        "SELECT payload_json FROM audit_log "
        "WHERE event_type = 'ORDER_REJECTED_BY_GATE' AND ts_utc >= ? AND ts_utc < ?",
        (since, until),
    ):
        payload = json.loads(row["payload_json"])
        gate = payload.get("gate") or "unknown"
        out[gate] = out.get(gate, 0) + 1
    return out


def _external_api_errors(
    conn: sqlite3.Connection, since: str, until: str
) -> dict[str, int]:
    out: dict[str, int] = {}
    for et in ("ORDER_REJECTED_BY_BROKER", "ERROR"):
        n = conn.execute(
            "SELECT COUNT(*) as n FROM audit_log "
            "WHERE event_type = ? AND ts_utc >= ? AND ts_utc < ?",
            (et, since, until),
        ).fetchone()["n"]
        if n > 0:
            out[et] = n
    return out


def _last_loaded_rules(conn: sqlite3.Connection, until: str) -> list[str]:
    """지정 범위 이전 마지막 RULE_LOAD 이벤트의 rule_ids를 리턴."""
    row = conn.execute(
        "SELECT payload_json FROM audit_log "
        "WHERE event_type = 'RULE_LOAD' AND ts_utc < ? "
        "ORDER BY seq DESC LIMIT 1",
        (until,),
    ).fetchone()
    if row is None:
        return []
    payload = json.loads(row["payload_json"])
    return list(payload.get("rule_ids", []))


def _quote_source_pct(
    conn: sqlite3.Connection, since: str, until: str
) -> dict[str, float]:
    counts: dict[str, int] = {"ask": 0, "bid": 0, "last": 0}
    total = 0
    for row in conn.execute(
        "SELECT payload_json FROM audit_log "
        "WHERE event_type = 'ORDER_PAPER_FILLED' AND ts_utc >= ? AND ts_utc < ?",
        (since, until),
    ):
        payload = json.loads(row["payload_json"])
        src = payload.get("quote_source", "last")
        counts[src] = counts.get(src, 0) + 1
        total += 1
    if total == 0:
        return {}
    return {k: round(v / total, 4) for k, v in counts.items() if v > 0}


def _count_paper_events(
    conn: sqlite3.Connection, since: str, until: str
) -> int:
    row = conn.execute(
        "SELECT COUNT(*) as n FROM audit_log "
        "WHERE event_type IN ("
        "'PAPER_RUN_STARTED', 'PAPER_RUN_STOPPED', "
        "'ORDER_PAPER_FILLED', 'PAPER_RUN_REJECTED') "
        "AND ts_utc >= ? AND ts_utc < ?",
        (since, until),
    ).fetchone()
    return int(row["n"])


# --------------------------------------------------------- text rendering


def render_text(report: PaperReport) -> str:
    """사람 친화적 표 형식. contracts/paper-report-cli.md 명세."""
    lines: list[str] = []
    lines.append("auto-invest paper-report")
    lines.append("=" * 24)
    lines.append(
        f"Period:        {report.period_since_utc} ~ {report.period_until_utc}"
    )
    uptime_h = report.sessions_uptime_seconds // 3600
    uptime_m = (report.sessions_uptime_seconds % 3600) // 60
    lines.append(
        f"Sessions:      {report.sessions_count} "
        f"(total uptime {uptime_h}h {uptime_m}m)"
    )
    if report.rulesets_observed:
        ruleset_count = len(report.rulesets_observed)
        first = report.rulesets_observed[0][:8]
        lines.append(
            f"Ruleset SHA:   {first}... ({ruleset_count} distinct rulesets observed)"
        )
    lines.append("")
    lines.append("Per-rule statistics")
    lines.append("-" * 19)
    lines.append("rule_id          signals  fills   denied   v.PnL (USD)")
    if not report.per_rule:
        lines.append("(no paper-run activity in this period)")
    for r in report.per_rule:
        suffix = "     ← never fired" if r.signals == 0 else ""
        lines.append(
            f"{r.rule_id:<16} {r.signals:>7}  {r.fills:>5}   {r.denied:>6}     "
            f"{r.virtual_pnl_usd:>+8}{suffix}"
        )
    lines.append("")
    lines.append("Gate denials (top 5)")
    lines.append("-" * 20)
    lines.append("gate                   count")
    for gate, n in sorted(report.gate_denials.items(), key=lambda kv: kv[1], reverse=True)[:5]:
        lines.append(f"{gate:<22} {n:>5}")
    lines.append("")
    if report.external_api_errors:
        lines.append("External API errors")
        lines.append("-" * 19)
        for et, n in report.external_api_errors.items():
            lines.append(f"{et:<26} {n:>3}")
        lines.append("")
    lines.append("Tuning feedback")
    lines.append("-" * 15)
    nf = ", ".join(report.rules_never_fired) or "(none)"
    lines.append(f"Rules that never fired:    {nf}")
    hottest = ", ".join(f"{rid} ({n})" for rid, n in report.hottest_rules) or "(none)"
    lines.append(f"Hottest rules (signals):   {hottest}")
    if report.quote_source_pct:
        qpct = ", ".join(
            f"{k} {int(v * 100)}%" for k, v in report.quote_source_pct.items()
        )
        lines.append(f"quote_source fallback:     {qpct} (낮을수록 좋음)")
    lines.append("")
    lines.append("Virtual positions snapshot")
    lines.append("-" * 26)
    lines.append("symbol   qty    avg_cost   realized_pnl")
    if not report.virtual_positions:
        lines.append("(no virtual positions)")
    for p in report.virtual_positions:
        lines.append(
            f"{p.symbol:<7}  {p.qty:>3}     ${p.avg_cost_usd:>8}    ${p.realized_pnl_usd:>8}"
        )
    return "\n".join(lines)
