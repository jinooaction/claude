"""Value reconciled KRW and USD cash reports under an explicit reporting FX policy."""

from decimal import ROUND_FLOOR, Decimal, localcontext

from auto_invest.broker.account_source_profile import _number
from auto_invest.broker.domestic_account import ROW_FIELDS, SUMMARY_FIELDS
from auto_invest.broker.intraday_cash_baseline import BaselineUnavailable, _require, _stamp


def normalize_reported_cash(baseline, domestic, *, observed_at):
    """A cash-component valuation, never whole-account coverage or spend authority.

    The same KIS observer owns both inputs. No external balance files, source
    counters or approvals are accepted here. Broker-reported first-posted FX is
    a named valuation policy, not a live executable FX quote.
    """
    result = dict(status="UNAVAILABLE", amount_usd=None, balances=None,
                  scope="RECONCILED_KRW_USD_ZERO_ADJUSTMENT_CASH",
                  full_account_verified=False, live_eligible=False)
    try:
        if isinstance(baseline, dict) and baseline.get("status") != "CALCULATED":
            baseline = baseline.get("settlement_cash")
        _require(isinstance(baseline, dict) and baseline.get("status") == "CALCULATED"
                 and isinstance(baseline.get("scope"), str)
                 and baseline.get("scope") in {"REPORTED_ZERO_ADJUSTMENT_USD_BASELINE",
                                                "RECONCILED_USD_REPORTED_SETTLEMENT_LEGS"},
                 "CASH_USD_BASELINE_UNAVAILABLE")
        _require(isinstance(domestic, dict) and domestic.get("currency") == "KRW"
                 and domestic.get("reporting_basis") == "KIS_DOMESTIC_CURRENT_BALANCE"
                 and domestic.get("pagination_complete") is True,
                 "CASH_DOMESTIC_REPORT_UNAVAILABLE")
        start, end = (_stamp(baseline.get(key)) for key in
                      ("observation_started_at", "observation_completed_at"))
        domestic_start, domestic_end = (_stamp(domestic.get(key)) for key in
                                        ("observation_started_at", "observation_completed_at"))
        clock = _stamp(observed_at)
        sequential = start <= end <= domestic_start <= domestic_end <= clock
        enclosed = start <= domestic_start <= domestic_end <= end <= clock
        _require((sequential or enclosed)
                 and 0 <= (clock - start).total_seconds() <= 30, "CASH_REPORT_INTERVAL_INVALID")
        summary = domestic.get("summary")
        _require(isinstance(summary, dict), "CASH_DOMESTIC_SUMMARY_INVALID")
        values = {field: _number(summary.get(field)) for field in SUMMARY_FIELDS}
        _require(all(value is not None for value in values.values()),
                 "CASH_DOMESTIC_AMOUNT_INVALID")
        cash = values["dnca_tot_amt"]
        _require(all(values[field] == cash for field in (
            "nxdy_excc_amt", "prvs_rcdl_excc_amt", "nass_amt", "tot_evlu_amt",
        )), "CASH_DOMESTIC_SETTLEMENT_CHANGED")
        _require(all(values[field] == 0 for field in (
            "cma_evlu_amt", "tot_loan_amt", "scts_evlu_amt", "tot_stln_slng_chgs",
            "bfdy_buy_amt", "thdt_buy_amt", "bfdy_sll_amt", "thdt_sll_amt",
        )), "CASH_DOMESTIC_OTHER_COMPONENTS_PRESENT")
        positions = domestic.get("positions")
        _require(isinstance(positions, dict) and len(positions) <= 1000
                 and all(isinstance(row, dict) and all(_number(row.get(field)) == 0
                     for field in ROW_FIELDS) for row in positions.values()),
                 "CASH_DOMESTIC_OTHER_COMPONENTS_PRESENT")
        _require(cash == _number(baseline.get("reported_krw_total_deposit")),
                 "CASH_KRW_REPORTS_DIFFER")
        usd, rate = _number(baseline.get("cash")), _number(baseline.get("reported_usd_krw_rate"))
        settlement = baseline["scope"] == "RECONCILED_USD_REPORTED_SETTLEMENT_LEGS"
        _require(not settlement or isinstance(baseline.get("reported_components"), dict),
                 "CASH_SETTLEMENT_COMPONENTS_INVALID")
        _require(usd is not None and (settlement or usd >= 0), "CASH_USD_AMOUNT_INVALID")
        _require(rate is not None and rate > 0, "CASH_REPORTED_FX_UNAVAILABLE")
        with localcontext() as context:
            context.prec = 80
            amount = (usd + cash / rate).quantize(Decimal("0.000000000001"),
                                                rounding=ROUND_FLOOR)
        _require(abs(amount) < Decimal("1e18"), "CASH_VALUATION_OUT_OF_RANGE")
        result.update(status="CALCULATED", amount_usd=str(amount),
                      balances={"KRW": str(cash), "USD": str(usd)},
                      reporting_fx=dict(usd_krw_rate=str(rate),
                          basis="KIS_FIRST_POSTED_RATE", rounding="FLOOR_12_DECIMALS",
                          executable_quote=False),
                      observation_started_at=start.isoformat(),
                      observation_completed_at=max(end, domestic_end).isoformat())
        if settlement:
            result.update(scope="RECONCILED_KRW_USD_REPORTED_SETTLEMENT_CASH",
                          usd_settlement_components=dict(baseline["reported_components"]),
                          fees_inclusion_verified=False)
    except BaselineUnavailable as error:
        result["reason"] = str(error)
    return result
