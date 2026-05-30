"""Spec 029 슬라이스 1 — 포트폴리오 순자산(NAV) 스냅샷 (순수·결정론·읽기 전용).

설계 원칙 (스펙 011 성과 엔진과 동일):
  - 순수 함수. 외부 API 를 호출하지 않는다 — CLI 계층이 KIS 잔고·보유·시세를 조회해
    주입한다(테스트 가능성). DB 에 어떤 row 도 쓰지 않는다.
  - 권위 출처는 **브로커**(실제 계좌). 브로커 잔고·보유가 주어지면 그것을 NAV 의
    기준으로 삼고, 없으면(오프라인/조회 실패) 내부 장부 + 시세로 폴백한다.
  - 원가 규약은 평균단가(스펙 009/011 과 동일, 헌법 X.2 단일 잣대). 미실현 손익은
    (현재가 − 평균단가) × 수량. 시세 없는 종목은 평균단가로 보수 평가하고 "측정 불가"
    로 분리한다.
  - 드리프트(브로커 vs 장부)는 보고만 한다. halt/주문/정정 0건 — 측정 전용.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from auto_invest.broker.models import PositionSnapshot
from auto_invest.performance.engine import PositionState

# 출처 표식.
SOURCE_BROKER = "broker"  # 브로커 잔고·보유를 NAV 기준으로 사용
SOURCE_LEDGER = "ledger"  # 브로커 정보 없음 — 내부 장부 + 시세로 폴백


@dataclass(frozen=True)
class NavHolding:
    """순자산 스냅샷의 종목 한 줄."""

    symbol: str
    qty: int
    avg_cost_usd: Decimal
    mark_price_usd: Decimal | None  # 현재 시세 (없으면 None)
    market_value_usd: Decimal  # 평가금액 (시세 없으면 평균단가 × 수량 — 보수)
    marked: bool  # True = 현재 시세로 평가, False = 평균단가 폴백
    weight_pct: Decimal | None  # 평가금액 / 총 순자산 × 100 (NAV 0 이면 None)
    unrealized_pnl_usd: Decimal | None  # (현재가 − 평단) × 수량 (시세 없으면 None)


@dataclass(frozen=True)
class NavDrift:
    """한 종목의 브로커 vs 장부 차이. 측정 전용 신호."""

    symbol: str
    broker_qty: int
    ledger_qty: int
    qty_drift: int  # 브로커 − 장부 (양수 = 브로커가 더 보유)
    market_value_drift_usd: Decimal  # 브로커평가 − 장부평가 (같은 시세로 평가)
    status: str  # "match" | "qty_mismatch" | "broker_only" | "ledger_only"


@dataclass(frozen=True)
class NavSnapshot:
    """한 시점의 포트폴리오 순자산 그림 (측정 전용)."""

    source: str  # SOURCE_BROKER | SOURCE_LEDGER
    cash_usd: Decimal
    holdings: list[NavHolding]
    total_market_value_usd: Decimal  # 보유 평가금액 합
    total_nav_usd: Decimal  # 현금 + 평가금액 합
    total_unrealized_pnl_usd: Decimal  # 측정 가능 종목의 미실현 손익 합
    unmarked_symbols: list[str]  # 시세 조회 못 해 평균단가로 평가한 종목
    # 브로커가 직접 보고한 총 평가금액(KIS 자체 계산) — 우리 계산과의 교차 검증용.
    broker_reported_nav_usd: Decimal | None
    drifts: list[NavDrift]
    total_qty_drift: int  # 종목별 |qty_drift| 합
    total_value_drift_usd: Decimal  # 종목별 market_value_drift 합 (부호 보존)
    data_quality_warnings: list[str] = field(default_factory=list)

    SCHEMA_VERSION = "1.0"

    def to_json_dict(self) -> dict:
        def _s(v: Decimal | None) -> str | None:
            return None if v is None else str(v)

        return {
            "schema_version": self.SCHEMA_VERSION,
            "source": self.source,
            "cash_usd": str(self.cash_usd),
            "total_market_value_usd": str(self.total_market_value_usd),
            "total_nav_usd": str(self.total_nav_usd),
            "total_unrealized_pnl_usd": str(self.total_unrealized_pnl_usd),
            "broker_reported_nav_usd": _s(self.broker_reported_nav_usd),
            "holdings": [
                {
                    "symbol": h.symbol,
                    "qty": h.qty,
                    "avg_cost_usd": str(h.avg_cost_usd),
                    "mark_price_usd": _s(h.mark_price_usd),
                    "market_value_usd": str(h.market_value_usd),
                    "marked": h.marked,
                    "weight_pct": _s(h.weight_pct),
                    "unrealized_pnl_usd": _s(h.unrealized_pnl_usd),
                }
                for h in self.holdings
            ],
            "unmarked_symbols": self.unmarked_symbols,
            "drifts": [
                {
                    "symbol": d.symbol,
                    "broker_qty": d.broker_qty,
                    "ledger_qty": d.ledger_qty,
                    "qty_drift": d.qty_drift,
                    "market_value_drift_usd": str(d.market_value_drift_usd),
                    "status": d.status,
                }
                for d in self.drifts
            ],
            "total_qty_drift": self.total_qty_drift,
            "total_value_drift_usd": str(self.total_value_drift_usd),
            "data_quality_warnings": self.data_quality_warnings,
        }


# 슬라이스 2 — 자산 인식 유효 자본 기본값.
DEFAULT_MAX_GROWTH_FACTOR = Decimal("2")


def effective_capital(
    starting_capital_usd: Decimal,
    nav_usd: Decimal | None,
    *,
    growth_enabled: bool = False,
    max_growth_factor: Decimal = DEFAULT_MAX_GROWTH_FACTOR,
) -> Decimal:
    """게이트에 넘길 유효 자본을 결정론적으로 계산한다 (슬라이스 2, FR-08~FR-11).

    설계 원칙 — 방어는 항상, 성장은 옵트인:
      - nav 가 None/0 이하(조회 실패·미측정)면 시작 자본 폴백 (거래 무중단, FR-11).
      - 하락(nav < starting)은 **항상** nav 를 쓴다 — 손실 구간에서 캡이 자동으로 줄어든다
        (방어, growth_enabled 무관, FR-09).
      - 상승(nav > starting)은 growth_enabled=True 일 때만 반영하고, starting ×
        max_growth_factor 로 하드 클램프해 폭주를 막는다 (FR-10). growth_enabled=False
        면 시작 자본이 천장(슬라이스 1 이전 동작과 동일).

    유효 자본은 게이트가 캡을 계산하는 "자본 기준"일 뿐이다. K1 게이트의 거부 로직·
    퍼센트는 무변경 — 캡 = 유효자본 × pct 의 입력만 살아있는 자산을 따라간다.
    """
    if nav_usd is None or nav_usd <= 0:
        return starting_capital_usd
    if nav_usd < starting_capital_usd:
        return nav_usd  # 방어: 항상 줄인다.
    # 여기부터 nav >= starting (상승 또는 동일).
    if not growth_enabled:
        return starting_capital_usd
    ceiling = starting_capital_usd * max_growth_factor
    return min(nav_usd, ceiling)


def _market_value(
    qty: int, avg_cost_usd: Decimal, mark: Decimal | None
) -> tuple[Decimal, bool]:
    """평가금액과 marked 플래그를 반환. 시세 없으면 평균단가로 보수 평가."""
    if mark is not None:
        return mark * Decimal(qty), True
    return avg_cost_usd * Decimal(qty), False


def compute_nav(
    *,
    broker_cash_usd: Decimal | None,
    broker_positions: list[PositionSnapshot] | None,
    broker_reported_total_value_usd: Decimal | None,
    ledger_positions: dict[str, PositionState],
    marks: dict[str, Decimal],
) -> NavSnapshot:
    """포트폴리오 순자산 스냅샷을 결정론적으로 계산한다 (FR-01~FR-05, FR-08).

    권위 출처는 브로커다. `broker_cash_usd` 가 주어지면 (None 아님) 브로커 보유를 NAV
    기준으로 쓰고 source="broker", 아니면 내부 장부 + 시세로 폴백해 source="ledger".
    어느 경우든 드리프트(브로커 vs 장부)는 둘 다 있으면 계산한다.

    marks 는 {symbol: 현재가}. 없는 종목은 평균단가로 보수 평가하고 unmarked 로 분리.
    """
    warnings: list[str] = []
    use_broker = broker_cash_usd is not None
    source = SOURCE_BROKER if use_broker else SOURCE_LEDGER

    # NAV 기준이 되는 보유: 브로커가 있으면 브로커, 없으면 장부의 보유분(qty>0).
    if use_broker:
        basis: dict[str, tuple[int, Decimal]] = {
            p.symbol: (p.qty, p.avg_cost_usd) for p in (broker_positions or [])
        }
    else:
        basis = {
            s: (st.qty, st.avg_cost_usd)
            for s, st in ledger_positions.items()
            if st.qty != 0
        }

    cash_usd = broker_cash_usd if broker_cash_usd is not None else Decimal("0")

    # 1차 패스: 평가금액·미실현 계산 (비중은 NAV 확정 후 2차 패스).
    unmarked: list[str] = []
    raw: list[tuple[str, int, Decimal, Decimal | None, Decimal, bool, Decimal | None]] = []
    total_market_value = Decimal("0")
    total_unrealized = Decimal("0")
    for symbol in sorted(basis):
        qty, avg_cost = basis[symbol]
        mark = marks.get(symbol)
        mv, marked = _market_value(qty, avg_cost, mark)
        total_market_value += mv
        unrealized: Decimal | None
        if marked and qty != 0:
            unrealized = (mark - avg_cost) * Decimal(qty)  # type: ignore[operator]
            total_unrealized += unrealized
        else:
            unrealized = None
            if qty != 0:
                unmarked.append(symbol)
        raw.append((symbol, qty, avg_cost, mark, mv, marked, unrealized))

    total_nav = cash_usd + total_market_value

    # 2차 패스: 비중(평가금액 / NAV × 100). NAV 0 이면 None (0 나눗셈 방지, FR-03).
    holdings: list[NavHolding] = []
    for symbol, qty, avg_cost, mark, mv, marked, unrealized in raw:
        weight = (mv / total_nav * Decimal(100)) if total_nav > 0 else None
        holdings.append(
            NavHolding(
                symbol=symbol,
                qty=qty,
                avg_cost_usd=avg_cost,
                mark_price_usd=mark,
                market_value_usd=mv,
                marked=marked,
                weight_pct=weight,
                unrealized_pnl_usd=unrealized,
            )
        )

    drifts, total_qty_drift, total_value_drift = _compute_drifts(
        broker_positions=broker_positions,
        ledger_positions=ledger_positions,
        marks=marks,
    )

    if (
        broker_reported_total_value_usd is not None
        and total_nav > 0
        and broker_reported_total_value_usd > 0
    ):
        gap = abs(broker_reported_total_value_usd - total_nav)
        # 브로커 자체 보고 NAV 와 우리 계산이 5% 넘게 벌어지면 데이터 품질 경고.
        if gap / total_nav > Decimal("0.05"):
            warnings.append(
                f"브로커 보고 순자산(${broker_reported_total_value_usd})과 계산 순자산"
                f"(${total_nav}) 차이 {gap} (시세 지연/환차/누락 체결 가능성)"
            )

    return NavSnapshot(
        source=source,
        cash_usd=cash_usd,
        holdings=holdings,
        total_market_value_usd=total_market_value,
        total_nav_usd=total_nav,
        total_unrealized_pnl_usd=total_unrealized,
        unmarked_symbols=unmarked,
        broker_reported_nav_usd=broker_reported_total_value_usd,
        drifts=drifts,
        total_qty_drift=total_qty_drift,
        total_value_drift_usd=total_value_drift,
        data_quality_warnings=warnings,
    )


def _compute_drifts(
    *,
    broker_positions: list[PositionSnapshot] | None,
    ledger_positions: dict[str, PositionState],
    marks: dict[str, Decimal],
) -> tuple[list[NavDrift], int, Decimal]:
    """브로커 vs 장부 보유를 종목별로 대조 (FR-04, FR-05).

    브로커 정보가 없으면 드리프트 계산 불가 → 빈 목록. 한쪽에만 있는 종목은
    broker_only / ledger_only 로 표기한다. 평가 차이는 같은 시세(없으면 평균단가)로
    잰다.
    """
    if broker_positions is None:
        return [], 0, Decimal("0")

    broker_qty: dict[str, tuple[int, Decimal]] = {
        p.symbol: (p.qty, p.avg_cost_usd) for p in broker_positions
    }
    ledger_qty: dict[str, tuple[int, Decimal]] = {
        s: (st.qty, st.avg_cost_usd)
        for s, st in ledger_positions.items()
        if st.qty != 0
    }

    drifts: list[NavDrift] = []
    total_qty_drift = 0
    total_value_drift = Decimal("0")
    for symbol in sorted(set(broker_qty) | set(ledger_qty)):
        b_qty, b_avg = broker_qty.get(symbol, (0, Decimal("0")))
        l_qty, l_avg = ledger_qty.get(symbol, (0, Decimal("0")))
        qty_drift = b_qty - l_qty
        mark = marks.get(symbol)
        b_price = mark if mark is not None else b_avg
        l_price = mark if mark is not None else l_avg
        value_drift = b_price * Decimal(b_qty) - l_price * Decimal(l_qty)

        if symbol not in ledger_qty:
            status = "broker_only"
        elif symbol not in broker_qty:
            status = "ledger_only"
        elif qty_drift == 0:
            status = "match"
        else:
            status = "qty_mismatch"

        total_qty_drift += abs(qty_drift)
        total_value_drift += value_drift
        drifts.append(
            NavDrift(
                symbol=symbol,
                broker_qty=b_qty,
                ledger_qty=l_qty,
                qty_drift=qty_drift,
                market_value_drift_usd=value_drift,
                status=status,
            )
        )
    return drifts, total_qty_drift, total_value_drift


def _money(v: Decimal | None) -> str:
    return "N/A" if v is None else f"${v:,.2f}"


def _pct(v: Decimal | None) -> str:
    return "N/A" if v is None else f"{v:.1f}%"


def render_text(snap: NavSnapshot) -> str:
    """사람용 표. CLI text 모드 출력."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(f"포트폴리오 순자산 (출처: {snap.source})")
    lines.append("=" * 60)
    lines.append(f"현금        : {_money(snap.cash_usd)}")
    lines.append(f"보유 평가   : {_money(snap.total_market_value_usd)}")
    lines.append(f"총 순자산   : {_money(snap.total_nav_usd)}")
    lines.append(f"미실현 손익 : {_money(snap.total_unrealized_pnl_usd)}")
    if snap.broker_reported_nav_usd is not None:
        lines.append(f"브로커 보고 : {_money(snap.broker_reported_nav_usd)}")
    lines.append("")
    if snap.holdings:
        lines.append(
            f"{'종목':<8}{'수량':>6}{'평단':>12}{'현재가':>12}"
            f"{'평가금액':>14}{'비중':>8}{'미실현':>14}"
        )
        lines.append("-" * 74)
        for h in snap.holdings:
            mk = "" if h.marked else "*"
            lines.append(
                f"{h.symbol:<8}{h.qty:>6}{_money(h.avg_cost_usd):>12}"
                f"{_money(h.mark_price_usd):>12}{_money(h.market_value_usd) + mk:>14}"
                f"{_pct(h.weight_pct):>8}{_money(h.unrealized_pnl_usd):>14}"
            )
    else:
        lines.append("(보유 종목 없음)")
    if snap.unmarked_symbols:
        lines.append("")
        lines.append(
            f"* 시세 조회 불가 — 평균단가로 보수 평가: {', '.join(snap.unmarked_symbols)}"
        )
    # 드리프트 — 불일치 종목만 표시.
    mismatches = [d for d in snap.drifts if d.status != "match"]
    if mismatches:
        lines.append("")
        lines.append("브로커 vs 장부 드리프트:")
        for d in mismatches:
            lines.append(
                f"  {d.symbol:<8} 브로커 {d.broker_qty} / 장부 {d.ledger_qty} "
                f"(차이 {d.qty_drift:+d}, {_money(d.market_value_drift_usd)}) [{d.status}]"
            )
        lines.append(
            f"  합계: 수량 드리프트 {snap.total_qty_drift}, "
            f"평가 드리프트 {_money(snap.total_value_drift_usd)}"
        )
    elif snap.drifts:
        lines.append("")
        lines.append("브로커 vs 장부: 일치 ✓")
    for w in snap.data_quality_warnings:
        lines.append(f"⚠ {w}")
    return "\n".join(lines)
