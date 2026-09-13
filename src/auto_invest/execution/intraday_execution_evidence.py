"""Authenticated order/report/ledger comparison, separate from full model parity.

Supported report scope: one strategy, USD, closed orders and unique broker order
IDs. Dated orders are matched by trade day/symbol/side; grouped fees are never
allocated among orders. Missing dates support only the older single-order diagnostic.
"""

import asyncio
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_invest.broker.intraday_transactions import audit_settlements, observe_transactions
from auto_invest.broker.overseas import get_order_executions_resolving_market
from auto_invest.execution.intraday_cost_reconciliation import reconcile_cost_inputs
from auto_invest.execution.intraday_observation import KISExecutionObserver
from auto_invest.execution.intraday_observation_models import (
    assess_intervals,
    assess_model_quantities,
    assess_next_bar_costs,
    assess_next_bar_timing,
)
from auto_invest.market_data.intraday import DataError


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return "sha256:" + hashlib.sha256(_encode(value).encode()).hexdigest()


def _ledger(connection):
    result = {table: [dict(row) for row in connection.execute(
        f"SELECT * FROM {table} ORDER BY seq")]
            for table in ("orders", "fills", "order_state_history")}
    result["fill_audits"] = [dict(row) for row in connection.execute(
        "SELECT * FROM audit_log WHERE event_type='FILL' ORDER BY seq"
    )]
    result["fill_notionals"] = [dict(row) for row in connection.execute(
        "SELECT * FROM fill_notionals ORDER BY kis_fill_id"
    )] if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fill_notionals'"
    ).fetchone() else []
    result["execution_claims"] = [dict(row) for row in connection.execute(
        "SELECT * FROM intraday_execution_claims ORDER BY id"
    )] if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='intraday_execution_claims'"
    ).fetchone() else []
    return result


def _signal_context(ledger, order, prefix, fingerprint):
    """Bind the persisted intent to this exact broker order; old rows stay unknown."""
    try:
        claims = [row for row in ledger.get("execution_claims", [])
                  if prefix + row["id"] == order["rule_id"]
                  and row["fingerprint"] == fingerprint]
        if len(claims) != 1:
            return {}
        value = json.loads(claims[0]["payload"])
        if (value["symbol"] != order["symbol"] or value["side"] != order["side"]
                or type(value["qty"]) is not int or value["qty"] != order["qty"]
                or Decimal(value["limit"]) != Decimal(order["limit_price_usd"])):
            return {}
        return {key: value.get(key) for key in ("signal_bar_end", "decision_kind")}
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return {}


def _recorded_upper_bound(ledger, order, lower, current):
    """Narrow only when every recorded fill has matching post-response evidence.

    Old logical observation times are deliberately ignored. Missing or invalid
    evidence falls back to the fresh authenticated GET's wider interval.
    """
    try:
        ceiling = datetime.fromisoformat(current.replace("Z", "+00:00"))
        fills = [row for row in ledger["fills"]
                 if row["order_correlation_id"] == order["correlation_id"]]
        events = [json.loads(row["payload_json"]) for row in ledger.get("fill_audits", [])
                  if row["correlation_id"] == order["correlation_id"]
                  and row["symbol"] == order["symbol"] and row["rule_id"] == order["rule_id"]]
        if not fills or len(fills) != len(events):
            return current
        by_id = {event["kis_fill_id"]: event for event in events}
        if len(by_id) != len(events):
            return current
        times = []
        for fill in fills:
            event = by_id[fill["kis_fill_id"]]
            if (type(event["qty"]) is not int or event["qty"] != fill["qty"]
                    or Decimal(event["price_usd"]) != Decimal(fill["price_usd"])):
                return current
            stamp = datetime.fromisoformat(
                event["broker_response_received_at_utc"].replace("Z", "+00:00")
            )
            if stamp.utcoffset() is None or not lower <= stamp <= ceiling:
                return current
            times.append(stamp)
        return max(times).isoformat()
    except (KeyError, TypeError, ValueError, AttributeError, ArithmeticError):
        return current


@dataclass(frozen=True)
class ExecutionCostAssessment:
    account_digest: str
    execution_identity: str
    runtime_digest: str
    window: tuple[str, str]
    digest: str
    checks_json: str
    issues: tuple[str, ...]
    missing_model_conditions: tuple[str, ...]
    intervals_json: str = "[]"
    orders_json: str = "[]"
    fee_groups_json: str | None = None

    def assess_interval_volume(self, bars, *, participation, observed_at, cost_model=None):
        if self.issues:
            raise DataError("INTERVAL_COST_BINDING_NOT_ACCEPTED")
        result = assess_intervals(json.loads(self.intervals_json), bars,
                                  participation=participation, observed_at=observed_at)
        result.update(assess_next_bar_timing(json.loads(self.intervals_json)))
        fee_groups = json.loads(self.fee_groups_json) if self.fee_groups_json is not None else None
        result.update(assess_next_bar_costs(
            json.loads(self.intervals_json), bars, cost_model, fee_groups=fee_groups,
        ))
        result.update(assess_model_quantities(json.loads(self.orders_json), bars, participation))
        return dict(result, account_digest=self.account_digest,
                    execution_identity=self.execution_identity, cost_digest=self.digest,
                    interval_digest=_digest(dict(cost_digest=self.digest,
                        intervals=json.loads(self.intervals_json),
                        orders=json.loads(self.orders_json), bars=bars,
                        participation=participation, observed_at=observed_at,
                        cost_model=cost_model, fee_groups=fee_groups)),
                    market_source_authentication_verified=False)

    def public(self):
        return dict(scope="CLOSED_SINGLE_STRATEGY_ORDER_REPORT_COSTS",
                    digest=self.digest, checks=json.loads(self.checks_json),
                    issues=list(self.issues),
                    missing_model_conditions=list(self.missing_model_conditions),
                    execution_parity_verified=not self.issues and not self.missing_model_conditions)


def assess_sources(*, database, account, selection, runtime_digest, window, executions,
                   transactions, before, after, commission_bps, response_received=None):
    """Recompute evidence; report flags from earlier processing are ignored."""
    comparison = reconcile_cost_inputs(database, executions, transactions["rows"])
    rows = transactions["rows"]
    settlement = audit_settlements(rows)
    issues = set(comparison["issues"])
    if before != after:
        issues.add("EXECUTION_LEDGER_CHANGED_DURING_READ")
    local = []
    for row in before["orders"]:
        if not row["kis_order_id"]:
            continue
        try:
            stamp = datetime.fromisoformat(row["submitted_at_utc"].replace("Z", "+00:00"))
            if stamp.utcoffset() is None:
                raise ValueError
            day = stamp.astimezone(UTC).strftime("%Y%m%d")
        except (TypeError, ValueError, AttributeError):
            issues.add("LOCAL_ORDER_DATE_UNAVAILABLE")
            continue
        if window[0] <= day <= window[1]:
            local.append(row)
    ids = [row["kis_order_id"] for row in local]
    reported = [value.kis_order_id for value in executions]
    if not ids or len(ids) != len(set(ids)) or set(ids) != set(reported):
        issues.add("COMPLETE_ORDER_SET_NOT_MATCHED")
    prefix = "intraday:" + selection.execution_identity + ":"
    if any(not row["rule_id"].startswith(prefix) for row in local):
        issues.add("OTHER_STRATEGY_IN_REPORT_WINDOW")
    if any(row["state"] not in {"FILLED", "CANCELLED", "REJECTED", "EXPIRED"} for row in local):
        issues.add("LOCAL_ORDER_NOT_CLOSED")
    grouped = {}
    price_ok = True
    local_by_id = {row["kis_order_id"]: row for row in local}
    for value in executions:
        order = local_by_id.get(value.kis_order_id)
        if (value.reported_order_quantity is not None and order is not None
                and value.reported_order_quantity != order["qty"]):
            issues.add("BROKER_LEDGER_ORDER_QUANTITY_MISMATCH")
        if value.unfilled_qty != 0 and not value.terminal:
            issues.add("BROKER_ORDER_NOT_CLOSED")
        if (value.reported_order_quantity is not None
                and value.filled_qty < value.reported_order_quantity and not value.terminal):
            issues.add("BROKER_ORDER_NOT_CLOSED")
        if not value.filled_qty:
            continue
        key = (value.symbol, value.side.value if value.side else None)
        grouped.setdefault(key, []).append(value)
        try:
            limit = Decimal(order["limit_price_usd"])
            price_ok &= bool(
                value.order_type is not None and value.order_type.value == "LIMIT"
                and value.order_price_usd == limit and limit.is_finite() and limit > 0
                and (value.avg_fill_price_usd <= limit if key[1] == "BUY"
                     else value.avg_fill_price_usd >= limit)
            )
        except (KeyError, TypeError, ArithmeticError):
            price_ok = False
    if not price_ok:
        issues.add("ORDER_LIMIT_OR_FILL_PRICE_MISMATCH")
    fee_ok = True
    date_ok = True
    reported_fees = {}
    fee_groups = []
    with localcontext() as context:
        context.prec = 80
        rate = Decimal(str(commission_bps)) / 10000
        if not rate.is_finite() or rate < 0:
            raise DataError("EXECUTION_COST_MODEL_INVALID")
        for key, values in grouped.items():
            matching = [row for row in rows if (
                row["pdno"], "BUY" if row["sll_buy_dvsn_cd"] == "02" else "SELL"
            ) == key]
            if not matching:
                fee_ok = False
                date_ok = False
                continue
            dated = {}
            if any(value.reported_order_date is None for value in values):
                date_ok = False
                if len(values) != 1:
                    fee_ok = False
                    issues.add("MULTIPLE_ORDERS_WITHOUT_REPORTED_DATES")
                    continue
                dated[None] = values
            else:
                for value in values:
                    dated.setdefault(value.reported_order_date.strftime("%Y%m%d"), []).append(value)
                if {row["trad_dt"] for row in matching} != dated.keys():
                    date_ok = False
                    issues.add("ORDER_TRADE_SETTLEMENT_DATES_NOT_MATCHED")
            if any(
                not window[0] <= row["trad_dt"] <= row["sttl_dt"] <= window[1]
                for row in matching
            ):
                date_ok = False
                issues.add("ORDER_TRADE_SETTLEMENT_DATES_NOT_MATCHED")
            for day, orders in dated.items():
                selected_rows = [row for row in matching if day is None or row["trad_dt"] == day]
                fees = sum((Decimal(row["dmst_frcr_fee1"]) + Decimal(row["frcr_fee1"])
                            for row in selected_rows), Decimal(0))
                gross = sum((Decimal(row["tr_frcr_amt2"]) for row in selected_rows), Decimal(0))
                quantity = sum((Decimal(row["ccld_qty"]) for row in selected_rows), Decimal(0))
                if (not selected_rows or quantity != sum(value.filled_qty for value in orders)
                        or gross != sum((value.filled_qty * value.avg_fill_price_usd
                                         for value in orders), Decimal(0))):
                    issues.add("DATED_TRANSACTION_EXECUTION_TOTAL_MISMATCH")
                if len(orders) == 1:
                    reported_fees[orders[0].kis_order_id] = str(fees)
                fee_groups.append(dict(trade_date=day, symbol=key[0], side=key[1],
                                       order_ids=sorted(value.kis_order_id for value in orders),
                                       reported_fees=str(fees)))
                fee_ok &= fees <= gross * rate
    if not fee_ok:
        issues.add("REPORTED_COST_EXCEEDS_MODEL_OR_AMBIGUOUS")
    if (transactions["registration_start_date"], transactions["registration_end_date"]) != window:
        issues.add("TRANSACTION_QUERY_WINDOW_CHANGED")
    checks = dict(order_and_amounts_match=comparison["report_totals_match"],
                  reported_settlement_arithmetic=settlement["arithmetic_verified"],
                  reported_fee_bound=fee_ok, limit_price_conformity=price_ok,
                  reported_order_trade_dates_match=bool(grouped) and date_ok,
                  order_report_scope_verified=not issues)
    # BrokerExecution carries order time, not actual execution time. Neither an
    # arithmetic match nor an operator digest proves model fill timing/volume.
    missing = ("SOURCE_EXECUTION_TIMING_NOT_PROVIDED", "MODEL_FILL_VOLUME_REPLAY_NOT_PROVIDED",
               "ORDER_TRADE_DATE_LINK_NOT_PROVIDED")
    intervals = []
    for execution in executions:
        if not execution.filled_qty:
            continue
        order = local_by_id.get(execution.kis_order_id)
        starts = [row["ts_utc"] for row in before.get("order_state_history", [])
                  if order is not None and row["order_correlation_id"] == order["correlation_id"]
                  and row["to_state"] == "SUBMITTING"]
        if not starts or response_received is None:
            intervals = []
            break
        lower = min(datetime.fromisoformat(stamp.replace("Z", "+00:00")) for stamp in starts)
        if lower.utcoffset() is None:
            intervals = []
            break
        intervals.append(dict(order_id=execution.kis_order_id, symbol=execution.symbol,
                              quantity=execution.filled_qty,
                              side=execution.side.value if execution.side else None,
                              average_fill_price=str(execution.avg_fill_price_usd),
                              reported_fees=reported_fees.get(execution.kis_order_id),
                              before_submission=lower.isoformat(),
                              response_received=_recorded_upper_bound(
                                  before, order, lower, response_received),
                              **_signal_context(
                                  before, order, prefix, selection.execution_identity)))
    identity = dict(account_digest="sha256:" + hashlib.sha256(account.encode()).hexdigest(),
                    execution_identity=selection.execution_identity, runtime_digest=runtime_digest,
                    research_digest=selection.research_digest,
                    dataset_fingerprint=selection.dataset_fingerprint, window=window)
    correlations = {order["correlation_id"] for order in local}
    scoped_ledger = dict(orders=local)
    rule_ids = {order["rule_id"] for order in local}
    scoped_ledger["execution_claims"] = [row for row in before.get("execution_claims", [])
        if prefix + row["id"] in rule_ids]
    for table in ("fills", "order_state_history", "fill_audits"):
        key = "correlation_id" if table == "fill_audits" else "order_correlation_id"
        scoped_ledger[table] = [row for row in before.get(table, [])
                                if row[key] in correlations]
    fill_ids = {row["kis_fill_id"] for row in scoped_ledger["fills"]}
    scoped_ledger["fill_notionals"] = [row for row in before.get("fill_notionals", [])
                                     if row["kis_fill_id"] in fill_ids]
    digest = _digest(dict(identity=identity, checks=checks, issues=sorted(issues), missing=missing,
                          executions=[v.model_dump(mode="json") for v in executions],
                          transactions=rows, ledger=scoped_ledger,
                          commission_bps=str(commission_bps)))
    model_orders = [dict(order_id=value.kis_order_id, symbol=value.symbol,
                        ordered_quantity=value.reported_order_quantity,
                        filled_quantity=value.filled_qty,
                        reported_order_date=(value.reported_order_date.isoformat()
                                             if value.reported_order_date is not None else None),
                        **_signal_context(before, local_by_id.get(value.kis_order_id, {}),
                                          prefix, selection.execution_identity))
                    for value in executions]
    return ExecutionCostAssessment(identity["account_digest"], selection.execution_identity,
                                   runtime_digest, window, digest, _encode(checks),
                                   tuple(sorted(issues)), missing, _encode(intervals),
                                   _encode(model_orders), _encode(fee_groups))


class ExecutionCostSource:
    """Use the router's authenticated GET client and a read-only ledger snapshot."""

    def __init__(self, authority, *, token_cache, runtime_digest):
        self.observer = KISExecutionObserver(authority, lambda: {}, token_cache=token_cache)
        self.authority = authority
        self.runtime_digest = runtime_digest
        self.last_assessment = None

    async def assess(self, selection, session_dates, commission_bps):
        try:
            dates = sorted({datetime.strptime(day, "%Y-%m-%d").strftime("%Y%m%d")
                            for day in session_dates})
            if not dates:
                raise ValueError
            window = (dates[0], dates[-1])
            if self.authority.conn.in_transaction:
                raise DataError("EXECUTION_LEDGER_TRANSACTION_ACTIVE")
            with TemporaryDirectory(prefix="intraday-execution-evidence-") as directory:
                path = Path(directory) / "ledger.db"
                copy = sqlite3.connect(path)
                try:
                    self.authority.conn.backup(copy)
                    copy.row_factory = sqlite3.Row
                    before = _ledger(copy)
                finally:
                    copy.close()
                async with asyncio.timeout(60):
                    await self.observer.refresh_credentials()
                    arguments = dict(account=self.observer.account,
                                     access_token=self.authority.access_token,
                                     app_key=self.authority.app_key,
                                     app_secret=self.authority.app_secret)
                    executions = await get_order_executions_resolving_market(
                        self.observer.broker, **arguments, order_date_yyyymmdd=window[0],
                        end_date_yyyymmdd=window[1], strict_contract=True,
                    )
                    response_received = datetime.now(UTC).isoformat()
                    transactions = await observe_transactions(
                        self.observer.broker, **arguments, start_date=window[0], end_date=window[1],
                    )
                    repeat = await get_order_executions_resolving_market(
                        self.observer.broker, **arguments, order_date_yyyymmdd=window[0],
                        end_date_yyyymmdd=window[1], strict_contract=True,
                    )
                self.observer._check_connection()
                if repeat != executions:
                    raise DataError("EXECUTION_REPORT_CHANGED_DURING_READ")
                after = _ledger(self.authority.conn)
                self.last_assessment = assess_sources(
                    database=path, account=self.observer.account, selection=selection,
                    runtime_digest=self.runtime_digest, window=window, executions=executions,
                    transactions=transactions, before=before, after=after,
                    commission_bps=commission_bps,
                    response_received=response_received,
                )
                return self.last_assessment
        except DataError:
            raise
        except Exception:
            raise DataError("EXECUTION_COST_SOURCE_UNAVAILABLE") from None
