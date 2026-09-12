"""Describe fixed account component states without exposing amounts or identities."""

from auto_invest.broker.account_asset_evidence import ASSETS_URL, TABLE_FIELDS
from auto_invest.broker.account_cash_comparison import BASES, ROOT, _rows
from auto_invest.broker.account_source_profile import _number

BALANCE_URL = ROOT + "inquire-balance"
HOLDING_FIELDS = ("ovrs_cblc_qty", "ord_psbl_qty", "now_pric2", "ovrs_stck_evlu_amt")
SUMMARY_FIELDS = (
    "dncl_amt", "cma_evlu_amt", "tot_dncl_amt", "frcr_evlu_tota", "tot_asst_amt",
    "ustl_sll_amt_smtl", "ustl_buy_amt_smtl", "tot_loan_amt",
)
STATES = ("ZERO", "POSITIVE", "NEGATIVE", "UNAVAILABLE")


def _state(value):
    number = _number(value)
    return ("UNAVAILABLE" if number is None else "ZERO" if number == 0 else
            "POSITIVE" if number > 0 else "NEGATIVE")


def _fields(row, fields):
    return {field: _state(row.get(field)) for field in fields}


def _holdings(rows):
    groups = {name: [] for name in ("OTCB", "LISTED_US", "OTHER_OR_UNKNOWN")}
    for row in rows:
        exchange = row.get("ovrs_excg_cd")
        exchange = exchange.strip() if isinstance(exchange, str) else ""
        group = ("OTCB" if exchange == "OTCB" else "LISTED_US"
                 if exchange in {"NASD", "NAS", "NYSE", "AMEX"} else "OTHER_OR_UNKNOWN")
        groups[group].append(row)
    return {name: dict(row_count=len(items), fields={
        field: {state: sum(_state(row.get(field)) == state for row in items)
                for state in STATES} for field in HOLDING_FIELDS
    }) for name, items in groups.items()}


def profile_account_components(responses):
    """Row-state evidence only: no inferred scope, price freshness or NAV authority."""
    result = dict(schema_version=1, responses=[], excluded_response_count=0,
                  full_account_scope_verified=False, execution_nav_verified=False,
                  live_eligible=False)
    if not isinstance(responses, list) or len(responses) > 200:
        return result
    for response in responses:
        if not isinstance(response, dict):
            continue
        endpoint, data = response.get("endpoint"), response.get("data")
        if not isinstance(endpoint, str) or endpoint not in {*BASES, ASSETS_URL, BALANCE_URL}:
            continue
        good = (response.get("http_status") == 200 and isinstance(data, dict)
                and data.get("rt_cd") == "0")
        field = "output3" if endpoint in BASES else "output1"
        rows = _rows(data.get(field)) if good else None
        if rows is None or (endpoint == ASSETS_URL and len(rows) not in {17, 20}):
            result["excluded_response_count"] += 1
            continue
        if endpoint == ASSETS_URL:
            profile = dict(kind="SETTLEMENT_ASSET_TABLE", row_count=len(rows), rows=[
                dict(row_index=index, is_total=index == len(rows) - 1,
                     fields=_fields(row, TABLE_FIELDS)) for index, row in enumerate(rows)
            ])
        elif endpoint == BALANCE_URL:
            profile = dict(kind="ORDINARY_US_HOLDINGS", groups=_holdings(rows))
        else:
            profile = dict(kind=BASES[endpoint] + "_SUMMARY", row_count=len(rows),
                           rows=[_fields(row, SUMMARY_FIELDS) for row in rows])
        result["responses"].append(profile)
    return result
