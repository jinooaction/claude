"""Rejected-order opportunity diagnostics for operator visibility.

This module is read-only: it interprets a rebalance result and optional current
marks, then reports what the rejected order would be worth at the mark time.
It does not submit, cancel, retry, or alter orders.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_CENT = Decimal("0.01")
_PCT = Decimal("0.01")
_REJECTED_STATES = frozenset({"REJECTED_BY_BROKER", "REJECTED_BY_GATE"})


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dec(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _qty(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _money(value: Decimal | None, *, signed: bool = False) -> str | None:
    if value is None:
        return None
    q = value.quantize(_CENT)
    sign = "+" if signed else ""
    return f"{q:{sign},.2f}"


def _pct(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value.quantize(_PCT):+,.2f}%"


@dataclass(frozen=True)
class RejectedOrderOpportunity:
    symbol: str
    side: str
    state: str
    qty: int
    intended_price_usd: Decimal
    intended_notional_usd: Decimal
    current_mark_usd: Decimal | None
    opportunity_pnl_usd: Decimal | None
    opportunity_return_pct: Decimal | None
    reason: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "state": self.state,
            "qty": self.qty,
            "intended_price_usd": str(self.intended_price_usd),
            "intended_notional_usd": _money(self.intended_notional_usd),
            "current_mark_usd": (
                None if self.current_mark_usd is None else str(self.current_mark_usd)
            ),
            "opportunity_pnl_usd": _money(self.opportunity_pnl_usd, signed=True),
            "opportunity_return_pct": _pct(self.opportunity_return_pct),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RejectedOrderOpportunityReport:
    as_of_utc: str
    rows: tuple[RejectedOrderOpportunity, ...]
    mark_fetch_error: str | None = None

    @property
    def rejected_count(self) -> int:
        return len(self.rows)

    @property
    def valued_count(self) -> int:
        return sum(1 for row in self.rows if row.opportunity_pnl_usd is not None)

    @property
    def missing_mark_symbols(self) -> tuple[str, ...]:
        return tuple(
            sorted(row.symbol for row in self.rows if row.current_mark_usd is None)
        )

    @property
    def total_opportunity_pnl_usd(self) -> Decimal:
        return sum(
            (
                row.opportunity_pnl_usd
                for row in self.rows
                if row.opportunity_pnl_usd is not None
            ),
            Decimal("0"),
        )

    @property
    def buy_opportunity_pnl_usd(self) -> Decimal:
        return sum(
            (
                row.opportunity_pnl_usd
                for row in self.rows
                if row.side == "BUY" and row.opportunity_pnl_usd is not None
            ),
            Decimal("0"),
        )

    @property
    def sell_opportunity_pnl_usd(self) -> Decimal:
        return sum(
            (
                row.opportunity_pnl_usd
                for row in self.rows
                if row.side == "SELL" and row.opportunity_pnl_usd is not None
            ),
            Decimal("0"),
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "as_of_utc": self.as_of_utc,
            "definition": (
                "positive means the rejected order would be more favorable at the "
                "current mark; "
                "negative means rejection was more favorable before fees, tax, FX, and fill risk"
            ),
            "rejected_count": self.rejected_count,
            "valued_count": self.valued_count,
            "missing_mark_symbols": list(self.missing_mark_symbols),
            "mark_fetch_error": self.mark_fetch_error,
            "total_opportunity_pnl_usd": _money(
                self.total_opportunity_pnl_usd,
                signed=True,
            ),
            "buy_opportunity_pnl_usd": _money(self.buy_opportunity_pnl_usd, signed=True),
            "sell_opportunity_pnl_usd": _money(
                self.sell_opportunity_pnl_usd,
                signed=True,
            ),
            "rows": [row.to_json_dict() for row in self.rows],
        }


def rejected_order_symbols(rebalance_result: Mapping[str, Any]) -> tuple[str, ...]:
    symbols: set[str] = set()
    for raw in rebalance_result.get("results") or []:
        if not isinstance(raw, Mapping):
            continue
        state = str(raw.get("state") or "").upper()
        if state not in _REJECTED_STATES:
            continue
        symbol = str(raw.get("symbol") or "").upper().strip()
        if symbol:
            symbols.add(symbol)
    return tuple(sorted(symbols))


def build_rejected_order_opportunity_report(
    rebalance_result: Mapping[str, Any],
    marks: Mapping[str, Decimal | str | int | float] | None = None,
    *,
    as_of_utc: str | None = None,
    mark_fetch_error: str | None = None,
) -> RejectedOrderOpportunityReport:
    marks_by_symbol = {
        str(symbol).upper(): mark
        for symbol, mark in (marks or {}).items()
        if str(symbol).strip()
    }
    rows: list[RejectedOrderOpportunity] = []
    for raw in rebalance_result.get("results") or []:
        if not isinstance(raw, Mapping):
            continue
        state = str(raw.get("state") or "").upper()
        if state not in _REJECTED_STATES:
            continue
        side = str(raw.get("side") or "").upper()
        if side not in {"BUY", "SELL"}:
            continue
        symbol = str(raw.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        qty = _qty(raw.get("routed_qty")) or _qty(raw.get("requested_qty"))
        price = _dec(raw.get("limit_price_usd"))
        if qty <= 0 or price is None or price <= 0:
            continue
        mark = _dec(marks_by_symbol.get(symbol))
        notional = Decimal(qty) * price
        pnl: Decimal | None = None
        ret: Decimal | None = None
        if mark is not None and mark > 0:
            pnl = (
                (mark - price) * Decimal(qty)
                if side == "BUY"
                else (price - mark) * Decimal(qty)
            )
            ret = (pnl / notional) * Decimal("100") if notional else None
        rows.append(
            RejectedOrderOpportunity(
                symbol=symbol,
                side=side,
                state=state,
                qty=qty,
                intended_price_usd=price,
                intended_notional_usd=notional,
                current_mark_usd=mark,
                opportunity_pnl_usd=pnl,
                opportunity_return_pct=ret,
                reason=(
                    str(raw.get("reason"))
                    if raw.get("reason") not in (None, "")
                    else None
                ),
            )
        )
    return RejectedOrderOpportunityReport(
        as_of_utc=as_of_utc or _now_iso(),
        rows=tuple(rows),
        mark_fetch_error=mark_fetch_error,
    )


def render_rejected_order_opportunity_text(
    report: RejectedOrderOpportunityReport,
) -> str:
    lines = [
        "거부 주문 기회손익(현재가 기준)",
        "기준: 양수=거부 주문이 체결됐으면 현재 더 유리, 음수=거부가 결과적으로 유리.",
        f"as_of_utc={report.as_of_utc}",
        (
            "총계: "
            f"{_money(report.total_opportunity_pnl_usd, signed=True)} USD "
            f"(매수 {_money(report.buy_opportunity_pnl_usd, signed=True)}, "
            f"매도 {_money(report.sell_opportunity_pnl_usd, signed=True)}, "
            f"평가 {report.valued_count}/{report.rejected_count}건)"
        ),
    ]
    if report.mark_fetch_error:
        lines.append(f"현재가 조회 오류: {report.mark_fetch_error}")
    if report.missing_mark_symbols:
        lines.append("현재가 없음: " + ", ".join(report.missing_mark_symbols))
    if not report.rows:
        lines.append("거부된 주문: 0건")
    for row in report.rows:
        mark = "N/A" if row.current_mark_usd is None else str(row.current_mark_usd)
        pnl = _money(row.opportunity_pnl_usd, signed=True) or "N/A"
        pct = _pct(row.opportunity_return_pct) or "N/A"
        reason = f" reason={row.reason}" if row.reason else ""
        lines.append(
            f"- {row.symbol} {row.side} {row.qty}주 @{row.intended_price_usd} "
            f"-> mark {mark}: {pnl} USD ({pct}){reason}"
        )
    lines.append("주의: 수수료, 세금, 환율, 실제 체결 가능성은 제외한 단순 현재가 비교입니다.")
    return "\n".join(lines)


__all__ = [
    "RejectedOrderOpportunity",
    "RejectedOrderOpportunityReport",
    "build_rejected_order_opportunity_report",
    "rejected_order_symbols",
    "render_rejected_order_opportunity_text",
]
