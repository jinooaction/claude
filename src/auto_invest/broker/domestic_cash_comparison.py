"""Compare captured KRW report fields without choosing a cash accounting rule."""

from decimal import localcontext

from auto_invest.broker.account_asset_evidence import ASSETS_URL
from auto_invest.broker.account_cash_comparison import BASES, _relation, _rows
from auto_invest.broker.account_source_profile import _number
from auto_invest.broker.domestic_account import SUMMARY_FIELDS, URL


def _summary(response, field):
    data = response.get("data")
    if (response.get("http_status") != 200 or not isinstance(data, dict)
            or data.get("rt_cd") != "0"):
        return None
    rows = _rows(data.get(field))
    return rows[0] if rows is not None and len(rows) == 1 else None


def compare_domestic_cash_sources(responses):
    """Preserve missing/changed reports; equality never certifies account scope.

    Domestic page summaries repeat, so compare every vector instead of summing
    them. The caller owns account binding, pagination and query-time validation.
    This diagnostic does not claim that separately queried reports are atomic.
    """
    result = dict(schema_version=1, domestic_reference_status="UNAVAILABLE",
                  domestic_checks={}, comparisons=[], cash_aggregation_verified=False,
                  temporal_equivalence_verified=False, live_eligible=False)
    if not isinstance(responses, list) or len(responses) > 200:
        return result
    records = [row for row in responses if isinstance(row, dict)]
    domestic = [row for row in records if row.get("endpoint") == URL]
    vectors = []
    for response in domestic:
        row = _summary(response, "output2")
        vector = tuple(_number(row.get(field)) for field in SUMMARY_FIELDS) if row else ()
        if not vector or None in vector:
            result["domestic_reference_status"] = "INVALID"
            return result
        vectors.append(vector)
    if not vectors:
        return result
    if len(set(vectors)) != 1:
        result["domestic_reference_status"] = "CHANGED"
        return result
    domestic = dict(zip(SUMMARY_FIELDS, vectors[0], strict=True))
    result["domestic_reference_status"] = "AVAILABLE"
    cash = domestic["dnca_tot_amt"]
    result["domestic_checks"] = dict(
        deposit_vs_next_day=_relation(cash, domestic["nxdy_excc_amt"]),
        deposit_vs_d2=_relation(cash, domestic["prvs_rcdl_excc_amt"]),
        deposit_vs_net_assets=_relation(cash, domestic["nass_amt"]),
        deposit_vs_total_valuation=_relation(cash, domestic["tot_evlu_amt"]),
        other_components_zero=all(domestic[field] == 0 for field in (
            "cma_evlu_amt", "tot_loan_amt", "scts_evlu_amt", "tot_stln_slng_chgs",
            "bfdy_buy_amt", "thdt_buy_amt", "bfdy_sll_amt", "thdt_sll_amt",
        )),
    )
    with localcontext() as context:
        context.prec = 80
        for response in records:
            endpoint = response.get("endpoint")
            if not isinstance(endpoint, str) or endpoint not in {*BASES, ASSETS_URL}:
                continue
            row = _summary(response, "output2" if endpoint == ASSETS_URL else "output3")
            row = row or {}
            foreign = _number(row.get("frcr_evlu_tota"))
            total = _number(row.get("tot_dncl_amt"))
            category = None
            if endpoint == ASSETS_URL and row:
                table = _rows(response["data"].get("output1"))
                # Only the documented ordinary-account 20-row layout is mapped.
                if table is not None and len(table) == 20:
                    category = _number(table[17].get("evlu_amt"))
            result["comparisons"].append(dict(
                reporting_basis=BASES.get(endpoint, "SETTLEMENT_ASSET_TABLE"),
                domestic_deposit_vs_reported_deposit=_relation(cash, _number(row.get("dncl_amt"))),
                domestic_deposit_vs_total_deposit=_relation(cash, total),
                domestic_plus_foreign_vs_total_deposit=_relation(
                    cash + foreign if foreign is not None else None, total),
                domestic_deposit_vs_deposit_category=_relation(cash, category),
                equivalence_verified=False,
            ))
    return result
