"""Spec 011 — 라이브 성과 측정 엔진 (읽기 전용).

설계 원칙:
  - 원천 진실(source of truth)은 append-only audit_log. 별도 영속 상태 없이
    체결 이벤트 + 현재 시세만으로 결정론적으로 손익을 재구성한다.
  - 원가 기준은 **평균단가(average cost)**. spec 009 paper 가상 포지션과 동일한
    규약이라 페이퍼·라이브 성과가 한 잣대로 비교된다.
  - 미실현 손익은 주입된 `marks`(종목→현재가) dict로만 계산한다. 엔진은 외부
    API를 호출하지 않는다 — CLI 계층이 KIS 시세를 조회해 주입한다(테스트 가능성).
  - DB에 INSERT/UPDATE/DELETE 없음. SELECT만 수행한다 (FR-002, SC-005).

라이브 FILL 이벤트는 side 를 payload 에 담지 않으므로, 같은 correlation_id 의
ORDER_INTENT 에서 side 를 가져온다. 페이퍼 ORDER_PAPER_FILLED 는 side·symbol·
qty·price 를 모두 자체 보유한다.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


def _fmt_ts(dt: datetime) -> str:
    """audit_log.ts_utc 와 동일한 밀리초 정밀도 ISO8601(Z). 고정 폭이라
    문자열 사전식 비교가 시각 비교와 일치한다. 밀리초를 .000 으로 자르면
    `until=now` 가 같은 초의 체결을 배제하므로 정밀도를 보존한다."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


@dataclass(frozen=True)
class FillRecord:
    """정규화된 체결 한 건. 라이브·페이퍼 공통 표현."""

    symbol: str
    side: str  # "BUY" | "SELL"
    qty: int
    price_usd: Decimal
    ts_utc: str
    rule_id: str | None


@dataclass
class PositionState:
    """체결 누적으로 재구성된 한 종목의 상태."""

    symbol: str
    qty: int
    avg_cost_usd: Decimal
    realized_pnl_usd: Decimal


@dataclass
class SymbolPerformance:
    symbol: str
    qty: int
    avg_cost_usd: Decimal
    realized_pnl_usd: Decimal
    unrealized_pnl_usd: Decimal | None  # None = 시세 조회 불가
    mark_price_usd: Decimal | None
    market_value_usd: Decimal | None

    @property
    def total_pnl_usd(self) -> Decimal:
        return self.realized_pnl_usd + (self.unrealized_pnl_usd or Decimal("0"))


@dataclass
class RulePerformance:
    rule_id: str
    realized_pnl_usd: Decimal
    fills: int
    buys: int
    sells: int


@dataclass
class PerformanceReport:
    mode: str  # "paper" | "live"
    period_since_utc: str
    period_until_utc: str
    fills_count: int
    gross_invested_usd: Decimal
    realized_pnl_usd: Decimal
    unrealized_pnl_usd: Decimal
    total_pnl_usd: Decimal
    return_pct: Decimal | None  # total_pnl / gross_invested × 100; 투입 0이면 None
    per_symbol: list[SymbolPerformance]
    per_rule: list[RulePerformance]
    unmarked_symbols: list[str]  # 미청산이나 시세 조회 못 한 종목
    data_quality_warnings: list[str]

    SCHEMA_VERSION = "1.0"

    def to_json_dict(self) -> dict:
        def _s(v: Decimal | None) -> str | None:
            return None if v is None else str(v)

        return {
            "schema_version": self.SCHEMA_VERSION,
            "mode": self.mode,
            "period": {
                "since_utc": self.period_since_utc,
                "until_utc": self.period_until_utc,
            },
            "fills_count": self.fills_count,
            "gross_invested_usd": str(self.gross_invested_usd),
            "realized_pnl_usd": str(self.realized_pnl_usd),
            "unrealized_pnl_usd": str(self.unrealized_pnl_usd),
            "total_pnl_usd": str(self.total_pnl_usd),
            "return_pct": _s(self.return_pct),
            "per_symbol": [
                {
                    "symbol": p.symbol,
                    "qty": p.qty,
                    "avg_cost_usd": str(p.avg_cost_usd),
                    "realized_pnl_usd": str(p.realized_pnl_usd),
                    "unrealized_pnl_usd": _s(p.unrealized_pnl_usd),
                    "mark_price_usd": _s(p.mark_price_usd),
                    "market_value_usd": _s(p.market_value_usd),
                    "total_pnl_usd": str(p.total_pnl_usd),
                }
                for p in self.per_symbol
            ],
            "per_rule": [
                {
                    "rule_id": r.rule_id,
                    "realized_pnl_usd": str(r.realized_pnl_usd),
                    "fills": r.fills,
                    "buys": r.buys,
                    "sells": r.sells,
                }
                for r in self.per_rule
            ],
            "unmarked_symbols": self.unmarked_symbols,
            "data_quality_warnings": self.data_quality_warnings,
        }


# --------------------------------------------------------------- audit_log read


def read_fills(
    conn: sqlite3.Connection,
    *,
    mode: str,
    since: datetime,
    until: datetime,
) -> list[FillRecord]:
    """모드별 체결을 audit_log에서 읽어 정규화한다.

    - mode="paper": ORDER_PAPER_FILLED (side·symbol·qty·price 자체 보유).
    - mode="live":  FILL (qty·price 보유) + 같은 correlation_id 의 ORDER_INTENT
      에서 side 를 조인. symbol·rule_id 는 FILL row 컬럼에서.
    """
    if mode not in ("paper", "live"):
        raise ValueError(f"mode must be 'paper' or 'live', got {mode!r}")
    since_str = _fmt_ts(since)
    until_str = _fmt_ts(until)

    if mode == "paper":
        return _read_paper_fills(conn, since_str, until_str)
    return _read_live_fills(conn, since_str, until_str)


def _read_paper_fills(
    conn: sqlite3.Connection, since: str, until: str
) -> list[FillRecord]:
    fills: list[FillRecord] = []
    for row in conn.execute(
        "SELECT ts_utc, rule_id, payload_json FROM audit_log "
        "WHERE event_type = 'ORDER_PAPER_FILLED' AND ts_utc >= ? AND ts_utc < ? "
        "ORDER BY seq",
        (since, until),
    ):
        p = json.loads(row["payload_json"])
        fills.append(
            FillRecord(
                symbol=p["symbol"],
                side=p["side"],
                qty=int(p["qty"]),
                price_usd=Decimal(str(p["simulated_fill_price_usd"])),
                ts_utc=row["ts_utc"],
                rule_id=p.get("rule_id") or row["rule_id"],
            )
        )
    return fills


def _read_live_fills(
    conn: sqlite3.Connection, since: str, until: str
) -> list[FillRecord]:
    # side 는 ORDER_INTENT 페이로드에 있다. correlation_id → side 매핑을 한 번에.
    side_by_corr: dict[str, str] = {}
    for row in conn.execute(
        "SELECT correlation_id, payload_json FROM audit_log "
        "WHERE event_type = 'ORDER_INTENT' AND correlation_id IS NOT NULL"
    ):
        p = json.loads(row["payload_json"])
        side = p.get("side")
        if side:
            side_by_corr[row["correlation_id"]] = side

    fills: list[FillRecord] = []
    for row in conn.execute(
        "SELECT ts_utc, rule_id, symbol, correlation_id, payload_json FROM audit_log "
        "WHERE event_type = 'FILL' AND ts_utc >= ? AND ts_utc < ? "
        "ORDER BY seq",
        (since, until),
    ):
        p = json.loads(row["payload_json"])
        corr = row["correlation_id"]
        side = side_by_corr.get(corr) if corr else None
        if side is None or not row["symbol"]:
            # side/symbol 을 확정 못 하면 손익 재구성에서 제외 (데이터 품질).
            continue
        fills.append(
            FillRecord(
                symbol=row["symbol"],
                side=side,
                qty=int(p["qty"]),
                price_usd=Decimal(str(p["price_usd"])),
                ts_utc=row["ts_utc"],
                rule_id=row["rule_id"],
            )
        )
    return fills


# ------------------------------------------------------------- reconstruction


def reconstruct(
    fills: list[FillRecord],
) -> tuple[dict[str, PositionState], dict[str, RulePerformance], Decimal, list[str]]:
    """체결 시퀀스로부터 종목별 포지션·룰별 성과·총 투입액·경고를 재구성.

    평균단가 기준:
      - BUY: 가중평균으로 avg_cost 갱신, qty += 매수량, gross_invested += 체결액.
      - SELL: realized += (체결가 − avg_cost) × 매도량, qty −= 매도량.

    SELL 수량이 보유를 초과하면(공매도/데이터 품질 문제) 경고를 남기고 보유
    수량까지만 실현 손익을 계산한다(음수 포지션을 만들지 않는다).
    """
    positions: dict[str, PositionState] = {}
    rules: dict[str, RulePerformance] = {}
    gross_invested = Decimal("0")
    warnings: list[str] = []

    for f in fills:
        pos = positions.get(f.symbol)
        if pos is None:
            pos = PositionState(f.symbol, 0, Decimal("0"), Decimal("0"))
            positions[f.symbol] = pos
        rid = f.rule_id or "(unknown)"
        rp = rules.get(rid)
        if rp is None:
            rp = RulePerformance(rid, Decimal("0"), 0, 0, 0)
            rules[rid] = rp
        rp.fills += 1

        if f.side == "BUY":
            new_qty = pos.qty + f.qty
            new_total = pos.avg_cost_usd * Decimal(pos.qty) + f.price_usd * Decimal(f.qty)
            pos.avg_cost_usd = new_total / Decimal(new_qty) if new_qty else Decimal("0")
            pos.qty = new_qty
            gross_invested += f.price_usd * Decimal(f.qty)
            rp.buys += 1
        elif f.side == "SELL":
            sell_qty = f.qty
            if sell_qty > pos.qty:
                warnings.append(
                    f"{f.symbol}: 매도 수량 {sell_qty} > 보유 {pos.qty} "
                    f"@ {f.ts_utc} — 보유분까지만 실현 처리"
                )
                sell_qty = pos.qty
            realized = (f.price_usd - pos.avg_cost_usd) * Decimal(sell_qty)
            pos.realized_pnl_usd += realized
            pos.qty -= sell_qty
            rp.realized_pnl_usd += realized
            rp.sells += 1
        else:
            warnings.append(f"{f.symbol}: 알 수 없는 side {f.side!r} @ {f.ts_utc}")

    return positions, rules, gross_invested, warnings


def compute_performance(
    fills: list[FillRecord],
    marks: dict[str, Decimal],
    *,
    mode: str,
    since: datetime,
    until: datetime,
) -> PerformanceReport:
    """정규화된 체결 + 시세(marks)로 성과 리포트를 합성한다. 순수 함수."""
    positions, rules, gross_invested, warnings = reconstruct(fills)

    per_symbol: list[SymbolPerformance] = []
    unmarked: list[str] = []
    total_realized = Decimal("0")
    total_unrealized = Decimal("0")

    for sym in sorted(positions):
        pos = positions[sym]
        total_realized += pos.realized_pnl_usd
        unrealized: Decimal | None = None
        mark: Decimal | None = None
        market_value: Decimal | None = None
        if pos.qty != 0:
            mark = marks.get(sym)
            if mark is None:
                unmarked.append(sym)
            else:
                unrealized = (mark - pos.avg_cost_usd) * Decimal(pos.qty)
                market_value = mark * Decimal(pos.qty)
                total_unrealized += unrealized
        per_symbol.append(
            SymbolPerformance(
                symbol=sym,
                qty=pos.qty,
                avg_cost_usd=pos.avg_cost_usd,
                realized_pnl_usd=pos.realized_pnl_usd,
                unrealized_pnl_usd=unrealized,
                mark_price_usd=mark,
                market_value_usd=market_value,
            )
        )

    total_pnl = total_realized + total_unrealized
    return_pct = (
        (total_pnl / gross_invested) * Decimal("100")
        if gross_invested > 0
        else None
    )

    per_rule = sorted(rules.values(), key=lambda r: r.rule_id)

    return PerformanceReport(
        mode=mode,
        period_since_utc=_fmt_ts(since),
        period_until_utc=_fmt_ts(until),
        fills_count=len(fills),
        gross_invested_usd=gross_invested,
        realized_pnl_usd=total_realized,
        unrealized_pnl_usd=total_unrealized,
        total_pnl_usd=total_pnl,
        return_pct=return_pct,
        per_symbol=per_symbol,
        per_rule=per_rule,
        unmarked_symbols=sorted(unmarked),
        data_quality_warnings=warnings,
    )


def build_performance_report(
    conn: sqlite3.Connection,
    *,
    mode: str,
    since: datetime,
    until: datetime,
    marks: dict[str, Decimal] | None = None,
) -> PerformanceReport:
    """audit_log 에서 체결을 읽어 성과 리포트를 만든다 (read-only 진입점)."""
    fills = read_fills(conn, mode=mode, since=since, until=until)
    return compute_performance(
        fills, marks or {}, mode=mode, since=since, until=until
    )


# --------------------------------------------------------------- text render


def _money(v: Decimal | None) -> str:
    if v is None:
        return "조회 불가"
    return f"{v.quantize(Decimal('0.01')):+}"


def render_text(report: PerformanceReport) -> str:
    lines: list[str] = []
    lines.append("auto-invest performance")
    lines.append("=" * 23)
    lines.append(f"Mode:          {report.mode}")
    lines.append(f"Period:        {report.period_since_utc} ~ {report.period_until_utc}")
    lines.append(f"Fills:         {report.fills_count}")
    lines.append(f"Invested:      ${report.gross_invested_usd.quantize(Decimal('0.01'))}")
    lines.append("")
    lines.append("PnL summary")
    lines.append("-" * 11)
    lines.append(f"Realized:      ${_money(report.realized_pnl_usd)}")
    lines.append(f"Unrealized:    ${_money(report.unrealized_pnl_usd)}")
    lines.append(f"Total:         ${_money(report.total_pnl_usd)}")
    if report.return_pct is None:
        lines.append("Return:        N/A (투입 자본 없음)")
    else:
        ret = report.return_pct.quantize(Decimal("0.01"))
        lines.append(f"Return:        {ret:+}% (투입 자본 대비)")
    if report.unmarked_symbols:
        lines.append(
            f"⚠ 시세 조회 불가 (미실현 미반영): {', '.join(report.unmarked_symbols)}"
        )
    lines.append("")
    lines.append("Per-symbol")
    lines.append("-" * 10)
    lines.append("symbol   qty   avg_cost   mark      realized    unrealized")
    if not report.per_symbol:
        lines.append("(no fills in this period)")
    for p in report.per_symbol:
        mark = "--" if p.mark_price_usd is None else f"{p.mark_price_usd.quantize(Decimal('0.01'))}"
        lines.append(
            f"{p.symbol:<7}  {p.qty:>3}   "
            f"{p.avg_cost_usd.quantize(Decimal('0.01')):>8}   {mark:>8}   "
            f"{_money(p.realized_pnl_usd):>9}   {_money(p.unrealized_pnl_usd):>10}"
        )
    lines.append("")
    lines.append("Per-rule")
    lines.append("-" * 8)
    lines.append("rule_id          fills  buys  sells   realized")
    if not report.per_rule:
        lines.append("(no fills in this period)")
    for r in report.per_rule:
        lines.append(
            f"{r.rule_id:<16} {r.fills:>5}  {r.buys:>4}  {r.sells:>5}   "
            f"{_money(r.realized_pnl_usd):>9}"
        )
    if report.data_quality_warnings:
        lines.append("")
        lines.append("Data-quality warnings")
        lines.append("-" * 21)
        for w in report.data_quality_warnings:
            lines.append(f"  ⚠ {w}")
    return "\n".join(lines)
