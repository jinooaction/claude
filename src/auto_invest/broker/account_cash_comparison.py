"""Compare original reported cash fields; numerical equality is not certification."""

from decimal import localcontext

from auto_invest.broker.account_source_profile import CASH_FIELDS, MARGIN_URL, _number

ROOT = "/uapi/overseas-stock/v1/trading/"
BASES = {
    ROOT + "inquire-present-balance": "CURRENT",
    ROOT + "inquire-paymt-stdr-balance": "SETTLED",
}
TOTAL_FIELDS = (
    "tot_dncl_amt", "frcr_evlu_tota", "evlu_amt_smtl", "ustl_sll_amt_smtl",
    "ustl_buy_amt_smtl", "tot_asst_amt",
)


def _rows(value):
    value = [value] if isinstance(value, dict) else value
    return value if (isinstance(value, list) and len(value) <= 2000
                     and all(isinstance(row, dict) for row in value)) else None


def _relation(left, right):
    if left is None or right is None:
        return "UNAVAILABLE"
    return "EQUAL" if left == right else "DIFFERENT"


def compare_cash_sources(responses):
    result = dict(schema_version=1, comparisons=[], common_margin_cash_available=False,
                  margin_adjustments_zero=False, cash_aggregation_verified=False,
                  live_eligible=False)
    if not isinstance(responses, list) or len(responses) > 200:
        return result
    margins, reports = [], []
    for response in responses:
        if not isinstance(response, dict):
            continue
        endpoint, data = response.get("endpoint"), response.get("data")
        if not isinstance(endpoint, str):
            continue
        good = (response.get("http_status") == 200 and isinstance(data, dict)
                and data.get("rt_cd") == "0")
        if endpoint == MARGIN_URL:
            margins.append(_rows(data.get("output")) if good else None)
        elif endpoint in BASES:
            reports.append((BASES[endpoint], data if good else {}))
    common = None
    if len(margins) == 1 and margins[0] is not None:
        usd = [row for row in margins[0] if isinstance(row.get("crcy_cd"), str)
               and row["crcy_cd"].strip() == "USD"]
        vectors = [tuple(_number(row.get(field)) for field in CASH_FIELDS) for row in usd]
        if vectors and all(None not in vector for vector in vectors) and len(set(vectors)) == 1:
            common = vectors[0]
            result["common_margin_cash_available"] = True
            result["margin_adjustments_zero"] = all(value == 0 for value in common[1:])
    with localcontext() as context:
        context.prec = 80
        for basis, data in reports:
            currencies, summaries = _rows(data.get("output2")), _rows(data.get("output3"))
            usd = [row for row in currencies or [] if row.get("crcy_cd") == "USD"]
            single = usd[0] if len(usd) == 1 else {}
            amount = _number(single.get("frcr_dncl_amt_2"))
            fx = _number(single.get("frst_bltn_exrt"))
            other_zero = currencies is not None and all(
                _number(row.get("frcr_dncl_amt_2")) == 0
                for row in currencies if row.get("crcy_cd") != "USD"
            )
            summary = summaries[0] if summaries is not None and len(summaries) == 1 else {}
            converted = amount * fx if (amount is not None and fx is not None and fx > 0
                                        and other_zero) else None
            values = [_number(summary.get(field)) for field in TOTAL_FIELDS]
            total = sum(values[:4]) - values[4] if None not in values else None
            result["comparisons"].append(dict(
                reporting_basis=basis,
                common_deposit_vs_reported_usd=_relation(common[0] if common else None, amount),
                single_usd_conversion_vs_foreign_total=_relation(
                    converted, _number(summary.get("frcr_evlu_tota"))),
                hts_total_formula_candidate=_relation(total, values[-1]),
                other_reported_currency_amounts_zero=other_zero,
                equivalence_verified=False,
            ))
    return result
