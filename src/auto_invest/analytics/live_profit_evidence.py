"""Spec 143: fail-closed first live profit evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation

STATUS_UNKNOWN = "UNKNOWN"
STATUS_NO_FILLS = "NO_FILLS_YET"
STATUS_INCOMPLETE = "PNL_INCOMPLETE"
STATUS_NOT_PROFITABLE = "FILLED_NOT_PROFITABLE"
STATUS_FIRST_PROFIT = "FIRST_PROFIT_OBSERVED"


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _string_list(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    return tuple(str(item) for item in value)


@dataclass(frozen=True)
class LiveProfitEvidence:
    schema_version: str
    status: str
    current_status: str
    first_profit_observed: bool
    first_profit_observed_at_utc: str | None
    first_profit_fills_count: int | None
    first_profit_realized_pnl_usd: str | None
    first_profit_unrealized_pnl_usd: str | None
    first_profit_total_pnl_usd: str | None
    observed_at_utc: str
    fills_count: int | None
    gross_invested_usd: str | None
    realized_pnl_usd: str | None
    unrealized_pnl_usd: str | None
    total_pnl_usd: str | None
    return_pct: str | None
    unmarked_symbols: tuple[str, ...]
    data_quality_warnings: tuple[str, ...]
    source_run_id: str
    detail: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["unmarked_symbols"] = list(self.unmarked_symbols)
        payload["data_quality_warnings"] = list(self.data_quality_warnings)
        return payload

    def as_markdown(self) -> str:
        first = (
            f"{self.first_profit_observed_at_utc} / "
            f"${self.first_profit_total_pnl_usd}"
            if self.first_profit_observed
            else "아직 없음"
        )
        fills = "불명" if self.fills_count is None else str(self.fills_count)
        total = "불명" if self.total_pnl_usd is None else f"${self.total_pnl_usd}"
        lines = [
            f"# 실계좌 첫 수익 증거 (as of {self.observed_at_utc})",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| 누적 판정 | {self.status} |",
            f"| 현재 관측 판정 | {self.current_status} |",
            f"| live 체결 수 | {fills} |",
            f"| 현재 실현 손익 | {self.realized_pnl_usd or '불명'} |",
            f"| 현재 미실현 손익 | {self.unrealized_pnl_usd or '불명'} |",
            f"| 현재 총손익 | {total} |",
            f"| 시세 결측 종목 | {', '.join(self.unmarked_symbols) or '없음'} |",
            f"| 데이터 경고 | {len(self.data_quality_warnings)}건 |",
            f"| 최초 양의 손익 | {first} |",
            f"| 판정 근거 | {self.detail} |",
            "",
            "> 이 보고서는 주문을 제출하거나 취소하지 않는다. 실제 수익을 보장하지 않으며,",
            "> 체결·시세·손익 증거가 완전할 때만 최초 수익을 인정한다.",
        ]
        return "\n".join(lines)


def _prior_first(prior: dict | None) -> tuple[bool, dict]:
    if not isinstance(prior, dict):
        return False, {}
    first_fills = _int(prior.get("first_profit_fills_count"))
    first_total = _decimal(prior.get("first_profit_total_pnl_usd"))
    first_at = prior.get("first_profit_observed_at_utc")
    achieved_flag = bool(prior.get("first_profit_observed")) and (
        prior.get("status") == STATUS_FIRST_PROFIT
    )
    achieved = (
        achieved_flag
        and isinstance(first_at, str)
        and bool(first_at)
        and first_fills is not None
        and first_fills > 0
        and first_total is not None
        and first_total > 0
    )
    return achieved, prior


def assess_live_profit(
    performance: dict | None,
    *,
    prior: dict | None,
    observed_at_utc: str,
    source_run_id: str,
) -> LiveProfitEvidence:
    prior_achieved, prior_data = _prior_first(prior)
    fills: int | None = None
    gross: Decimal | None = None
    realized: Decimal | None = None
    unrealized: Decimal | None = None
    total: Decimal | None = None
    return_pct: Decimal | None = None
    unmarked: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    valid = isinstance(performance, dict) and performance.get("mode") == "live"
    if valid:
        fills = _int(performance.get("fills_count"))
        gross = _decimal(performance.get("gross_invested_usd"))
        realized = _decimal(performance.get("realized_pnl_usd"))
        unrealized = _decimal(performance.get("unrealized_pnl_usd"))
        total = _decimal(performance.get("total_pnl_usd"))
        raw_return = performance.get("return_pct")
        return_pct = None if raw_return is None else _decimal(raw_return)
        parsed_unmarked = _string_list(performance.get("unmarked_symbols"))
        parsed_warnings = _string_list(performance.get("data_quality_warnings"))
        valid = (
            fills is not None
            and gross is not None
            and realized is not None
            and unrealized is not None
            and total is not None
            and parsed_unmarked is not None
            and parsed_warnings is not None
        )
        if parsed_unmarked is not None:
            unmarked = parsed_unmarked
        if parsed_warnings is not None:
            warnings = parsed_warnings

    if not valid:
        current_status = STATUS_UNKNOWN
        detail = "live 성과 JSON이 없거나 필수 필드가 불완전해 손익을 단정하지 않음."
    elif fills == 0:
        current_status = STATUS_NO_FILLS
        detail = "실제 live 체결이 0건이라 수익 판정 전 단계."
    elif unmarked or warnings:
        current_status = STATUS_INCOMPLETE
        detail = "체결은 있으나 시세 결측 또는 데이터 경고가 있어 양의 수익으로 인정하지 않음."
    elif total is not None and total > 0:
        current_status = STATUS_FIRST_PROFIT
        detail = "live 체결 1건 이상 + 결측·경고 0 + 총손익 > 0을 모두 확인."
    else:
        current_status = STATUS_NOT_PROFITABLE
        detail = "live 체결은 있으나 완전한 현재 총손익이 0 이하."

    achieved_now = current_status == STATUS_FIRST_PROFIT
    achieved = prior_achieved or achieved_now
    status = STATUS_FIRST_PROFIT if achieved else current_status

    if prior_achieved:
        first_at = prior_data.get("first_profit_observed_at_utc")
        first_fills = _int(prior_data.get("first_profit_fills_count"))
        first_realized = prior_data.get("first_profit_realized_pnl_usd")
        first_unrealized = prior_data.get("first_profit_unrealized_pnl_usd")
        first_total = prior_data.get("first_profit_total_pnl_usd")
    elif achieved_now:
        first_at = observed_at_utc
        first_fills = fills
        first_realized = str(realized)
        first_unrealized = str(unrealized)
        first_total = str(total)
    else:
        first_at = None
        first_fills = None
        first_realized = None
        first_unrealized = None
        first_total = None

    return LiveProfitEvidence(
        schema_version="1.0",
        status=status,
        current_status=current_status,
        first_profit_observed=achieved,
        first_profit_observed_at_utc=None if first_at is None else str(first_at),
        first_profit_fills_count=first_fills,
        first_profit_realized_pnl_usd=(
            None if first_realized is None else str(first_realized)
        ),
        first_profit_unrealized_pnl_usd=(
            None if first_unrealized is None else str(first_unrealized)
        ),
        first_profit_total_pnl_usd=None if first_total is None else str(first_total),
        observed_at_utc=observed_at_utc,
        fills_count=fills,
        gross_invested_usd=None if gross is None else str(gross),
        realized_pnl_usd=None if realized is None else str(realized),
        unrealized_pnl_usd=None if unrealized is None else str(unrealized),
        total_pnl_usd=None if total is None else str(total),
        return_pct=None if return_pct is None else str(return_pct),
        unmarked_symbols=unmarked,
        data_quality_warnings=warnings,
        source_run_id=source_run_id,
        detail=detail,
    )
