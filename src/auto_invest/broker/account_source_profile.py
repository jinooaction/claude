"""Amount-free structural evidence; repeated values never establish aggregation."""

import re
from decimal import Decimal

MARGIN_URL = "/uapi/overseas-stock/v1/trading/foreign-margin"
CASH_FIELDS = (
    "frcr_dncl_amt1", "ustl_buy_amt", "ustl_sll_amt", "frcr_rcvb_amt", "frcr_mgn_amt",
)
FIELDS = CASH_FIELDS + (
    "frcr_gnrl_ord_psbl_amt", "frcr_ord_psbl_amt1", "itgr_ord_psbl_amt", "bass_exrt",
)


def _number(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"-?[0-9]{1,18}(\.[0-9]{1,12})?", value.strip(),
    ):
        return None
    return Decimal(value.strip())


def _group(rows):
    fields = {}
    for field in FIELDS:
        values = [_number(row.get(field)) for row in rows]
        valid = [value for value in values if value is not None]
        fields[field] = dict(
            valid_count=len(valid), invalid_or_missing_count=len(rows) - len(valid),
            zero_count=sum(value == 0 for value in valid),
            negative_count=sum(value < 0 for value in valid), distinct_count=len(set(valid)),
        )
    vectors = [tuple(_number(row.get(field)) for field in CASH_FIELDS) for row in rows]
    complete = [vector for vector in vectors if None not in vector]
    names = [row.get("natn_name") for row in rows]
    return dict(
        row_count=len(rows), fields=fields, cash_vector_complete_count=len(complete),
        cash_vector_zero_count=sum(all(value == 0 for value in vector) for vector in complete),
        cash_vector_distinct_count=len(set(complete)),
        country_name_present_count=sum(isinstance(name, str) and bool(name.strip())
                                       for name in names),
        country_name_distinct_count=len({name.strip() for name in names
                                         if isinstance(name, str) and name.strip()}),
    )


def profile_margin_responses(responses):
    """Consume the collected batch without echoing any upstream text or amounts.

    Statistics apply to each response separately; no page, repeated snapshot,
    country or currency row is deduplicated or summed into an account balance.
    """
    result = dict(schema_version=1, status="SOURCE_STRUCTURE_UNAVAILABLE", responses=[],
                  excluded_response_count=0, cash_aggregation_verified=False, live_eligible=False)
    if not isinstance(responses, list) or len(responses) > 200:
        return result
    for response in responses:
        if not isinstance(response, dict) or response.get("endpoint") != MARGIN_URL:
            continue
        data = response.get("data")
        if (response.get("http_status") != 200 or not isinstance(data, dict)
                or data.get("rt_cd") != "0"):
            result["excluded_response_count"] += 1
            continue
        rows = data.get("output")
        if (not isinstance(rows, list) or len(rows) > 2000
                or any(not isinstance(row, dict) for row in rows)):
            result["excluded_response_count"] += 1
            continue
        groups = {name: [] for name in ("USD", "OTHER_CURRENCY", "UNCLASSIFIED")}
        for row in rows:
            currency = row.get("crcy_cd")
            currency = currency.strip() if isinstance(currency, str) else ""
            name = ("USD" if currency == "USD" else "OTHER_CURRENCY"
                    if re.fullmatch(r"[A-Z]{3}", currency) else "UNCLASSIFIED")
            groups[name].append(row)
        result["responses"].append({name: _group(group) for name, group in groups.items()})
    if result["responses"]:
        result["status"] = ("SOURCE_STRUCTURE_PARTIAL" if result["excluded_response_count"]
                            else "SOURCE_STRUCTURE_REVIEWED")
    return result
