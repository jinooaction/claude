"""모바일용 자금·전략 공개 요약을 안전하게 조립한다.

이 모듈은 이미 발행된 사이드카와 확정 준비 계약만 읽는다. 원문을 전달하지 않고
명시적으로 허용한 필드만 새 문서에 복사하며, 계좌 집계 미완료 값은 숫자로 만들지 않는다.
브로커, 주문, 비밀값, SSH, 거래 데이터베이스에는 접근하지 않는다.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from auto_invest.analytics.capital_path_readiness import extract_json_after_header
from auto_invest.analytics.pipeline_liveness import (
    SidecarSpec,
    assess_liveness,
    parse_timestamp_utc,
)

SCHEMA_VERSION = "1.0"
MAX_AGE_MINUTES = 30 * 60

_MONEY_PATH_HEADER = "## 결정 JSON"
_JSON_DECODER = json.JSONDecoder()
_SAFE_SYMBOL = re.compile(r"^[A-Z0-9.\-]{1,12}$")

_RESEARCH_SPEC = SidecarSpec(
    key="autonomous-strategy-factory",
    branch="automation/autonomous-strategy-factory-last-run",
    filename="LAST_RUN.md",
    max_age_hours=30.0,
    critical=False,
    description="64개 후보 전체 다중검정 자동 전략 탐색(연구 전용)",
)
_LIVE_PROFIT_SPEC = SidecarSpec(
    key="live-profit-evidence",
    branch="automation/live-profit-evidence-last-run",
    filename="profit_evidence.json",
    max_age_hours=30.0,
    critical=False,
    description="실계좌 체결과 전략 범위 손익 증거(읽기 전용)",
)


def mobile_summary_sidecar_specs() -> tuple[SidecarSpec, ...]:
    """Extra source files needed by the capital and strategy summaries."""

    return (_LIVE_PROFIT_SPEC, _RESEARCH_SPEC)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _mapping(value: object) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _safe_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _safe_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _safe_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]+", value.strip()):
        return int(value)
    return None


def _safe_money(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    if not amount.is_finite():
        return None
    return format(amount, "f")


def _safe_timestamp(value: object) -> str | None:
    raw = _safe_string(value)
    if raw is None:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _latest_timestamp(*values: str | None) -> str | None:
    parsed: list[datetime] = []
    for value in values:
        safe = _safe_timestamp(value)
        if safe is not None:
            parsed.append(datetime.fromisoformat(safe.replace("Z", "+00:00")))
    if not parsed:
        return None
    return max(parsed).astimezone(UTC).isoformat().replace("+00:00", "Z")


def _extract_json_object_containing(raw: str | None, required_key: str) -> dict[str, Any] | None:
    """Find a complete JSON object in a mixed Markdown/log block."""

    if not raw:
        return None
    for match in re.finditer(r"\{", raw):
        try:
            value, _ = _JSON_DECODER.raw_decode(raw[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and required_key in value:
            return value
    return None


def _parse_money_path(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        value = extract_json_after_header(raw, _MONEY_PATH_HEADER)
    except (ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _account_summary(money_path: dict[str, Any] | None) -> dict[str, Any]:
    reason = (
        "실계좌 조회 행은 수집됐지만 총자산·현금·평가액 집계 계약은 아직 검증되지 않았습니다."
        if money_path is not None
        else "검증된 실계좌 집계 자료가 아직 없습니다."
    )
    return {
        "status": "UNVERIFIED",
        "currency": "USD",
        "total_assets_usd": None,
        "purchasable_cash_usd": None,
        "holdings_market_value_usd": None,
        "reason_code": "VERIFIED_ACCOUNT_AGGREGATE_REQUIRED",
        "reason_ko": reason,
        "protection": "DEVICE_AUTH_REQUIRED",
    }


def _live_allocation(money_path: dict[str, Any] | None) -> dict[str, Any] | None:
    if money_path is None:
        return None
    live_state = _mapping(money_path.get("live_money_state")) or {}
    capital = _safe_money(money_path.get("deployed_capital_usd"))
    if capital is None:
        capital = _safe_money(live_state.get("capital_usd"))
    return {
        "status": _safe_string(live_state.get("status")) or "UNKNOWN",
        "stage": _safe_string(money_path.get("stage")) or "UNKNOWN",
        "rung": _safe_int(money_path.get("current_rung")),
        "capital_pct": _safe_money(money_path.get("capital_pct")),
        "allocated_capital_usd": capital,
        "can_submit_real_orders": _safe_bool(live_state.get("can_submit_real_orders")),
        "next_scheduled_live_utc": _safe_timestamp(live_state.get("next_scheduled_live_utc")),
        "detail_ko": (
            "수익 우위가 확정된 전략이 아니라 주문·체결·정합성 배관을 검증하는 제한된 캐너리입니다."
        ),
    }


def _intraday_budget(
    budget: dict[str, Any] | None,
    preflight: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if budget is None:
        return None
    if _safe_string(budget.get("currency")) != "USD":
        return None
    fields = {
        key: _safe_money(budget.get(key))
        for key in (
            "capital_limit_usd",
            "order_limit_usd",
            "symbol_limit_usd",
            "total_exposure_limit_usd",
            "daily_stop_trigger_usd",
        )
    }
    if any(value is None for value in fields.values()):
        return None
    preflight_status = _safe_string(preflight.get("status")) if preflight else None
    live_eligible = _safe_bool(preflight.get("live_eligible")) if preflight else False
    orders_submitted = _safe_int(preflight.get("orders_submitted")) if preflight else 0
    return {
        "status": "PREPARATION_ONLY",
        "preflight_status": preflight_status or "UNAVAILABLE",
        "currency": "USD",
        **fields,
        "orders_enabled": _safe_bool(budget.get("orders_enabled")) is True,
        "live_eligible": live_eligible is True,
        "orders_submitted": orders_submitted,
        "confirmed_on": _safe_string(budget.get("confirmed_on")),
    }


def _performance(evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    if evidence is None:
        return None
    observed_at = _safe_timestamp(evidence.get("observed_at_utc"))
    scope = _safe_string(evidence.get("measurement_scope"))
    values = {
        key: _safe_money(evidence.get(key))
        for key in (
            "gross_invested_usd",
            "realized_pnl_usd",
            "unrealized_pnl_usd",
            "total_pnl_usd",
            "return_pct",
        )
    }
    fills = _safe_int(evidence.get("fills_count"))
    if observed_at is None or scope != "strategy" or fills is None:
        return None
    return {
        "status": _safe_string(evidence.get("status")) or "UNKNOWN",
        "measurement_scope": scope,
        "observed_at_utc": observed_at,
        "fills_count": fills,
        **values,
    }


def _risk(money_path: dict[str, Any] | None) -> dict[str, Any] | None:
    if money_path is None:
        return None
    budget = _mapping(money_path.get("safety_budget"))
    if budget is None:
        return None
    return {
        "reference_rung": _safe_int(budget.get("reference_rung")),
        "current_drawdown_pct": _safe_money(budget.get("current_dd_pct")),
        "demote_drawdown_pct": _safe_money(budget.get("demote_dd_pct")),
        "halt_drawdown_pct": _safe_money(budget.get("halt_dd_pct")),
        "loss_at_demote_usd": _safe_money(budget.get("loss_at_demote_usd")),
        "loss_at_halt_usd": _safe_money(budget.get("loss_at_halt_usd")),
    }


def _active_strategy(
    money_path: dict[str, Any] | None,
    live_canary_raw: str | None,
) -> dict[str, Any] | None:
    if money_path is None:
        return None
    revalidation = _extract_json_object_containing(live_canary_raw, "allowed")
    evidence = _mapping(revalidation.get("evidence")) if revalidation else None
    operational = _mapping(evidence.get("operational_assessment")) if evidence else None
    fundability = _mapping(evidence.get("fundability")) if evidence else None
    if evidence is None or operational is None:
        return None

    target_symbols: list[str] = []
    target_weights = _mapping(fundability.get("target_weights")) if fundability else None
    if target_weights:
        target_symbols = sorted(
            key for key in target_weights if isinstance(key, str) and _SAFE_SYMBOL.fullmatch(key)
        )

    live_state = _mapping(money_path.get("live_money_state")) or {}
    return {
        "strategy_id": _safe_string(operational.get("candidate_id")),
        "role": "OPERATIONAL_CANARY",
        "entry_route": _safe_string(money_path.get("entry_route")),
        "status": _safe_string(live_state.get("status")) or "UNKNOWN",
        "alpha_confirmed": _safe_bool(operational.get("alpha_confirmed")) is True,
        "rung": _safe_int(money_path.get("current_rung")),
        "capital_pct": _safe_money(money_path.get("capital_pct")),
        "capital_limit_usd": _safe_money(money_path.get("deployed_capital_usd")),
        "target_symbols": target_symbols,
        "forward_observations": {
            "current": _safe_int(evidence.get("forward_n_obs")),
            "required": _safe_int(evidence.get("min_forward_obs")),
        },
        "forward_psr": {
            "current": _safe_money(evidence.get("forward_psr")),
            "required": _safe_money(evidence.get("min_forward_psr")),
        },
        "promotion_status": "BLOCKED" if not operational.get("alpha_confirmed") else "ELIGIBLE",
        "blockers_ko": [
            value
            for value in [_safe_string(money_path.get("blocking_gate"))]
            if value is not None
        ],
        "observed_at_utc": _safe_timestamp(parse_timestamp_utc(live_canary_raw)),
    }


def _intraday_strategy(
    budget: dict[str, Any] | None,
    preflight: dict[str, Any] | None,
) -> dict[str, Any] | None:
    summary = _intraday_budget(budget, preflight)
    if summary is None:
        return None
    blockers = preflight.get("blockers") if preflight else []
    safe_blockers = (
        [value for value in blockers if isinstance(value, str)]
        if isinstance(blockers, list)
        else []
    )
    return {
        "strategy_id": "intraday-kis-execution",
        "role": "PREPARATION_ONLY",
        "status": summary["preflight_status"],
        "live_eligible": summary["live_eligible"],
        "orders_enabled": summary["orders_enabled"],
        "orders_submitted": summary["orders_submitted"],
        "capital_limit_usd": summary["capital_limit_usd"],
        "blockers": safe_blockers,
        "confirmed_on": summary["confirmed_on"],
        "observed_at_utc": None,
    }


def _research_strategy(raw: str | None, now: datetime) -> dict[str, Any]:
    check = assess_liveness(
        [_RESEARCH_SPEC],
        {_RESEARCH_SPEC.key: raw},
        now,
    ).checks[0]
    candidate_match = re.search(r"^- 개발 선택 후보:\s*`([^`]+)`", raw or "", re.MULTILINE)
    verdict_match = re.search(r"^- 역사 판정:\s*`([^`]+)`", raw or "", re.MULTILINE)
    return {
        "role": "RESEARCH_ONLY",
        "status": check.status,
        "candidate_id": candidate_match.group(1) if candidate_match else None,
        "historical_verdict": verdict_match.group(1) if verdict_match else None,
        "observed_at_utc": _safe_timestamp(check.timestamp_utc),
        "detail_ko": check.detail,
        "promotion_eligible": False,
    }


def _last_execution(money_path: dict[str, Any] | None) -> dict[str, Any] | None:
    if money_path is None:
        return None
    state = _mapping(money_path.get("live_money_state"))
    last_run = _mapping(state.get("last_run")) if state else None
    if last_run is None:
        return None
    return {
        "timestamp_utc": _safe_timestamp(last_run.get("timestamp_utc")),
        "event": _safe_string(last_run.get("event")),
        "status": (_safe_string(last_run.get("live_step")) or "UNKNOWN").upper(),
        "preflight_ok": _safe_bool(last_run.get("preflight_ok")),
        "preflight_reason": _safe_string(last_run.get("preflight_reason")),
        "accepted_or_filled_count": _safe_int(last_run.get("accepted_or_filled_count")),
        "broker_rejected_count": _safe_int(last_run.get("broker_rejected_count")),
        "next_scheduled_utc": _safe_timestamp(state.get("next_scheduled_live_utc")),
    }


def build_mobile_operator_summaries(
    *,
    sidecar_dir: Path,
    budget_path: Path | None,
    preflight_path: Path | None,
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return sanitized capital and strategy summaries.

    Missing or malformed inputs degrade only their own subsection. The returned
    document remains read-only and never guesses account aggregates.
    """

    money_raw = _read_text(sidecar_dir / "money-path.md")
    live_canary_raw = _read_text(sidecar_dir / "rebalance-live-canary.md")
    live_profit_raw = _read_text(sidecar_dir / "live-profit-evidence.md")
    research_raw = _read_text(sidecar_dir / "autonomous-strategy-factory.md")
    money_path = _parse_money_path(money_raw)
    money_path_performance = (
        _mapping(money_path.get("live_profit_evidence")) if money_path else None
    )
    live_profit = None
    if live_profit_raw is not None:
        try:
            parsed_profit = json.loads(live_profit_raw)
        except json.JSONDecodeError:
            parsed_profit = None
        live_profit = _mapping(parsed_profit)
    budget = _read_json(budget_path)
    preflight = _read_json(preflight_path)

    # New deployments read the event source directly. Older deployments that do
    # not collect it yet retain the money-path embedded snapshot as a compatible
    # fallback. A present-but-broken newest source never falls back silently.
    performance = _performance(
        live_profit if live_profit_raw is not None else money_path_performance
    )
    money_as_of = _safe_timestamp(money_path.get("as_of_utc")) if money_path else None
    capital_summary = {
        "schema_version": SCHEMA_VERSION,
        "as_of_utc": _latest_timestamp(
            money_as_of,
            performance.get("observed_at_utc") if performance else None,
        ),
        "max_age_minutes": MAX_AGE_MINUTES,
        "account": _account_summary(money_path),
        "live_allocation": _live_allocation(money_path),
        "intraday_budget": _intraday_budget(budget, preflight),
        "performance": performance,
        "risk": _risk(money_path),
    }

    active = _active_strategy(money_path, live_canary_raw)
    research = _research_strategy(research_raw, now)
    last_execution = _last_execution(money_path)
    strategy_summary = {
        "schema_version": SCHEMA_VERSION,
        "as_of_utc": _latest_timestamp(
            money_as_of,
            active.get("observed_at_utc") if active else None,
            research.get("observed_at_utc"),
        ),
        "max_age_minutes": MAX_AGE_MINUTES,
        "active": active,
        "intraday": _intraday_strategy(budget, preflight),
        "research": research,
        "last_execution": last_execution,
    }
    return capital_summary, strategy_summary


__all__ = [
    "MAX_AGE_MINUTES",
    "SCHEMA_VERSION",
    "build_mobile_operator_summaries",
    "mobile_summary_sidecar_specs",
]
