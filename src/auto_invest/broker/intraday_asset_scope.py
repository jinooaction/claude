"""Cross-check settlement asset categories against current cash and equity inputs."""

from decimal import Decimal, localcontext

from auto_invest.broker.account_asset_evidence import ASSETS_URL, TABLE_FIELDS, _parse
from auto_invest.broker.account_source_profile import _number
from auto_invest.broker.intraday_account import AccountReadError
from auto_invest.broker.intraday_cash_baseline import BaselineUnavailable, _require, _stamp

SUPPORTED_CATEGORIES = frozenset({8, 16, 17})  # Foreign equities, foreign cash, KRW deposit.
EXCLUDED_SUMMARY = (
    "loan_amt_smtl", "tot_lnda_tot_ulst_lnda", "cma_auto_loan_amt", "tot_mgln_amt",
    "stln_evlu_amt", "crdt_fncg_amt", "ocl_apl_loan_amt", "pldg_stup_amt", "cma_evlu_amt",
    "tot_sbst_amt", "thdt_rcvb_amt", "ovrs_bond_evlu_amt", "mmf_cma_mgge_loan_amt",
    "sbsc_dncl_amt", "pbst_sbsc_fnds_loan_use_amt", "etpr_crdt_grnt_loan_amt",
)


def reconcile_asset_categories(reports, cash, holdings, *, observed_at, product):
    result = dict(status="UNAVAILABLE", reported_asset_categories_matched=False,
                  scope="SETTLEMENT_CATEGORIES_WITH_CURRENT_INPUTS",
                  full_account_scope_verified=False, live_eligible=False)
    try:
        _require(isinstance(product, str) and len(product) == 2 and product.isascii()
                 and product.isdigit() and product != "21", "ASSET_SCOPE_PRODUCT_UNSUPPORTED")
        _require(isinstance(cash, dict) and cash.get("status") == "CALCULATED"
                 and isinstance(cash.get("scope"), str)
                 and cash.get("scope") in {"RECONCILED_KRW_USD_ZERO_ADJUSTMENT_CASH",
                                           "RECONCILED_KRW_USD_REPORTED_SETTLEMENT_CASH"},
                 "ASSET_SCOPE_CASH_UNAVAILABLE")
        _require(isinstance(holdings, dict) and holdings.get("status") == "MATCH"
                 and holdings.get("equity_holdings_matched") is True
                 and holdings.get("scope") == "CURRENT_OVERSEAS_EQUITIES_ONLY"
                 and type(holdings.get("positive_holding_count")) is int
                 and 0 <= holdings["positive_holding_count"] <= 2000,
                 "ASSET_SCOPE_HOLDINGS_UNAVAILABLE")
        balances = cash.get("balances")
        _require(isinstance(balances, dict) and set(balances) == {"KRW", "USD"},
                 "ASSET_SCOPE_CURRENCY_UNAVAILABLE")
        krw, usd = _number(balances["KRW"]), _number(balances["USD"])
        _require(krw is not None and usd is not None,
                 "ASSET_SCOPE_CASH_INVALID")
        start, end = (_stamp(cash.get(key)) for key in
                      ("observation_started_at", "observation_completed_at"))
        clock = _stamp(observed_at)
        _require(start <= end <= clock and 0 <= (clock - start).total_seconds() <= 30,
                 "ASSET_SCOPE_INTERVAL_INVALID")
        _require(isinstance(reports, list) and len(reports) == 2, "ASSET_SCOPE_REPORTS_MISSING")
        previous = start
        signatures = []
        for report in reports:
            _require(isinstance(report, dict) and report.get("endpoint") == ASSETS_URL
                     and report.get("http_status") == 200
                     and isinstance(report.get("continuation"), str)
                     and report.get("continuation") in {"", "D", "E"},
                     "ASSET_SCOPE_RESPONSE_INVALID")
            began, received = _stamp(report.get("started_at")), _stamp(report.get("received_at"))
            _require(previous <= began <= received <= end, "ASSET_SCOPE_INTERVAL_INVALID")
            previous = received
            body = report.get("data")
            _require(isinstance(body, dict) and body.get("rt_cd") == "0",
                     "ASSET_SCOPE_RESPONSE_INVALID")
            parsed = _parse(body, product)
            rows, summary = parsed["rows"], parsed["summary"]
            _require(len(rows) == 20, "ASSET_SCOPE_PRODUCT_UNSUPPORTED")
            with localcontext() as context:
                context.prec = 80
                _require(all(sum((row[field] for row in rows[:-1]), Decimal(0))
                             == rows[-1][field] for field in TABLE_FIELDS),
                         "ASSET_SCOPE_CATEGORY_SUM_DIFFERS")
            _require(all(row["crdt_lnd_amt"] == 0 for row in rows)
                     and all(summary[field] == 0 for field in EXCLUDED_SUMMARY),
                     "ASSET_SCOPE_OTHER_LIABILITY_PRESENT")
            _require(all(all(row[field] == 0 for field in TABLE_FIELDS)
                         for index, row in enumerate(rows[:-1])
                         if index not in SUPPORTED_CATEGORIES), "ASSET_SCOPE_OTHER_ASSET_PRESENT")
            _require(rows[17]["evlu_amt"] == summary["dncl_amt"] == summary["tot_dncl_amt"] == krw,
                     "ASSET_SCOPE_KRW_DIFFERS")
            _require(rows[8]["evlu_amt"] >= 0 and rows[16]["evlu_amt"] >= 0
                     and (holdings["positive_holding_count"] > 0 or rows[8]["evlu_amt"] == 0),
                     "ASSET_SCOPE_EQUITY_PRESENCE_DIFFERS")
            if cash["scope"] == "RECONCILED_KRW_USD_ZERO_ADJUSTMENT_CASH":
                _require(usd >= 0 and (usd > 0) == (rows[16]["evlu_amt"] > 0),
                         "ASSET_SCOPE_FOREIGN_CASH_PRESENCE_DIFFERS")
            signatures.append(tuple(rows[index]["pchs_amt"] for index in (8, 16, 17)))
        _require(signatures[0] == signatures[1], "ASSET_SCOPE_COMPONENTS_CHANGED")
        result.update(status="MATCH", reported_asset_categories_matched=True,
                      category_count=19,
                      current_positive_holding_count=holdings["positive_holding_count"])
    except (BaselineUnavailable, AccountReadError) as error:
        result["reason"] = str(error)
    return result
