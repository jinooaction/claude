"""Reconcile current overseas quantities without claiming whole-account coverage."""

import re
from datetime import UTC, datetime

from auto_invest.broker.account_source_profile import _number

ROOT = "/uapi/overseas-stock/v1/trading/"
CURRENT = ROOT + "inquire-present-balance"
MARGIN = ROOT + "foreign-margin"
US_MARKETS = {"NAS", "NASD", "NYSE", "NYS", "AMEX", "AMS"}


class HoldingsCoverageError(ValueError):
    pass


def _require(condition, reason):
    if not condition:
        raise HoldingsCoverageError(reason)


def _time(value):
    try:
        value = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ValueError
        return value.astimezone(UTC)
    except (ValueError, TypeError, OverflowError):
        raise HoldingsCoverageError("HOLDINGS_TIME_INVALID") from None


def _positions(data):
    rows = data.get("output1")
    _require(isinstance(rows, list) and len(rows) <= 2000, "HOLDINGS_ROWS_INVALID")
    positions, stable = {}, {}
    for row in rows:
        _require(isinstance(row, dict), "HOLDINGS_ROW_INVALID")
        symbol, currency, market = (row.get(key) for key in
                                    ("pdno", "buy_crcy_cd", "ovrs_excg_cd"))
        _require(isinstance(symbol, str) and re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,31}",
                                                        symbol.strip()), "HOLDINGS_SYMBOL_INVALID")
        _require(isinstance(currency, str) and re.fullmatch(r"[A-Z]{3}", currency.strip())
                 and isinstance(market, str) and re.fullmatch(r"[A-Z0-9]{1,8}", market.strip()),
                 "HOLDINGS_CURRENCY_OR_MARKET_INVALID")
        symbol, currency, market = symbol.strip(), currency.strip(), market.strip()
        _require(symbol not in positions, "HOLDINGS_DUPLICATE_SYMBOL")
        quantity, sellable, loan = (_number(row.get(key)) for key in (
            "ccld_qty_smtl1", "ord_psbl_qty1", "loan_rmnd"))
        value = _number(row.get("frcr_evlu_amt2"))
        _require(all(item is not None and item >= 0 for item in (quantity, sellable, loan))
                 and sellable <= quantity, "HOLDINGS_AMOUNT_INVALID")
        _require("frcr_evlu_amt2" not in row or (value is not None and value >= 0),
                 "HOLDINGS_VALUE_INVALID")
        stable[symbol] = (currency, market, quantity, sellable, loan)
        positions[symbol] = dict(currency=currency, market=market, quantity=str(quantity),
            sellable_quantity=str(sellable), loan=str(loan),
            reported_value=str(value) if value is not None else None,
            price_source_at=None)
    return positions, stable


def normalize_current_holdings(records, *, observed_at):
    result = dict(status="UNAVAILABLE", positions=None, full_account_verified=False,
                  scope="CURRENT_ALL_COUNTRY_OVERSEAS_HOLDINGS", live_eligible=False)
    try:
        _require(isinstance(records, list) and len(records) == 3, "HOLDINGS_BATCH_INVALID")
        clock, previous = _time(observed_at), None
        for row, endpoint in zip(records, (CURRENT, MARGIN, CURRENT), strict=True):
            _require(isinstance(row, dict) and row.get("endpoint") == endpoint,
                     "HOLDINGS_REQUEST_SCOPE")
            continuation, data = row.get("continuation"), row.get("data")
            _require(isinstance(continuation, str) and continuation in {"", "D", "E"},
                     "HOLDINGS_PAGE_INCOMPLETE")
            _require(row.get("http_status") == 200 and isinstance(data, dict)
                     and data.get("rt_cd") == "0", "HOLDINGS_RESPONSE_INVALID")
            start, end = _time(row.get("started_at")), _time(row.get("received_at"))
            _require(start <= end <= clock and (previous is None or previous <= start)
                     and 0 <= (clock - start).total_seconds() <= 30, "HOLDINGS_INTERVAL_INVALID")
            previous = end
        _, before = _positions(records[0]["data"])
        positions, after = _positions(records[-1]["data"])
        _require(before == after, "HOLDINGS_CHANGED")
        result.update(status="OBSERVED", positions=positions,
            observation_started_at=_time(records[0]["started_at"]).isoformat(),
            observation_completed_at=_time(records[-1]["received_at"]).isoformat())
    except HoldingsCoverageError as error:
        result["reason"] = str(error)
    return result


def compare_current_holdings(current, ordinary, *, observed_at):
    result = dict(status="UNAVAILABLE", equity_holdings_matched=False,
                  scope="CURRENT_OVERSEAS_EQUITIES_ONLY", full_account_verified=False,
                  live_eligible=False)
    try:
        _require(isinstance(current, dict) and current.get("status") == "OBSERVED"
                 and current.get("scope") == "CURRENT_ALL_COUNTRY_OVERSEAS_HOLDINGS"
                 and isinstance(current.get("positions"), dict)
                 and len(current["positions"]) <= 2000, "HOLDINGS_CURRENT_UNAVAILABLE")
        _require(isinstance(ordinary, dict) and ordinary.get("pagination_complete") is True,
                 "HOLDINGS_ORDINARY_UNAVAILABLE")
        _require(ordinary.get("currency") == "USD"
                 and ordinary.get("account_scope") == "US_ORDINARY_OVERSEAS_STOCK",
                 "HOLDINGS_ORDINARY_SCOPE_INVALID")
        start, end = (_time(ordinary.get(key)) for key in
                      ("observation_started_at", "observation_completed_at"))
        current_start, current_end = (_time(current.get(key)) for key in
                                      ("observation_started_at", "observation_completed_at"))
        clock = _time(observed_at)
        sequential = start <= end <= current_start <= current_end <= clock
        enclosed = current_start <= start <= end <= current_end <= clock
        _require((sequential or enclosed)
                 and 0 <= (clock - min(start, current_start)).total_seconds() <= 30,
                 "HOLDINGS_INTERVAL_INVALID")
        positions, reported = ordinary.get("positions"), ordinary.get("unverified_assets")
        _require(isinstance(positions, dict) and isinstance(reported, dict)
                 and len(positions) + len(reported) <= 2000
                 and not positions.keys() & reported.keys(), "HOLDINGS_ORDINARY_INVALID")
        expected = {}
        for symbol, row in positions.items():
            _require(isinstance(row, dict) and type(row.get("quantity")) is int
                     and 0 <= row["quantity"] <= 10**18, "HOLDINGS_ORDINARY_INVALID")
            if row["quantity"]:
                expected[symbol] = (row["quantity"], False)
        for symbol, row in reported.items():
            _require(isinstance(row, dict) and row.get("reported_market_code") == "OTCB",
                     "HOLDINGS_ORDINARY_INVALID")
            quantity = _number(row.get("reported_quantity"))
            _require(quantity is not None and quantity >= 0, "HOLDINGS_ORDINARY_INVALID")
            if quantity:
                expected[symbol] = (quantity, True)
        observed = {}
        for symbol, row in current["positions"].items():
            _require(isinstance(row, dict), "HOLDINGS_CURRENT_INVALID")
            quantity, loan = _number(row.get("quantity")), _number(row.get("loan"))
            _require(quantity is not None and quantity >= 0 and loan == 0,
                     "HOLDINGS_QUANTITY_OR_LOAN_INVALID")
            if not quantity:
                continue
            market = row.get("market")
            _require(row.get("currency") == "USD" and isinstance(market, str)
                     and market in US_MARKETS | {"OTCB"}, "HOLDINGS_OUTSIDE_US_SCOPE")
            observed[symbol] = (quantity, market == "OTCB")
        _require(observed == expected, "HOLDINGS_SCOPE_OR_QUANTITY_DIFFERS")
        result.update(status="MATCH", equity_holdings_matched=True,
                      positive_holding_count=len(observed))
    except HoldingsCoverageError as error:
        result["reason"] = str(error)
    return result
