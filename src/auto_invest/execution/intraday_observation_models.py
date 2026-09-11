"""Scoped cash arithmetic and worst-case fill-interval tests, not authorizations.

An interval starts before submission and ends after a positive broker response.
It never starts at an acknowledgement or a possibly stale zero-fill response.
Market bars must cover every possible instant, including an endpoint on a new
bar boundary. All executions of a symbol share that bar's volume budget.
"""

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from zoneinfo import ZoneInfo


class ObservationModelError(ValueError):
    pass


def assess_next_bar_timing(intervals):
    """Prove containment in the original signal's next bar, not an exact fill time."""
    issues = set()
    if not isinstance(intervals, list) or not 0 < len(intervals) <= 10000:
        return dict(next_bar_timing_verified=False, timing_issues=["SIGNAL_INTERVALS_UNAVAILABLE"])
    for interval in intervals:
        try:
            if interval.get("decision_kind") not in {"SIGNAL", "STRATEGY_EXIT"}:
                issues.add("SIGNAL_CONTEXT_UNAVAILABLE")
                continue
            signal = _time(interval.get("signal_bar_end"))
            lower = _time(interval["before_submission"])
            upper = _time(interval["response_received"])
            if signal.second or signal.microsecond or signal.minute % 5:
                issues.add("SIGNAL_BAR_ALIGNMENT_INVALID")
            elif not signal <= lower <= upper < signal + timedelta(minutes=5):
                issues.add("EXECUTION_INTERVAL_OUTSIDE_NEXT_BAR")
        except (AttributeError, TypeError, KeyError, OverflowError, ObservationModelError):
            issues.add("SIGNAL_CONTEXT_INVALID")
    return dict(next_bar_timing_verified=not issues, timing_issues=sorted(issues))


def assess_next_bar_costs(intervals, bars, cost_model, *, fee_groups=None):
    """Compare reported execution costs to the research reference, not fill gross.

    This is a cost bound for matched executions, not complete strategy parity.
    Source authentication and report completeness belong to the caller.
    """
    issues = set()
    price_ok = fee_ok = True
    try:
        if not assess_next_bar_timing(intervals)["next_bar_timing_verified"]:
            raise ObservationModelError("NEXT_BAR_TIMING_UNVERIFIED")
        if not isinstance(bars, list) or len(bars) > 160000:
            raise ObservationModelError("MODEL_INPUT_SIZE_INVALID")
        rates = [_amount(str(cost_model[key])) for key in (
            "spread_bps_per_side", "slippage_bps_per_side", "commission_bps_per_side",
        )]
        if any(not 0 <= rate <= 10000 for rate in rates):
            raise ObservationModelError("MODEL_COST_RATE_INVALID")
        indexed = {}
        for bar in bars:
            key = (bar["symbol"], _time(bar["timestamp_utc"]))
            if key in indexed:
                raise ObservationModelError("MODEL_BAR_INVALID")
            indexed[key] = bar
        with localcontext() as context:
            context.prec = 80
            adverse, commission = (rates[0] + rates[1]) / 10000, rates[2] / 10000
            if adverse >= 1:
                raise ObservationModelError("MODEL_COST_RATE_INVALID")
            reference_amounts = {}
            for entry in intervals:
                bar = indexed.get((entry["symbol"], _time(entry["signal_bar_end"])))
                if bar is None:
                    raise ObservationModelError("NEXT_BAR_REFERENCE_UNAVAILABLE")
                reference = _amount(str(bar["open"]))
                price = _amount(entry["average_fill_price"])
                qty, side = entry["quantity"], entry["side"]
                if (reference <= 0 or price <= 0 or type(qty) is not int
                        or not 0 < qty <= 10**12 or side not in {"BUY", "SELL"}):
                    raise ObservationModelError("MODEL_EXECUTION_COST_INVALID")
                if not (price <= reference * (1 + adverse) if side == "BUY"
                        else price >= reference * (1 - adverse)):
                    price_ok = False
                    issues.add("NEXT_BAR_PRICE_BOUND_EXCEEDED")
                identity = entry["order_id"]
                if not isinstance(identity, str) or not identity or identity in reference_amounts:
                    raise ObservationModelError("MODEL_ORDER_INVALID")
                reference_amounts[identity] = reference * qty
                if fee_groups is None:
                    fees = _amount(entry["reported_fees"])
                    if fees < 0:
                        raise ObservationModelError("MODEL_EXECUTION_COST_INVALID")
                    if fees > reference * qty * commission:
                        fee_ok = False
                        issues.add("NEXT_BAR_FEE_BOUND_EXCEEDED")
            if fee_groups is not None:
                if not isinstance(fee_groups, list) or not 0 < len(fee_groups) <= 10000:
                    raise ObservationModelError("MODEL_FEE_GROUP_INVALID")
                covered = set()
                for group in fee_groups:
                    identities = group["order_ids"]
                    if (not isinstance(identities, list) or not identities
                            or any(not isinstance(value, str) for value in identities)
                            or len(identities) != len(set(identities))
                            or covered.intersection(identities)):
                        raise ObservationModelError("MODEL_FEE_GROUP_INVALID")
                    fees = _amount(group["reported_fees"])
                    if fees < 0:
                        raise ObservationModelError("MODEL_EXECUTION_COST_INVALID")
                    reference_total = sum((reference_amounts[value] for value in identities),
                                          Decimal(0))
                    covered.update(identities)
                    if fees > reference_total * commission:
                        fee_ok = False
                        issues.add("NEXT_BAR_FEE_BOUND_EXCEEDED")
                if covered != reference_amounts.keys():
                    raise ObservationModelError("MODEL_FEE_GROUP_INVALID")
    except (ObservationModelError, KeyError, TypeError, ValueError, ArithmeticError):
        price_ok = fee_ok = False
        issues.add("NEXT_BAR_COST_INPUT_UNVERIFIED")
    return dict(next_bar_price_bound_verified=price_ok, next_bar_fee_bound_verified=fee_ok,
                cost_issues=sorted(issues))


def assess_model_quantities(orders, bars, participation):
    """Compare all reported orders, including zero fills, with the model's integer cap."""
    issues = set()
    try:
        if (not isinstance(orders, list) or not 0 < len(orders) <= 10000
                or not isinstance(bars, list) or len(bars) > 160000):
            raise ObservationModelError("MODEL_INPUT_SIZE_INVALID")
        rate = _amount(participation)
        if not 0 < rate <= 1:
            raise ObservationModelError("MODEL_PARTICIPATION_INVALID")
        indexed, seen = {}, set()
        for bar in bars:
            key = (bar["symbol"], _time(bar["timestamp_utc"]))
            if key in indexed or type(bar["volume"]) is not int or not 0 <= bar["volume"] <= 10**18:
                raise ObservationModelError("MODEL_BAR_INVALID")
            indexed[key] = bar["volume"]
        with localcontext() as context:
            context.prec = 80
            for order in orders:
                identity = order["order_id"]
                requested, filled = order["ordered_quantity"], order["filled_quantity"]
                stamp = _time(order["signal_bar_end"])
                if (not isinstance(identity, str) or not identity or identity in seen
                        or order["decision_kind"] not in {"SIGNAL", "STRATEGY_EXIT"}
                        or order.get("reported_order_date") != stamp.astimezone(
                            ZoneInfo("America/New_York")).date().isoformat()
                        or stamp.second or stamp.microsecond or stamp.minute % 5
                        or type(requested) is not int or not 0 < requested <= 10**12
                        or type(filled) is not int or not 0 <= filled <= requested):
                    raise ObservationModelError("MODEL_ORDER_INVALID")
                seen.add(identity)
                volume = indexed[(order["symbol"], stamp)]
                expected = min(requested, int(Decimal(volume) * rate))
                if filled != expected:
                    issues.add("MODEL_FILL_QUANTITY_MISMATCH")
    except (ObservationModelError, KeyError, TypeError, ValueError, ArithmeticError):
        issues.add("MODEL_ORDER_QUANTITIES_UNVERIFIED")
    return dict(model_fill_quantity_verified=not issues, quantity_issues=sorted(issues))


def _amount(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]{1,18}(\.[0-9]{1,12})?", value):
        raise ObservationModelError("MODEL_AMOUNT_INVALID")
    return Decimal(value)


def _time(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.utcoffset() is None:
            raise ValueError
        return stamp.astimezone(UTC)
    except (ValueError, TypeError, AttributeError):
        raise ObservationModelError("MODEL_TIME_INVALID") from None


def settled_usd_cash(rows, *, unclassified_rows=0):
    """Interpret only a single already-USD margin row with no unsettled/debt leg.

    This is that row's reported settled cash, not whole-account NAV, buying
    power or a declaration that omitted currencies/assets/liabilities are zero.
    Nonzero ambiguous components return no cash instead of guessing a formula.
    """
    if not isinstance(rows, list) or len(rows) != 1 or unclassified_rows != 0:
        return dict(status="UNSUPPORTED", reason="CASH_ROW_SCOPE_AMBIGUOUS", cash=None)
    row = rows[0]
    try:
        values = {key: _amount(row[key]) for key in (
            "frcr_dncl_amt1", "ustl_buy_amt", "ustl_sll_amt", "frcr_rcvb_amt", "frcr_mgn_amt",
        )}
    except (KeyError, TypeError, ObservationModelError):
        return dict(status="INVALID", reason="CASH_COMPONENT_INVALID", cash=None)
    if any(value < 0 for value in values.values()):
        return dict(status="INVALID", reason="CASH_COMPONENT_INVALID", cash=None)
    if any(values[key] != 0 for key in values if key != "frcr_dncl_amt1"):
        return dict(status="UNSUPPORTED", reason="UNSETTLED_OR_LIABILITY_PRESENT", cash=None)
    return dict(status="CALCULATED", scope="REPORTED_SETTLED_USD_MARGIN_ROW",
                cash=str(values["frcr_dncl_amt1"]), full_account_verified=False)


def assess_intervals(intervals, bars, *, participation, observed_at):
    """Test a supplied interval envelope against completed five-minute source bars.

    This proves only the stated interval/volume model under supplied provenance.
    It does not prove exact execution times, next-bar research equivalence,
    completeness of source records, or grant live authority.
    """
    try:
        return _assess_intervals(intervals, bars, participation=participation,
                                observed_at=observed_at)
    except ObservationModelError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ObservationModelError("MODEL_INPUT_INVALID") from None


def _assess_intervals(intervals, bars, *, participation, observed_at):
    if (not isinstance(intervals, list) or not 1 <= len(intervals) <= 10000
            or not isinstance(bars, list) or len(bars) > 160000):
        raise ObservationModelError("MODEL_INPUT_SIZE_INVALID")
    rate, clock = _amount(participation), _time(observed_at)
    if not 0 < rate <= 1:
        raise ObservationModelError("MODEL_PARTICIPATION_INVALID")
    by_symbol, seen = {}, set()
    for bar in bars:
        start = _time(bar["timestamp_utc"])
        symbol = bar["symbol"]
        volume = bar["volume"]
        if (not isinstance(symbol, str) or not symbol
                or type(volume) is not int or not 0 <= volume <= 10**18
                or start.second or start.microsecond or start.minute % 5
                or start + timedelta(minutes=5) > clock or (symbol, start) in seen):
            raise ObservationModelError("MODEL_BAR_INVALID")
        seen.add((symbol, start))
        by_symbol.setdefault(symbol, {})[start] = volume
    exposure, identifiers, issues = {}, set(), set()
    for entry in intervals:
        identity, symbol, qty = entry["order_id"], entry["symbol"], entry["quantity"]
        start, end = _time(entry["before_submission"]), _time(entry["response_received"])
        if (not isinstance(identity, str) or not identity or identity in identifiers
                or not isinstance(symbol, str) or not symbol
                or type(qty) is not int or not 0 < qty <= 10**12
                or not start <= end <= clock or end - start > timedelta(days=7)):
            raise ObservationModelError("MODEL_INTERVAL_INVALID")
        identifiers.add(identity)
        # The upper endpoint is inclusive: receipt on a bar boundary cannot
        # exclude a fill at that instant. Never allocate unknown fills to a
        # convenient high-volume bar or distribute them pro rata.
        current = start.replace(minute=start.minute // 5 * 5, second=0, microsecond=0)
        while current <= end:
            key = (symbol, current)
            exposure[key] = exposure.get(key, 0) + qty
            if len(exposure) > 160000:
                raise ObservationModelError("MODEL_INPUT_SIZE_INVALID")
            if current not in by_symbol.get(symbol, {}):
                issues.add("INTERVAL_BAR_COVERAGE_MISSING")
            current += timedelta(minutes=5)
    with localcontext() as context:
        context.prec = 80
        for (symbol, start), quantity in exposure.items():
            volume = by_symbol.get(symbol, {}).get(start)
            if volume is not None and quantity > Decimal(volume) * rate:
                issues.add("WORST_CASE_VOLUME_LIMIT_EXCEEDED")
    return dict(model="ALL_POSSIBLE_FIVE_MINUTE_BARS_V1", interval_count=len(intervals),
                possible_bar_count=len(exposure), issues=sorted(issues),
                interval_volume_verified=not issues, exact_execution_time_verified=False,
                full_execution_parity_verified=False)
