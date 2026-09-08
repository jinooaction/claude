"""Audit reported balance arithmetic without granting execution NAV authority."""

import json
import re
from decimal import Decimal, localcontext

POSITION_MONEY = (
    "ccld_qty_smtl1", "ovrs_now_pric1", "frcr_pchs_amt", "frcr_evlu_amt2",
    "evlu_pfls_amt2", "bass_exrt",
)
CURRENCY_MONEY = (
    "frcr_dncl_amt_2", "frcr_buy_mgn_amt", "frcr_etc_mgna", "frcr_drwg_psbl_amt_1",
)
SUMMARY_MONEY = (
    "pchs_amt_smtl", "evlu_amt_smtl", "evlu_pfls_amt_smtl", "dncl_amt",
    "cma_evlu_amt", "tot_dncl_amt", "frcr_evlu_tota", "tot_asst_amt",
    "ustl_sll_amt_smtl", "ustl_buy_amt_smtl", "tot_loan_amt",
)
FIELDS = {
    "output1": POSITION_MONEY + (
        "pdno", "buy_crcy_cd", "ovrs_excg_cd", "prdt_type_cd", "loan_dt",
    ),
    "output2": CURRENCY_MONEY + ("crcy_cd",),
    "output3": SUMMARY_MONEY,
}


def select_records(outputs):
    """Keep only audit inputs in memory; callers must never publish these rows."""
    return {
        part: [{key: row[key] for key in fields if key in row} for row in outputs[part]]
        for part, fields in FIELDS.items()
    }


def _canonical(rows):
    return sorted(json.dumps(row, sort_keys=True, allow_nan=False) for row in rows)


def audit_report(before, after):
    """Return count-only comparisons; MATCH means report arithmetic, not live NAV.

    Field semantics: KIS CTRP6504R property orders 004.005/007-014 and
    006.001-003. Cash/total composition and broker valuation timestamps have
    no sufficient public contract here and are explicitly NOT certified.
    """
    with localcontext() as context:
        context.prec = 80
        return _audit(select_records(before), select_records(after))


def _audit(before, after):
    checks, invalid = [], []

    def record(name, status, reason=None, row=None):
        result = dict(check=name, status=status)
        if reason:
            result["reason"] = reason
        if row is not None:
            result["row"] = row
        checks.append(result)

    def number(row, field, part, index):
        value = row.get(field)
        if not isinstance(value, str) or not re.fullmatch(
            r"-?[0-9]{1,18}(\.[0-9]{1,12})?", value.strip()
        ):
            invalid.append(dict(part=part, row=index, field=field))
            return None
        return Decimal(value)

    def compare(name, expected, reported, *, rounding=Decimal(0), row=None):
        if expected is None or reported is None:
            record(name, "INCOMPLETE", "MISSING_OR_INVALID_COMPONENT", row)
        elif expected == reported:
            record(name, "MATCH", row=row)
        elif abs(expected - reported) <= rounding:
            record(name, "INCOMPLETE", "ROUNDING_DIFFERENCE", row)
        else:
            record(name, "MISMATCH", "ARITHMETIC_DIFFERENCE", row)

    for part in FIELDS:
        record(part + "_stable", "MATCH" if (
            _canonical(before[part]) == _canonical(after[part])
        ) else "CHANGED")

    positions, currencies, summaries = (after[key] for key in FIELDS)
    symbols = [row.get("pdno") for row in positions]
    unique_positions = all(
        isinstance(s, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,32}", s.strip())
        for s in symbols
    ) and len({s.strip() for s in symbols}) == len(symbols)
    record("positions_unique", "MATCH" if unique_positions else "INCOMPLETE",
           None if unique_positions else "POSITION_IDENTITY_AMBIGUOUS")

    codes = [row.get("crcy_cd") for row in currencies]
    unique_currencies = all(
        isinstance(c, str) and re.fullmatch(r"[A-Z]{3}", c.strip()) for c in codes
    ) and len({c.strip() for c in codes}) == len(codes)
    record("currencies_unique", "MATCH" if unique_currencies else "INCOMPLETE",
           None if unique_currencies else "CURRENCY_IDENTITY_AMBIGUOUS")
    holding_currencies = [row.get("buy_crcy_cd") for row in positions]
    currency_coverage = unique_currencies and all(
        isinstance(c, str) and c.strip() in {v.strip() for v in codes}
        for c in holding_currencies
    )
    record("currency_coverage", "MATCH" if currency_coverage else "INCOMPLETE",
           None if currency_coverage else "HOLDING_CURRENCY_NOT_COVERED")

    aggregate = {field: Decimal(0) for field in (
        "frcr_pchs_amt", "frcr_evlu_amt2", "evlu_pfls_amt2",
    )}
    aggregate_valid = unique_positions and currency_coverage
    # Do not infer the quotation unit for per-100 currencies from the name.
    fx_supported = all(c == "USD" for c in holding_currencies)
    for index, row in enumerate(positions):
        parsed = {field: number(row, field, "output1", index) for field in POSITION_MONEY}
        nonnegative = all(
            parsed[k] is not None and parsed[k] >= 0 for k in (
                "ccld_qty_smtl1", "ovrs_now_pric1", "frcr_pchs_amt", "frcr_evlu_amt2",
            )
        ) and parsed["bass_exrt"] is not None and parsed["bass_exrt"] > 0
        record("position_fields", "MATCH" if nonnegative and all(
            v is not None for v in parsed.values()
        ) else "INCOMPLETE", None if nonnegative else "INVALID_POSITION_COMPONENT", index)
        qty, price = parsed["ccld_qty_smtl1"], parsed["ovrs_now_pric1"]
        if row.get("buy_crcy_cd") == "USD":
            compare("position_valuation", qty * price if qty is not None and price is not None
                    else None, parsed["frcr_evlu_amt2"], row=index)
        else:
            record("position_valuation", "INCOMPLETE", "PRICE_UNIT_UNVERIFIED", index)
        value, cost = parsed["frcr_evlu_amt2"], parsed["frcr_pchs_amt"]
        compare("position_profit", value - cost if value is not None and cost is not None
                else None, parsed["evlu_pfls_amt2"], row=index)
        if not nonnegative or any(v is None for v in parsed.values()):
            aggregate_valid = False
        else:
            for field in aggregate:
                aggregate[field] += parsed[field] * parsed["bass_exrt"]

    start_errors = len(invalid)
    for index, row in enumerate(currencies):
        for field in CURRENCY_MONEY:
            number(row, field, "output2", index)
    record("currency_components", "MATCH" if len(invalid) == start_errors else "INCOMPLETE",
           None if len(invalid) == start_errors else "MISSING_OR_INVALID_COMPONENT")

    record("summary_unique", "MATCH" if len(summaries) == 1 else "INCOMPLETE",
           None if len(summaries) == 1 else "SUMMARY_ROW_COUNT")
    summary = {}
    if len(summaries) == 1:
        summary = {field: number(summaries[0], field, "output3", 0) for field in SUMMARY_MONEY}
    record("summary_components", "MATCH" if summary and all(
        value is not None for value in summary.values()
    ) else "INCOMPLETE")
    for name, field, total in (
        ("purchase_krw", "frcr_pchs_amt", "pchs_amt_smtl"),
        ("valuation_krw", "frcr_evlu_amt2", "evlu_amt_smtl"),
        ("profit_krw", "evlu_pfls_amt2", "evlu_pfls_amt_smtl"),
    ):
        if not fx_supported:
            record(name, "INCOMPLETE", "FX_UNIT_UNVERIFIED")
        else:
            compare(name, aggregate[field] if aggregate_valid else None,
                    summary.get(total), rounding=Decimal(len(positions)))
    value, cost = summary.get("evlu_amt_smtl"), summary.get("pchs_amt_smtl")
    compare("summary_profit", value - cost if value is not None and cost is not None else None,
            summary.get("evlu_pfls_amt_smtl"), rounding=Decimal(1))
    statuses = {c["status"] for c in checks}
    status = next((s for s in ("CHANGED", "MISMATCH", "INCOMPLETE") if s in statuses), "MATCH")
    return dict(
        schema_version=1, status=status, positions_checked=len(positions),
        checks=checks[:100], check_count=len(checks), checks_truncated=len(checks) > 100,
        check_counts={s: sum(c["status"] == s for c in checks)
                      for s in ("MATCH", "MISMATCH", "INCOMPLETE", "CHANGED")},
        invalid_field_count=len(invalid), invalid_fields=invalid[:30],
        cash_composition_status="CONTRACT_UNVERIFIED",
        total_asset_composition_status="CONTRACT_UNVERIFIED",
        execution_nav_verified=False,
        execution_nav_reasons=[
            "CASH_AND_TOTAL_COMPOSITION_NOT_DOCUMENTED",
            "BROKER_VALUATION_TIMESTAMP_NOT_PROVIDED",
            "DOMESTIC_AND_OTHER_ACCOUNT_ASSETS_NOT_COVERED",
        ],
    )
