"""Read the broker's settlement-basis asset table, without execution authority."""

import re
from datetime import UTC, datetime
from decimal import Decimal, localcontext

from auto_invest.broker.intraday_account import AccountReadError
from auto_invest.broker.intraday_balance_evidence import _time
from auto_invest.broker.overseas import _kis_headers, _split_account

ASSETS_URL = "/uapi/domestic-stock/v1/trading/inquire-account-balance"
TABLE_FIELDS = (
    "pchs_amt", "evlu_amt", "evlu_pfls_amt", "crdt_lnd_amt", "real_nass_amt",
)
SUMMARY_FIELDS = (
    "pchs_amt_smtl", "nass_tot_amt", "loan_amt_smtl", "evlu_pfls_amt_smtl",
    "evlu_amt_smtl", "tot_asst_amt", "tot_lnda_tot_ulst_lnda", "cma_auto_loan_amt",
    "tot_mgln_amt", "stln_evlu_amt", "crdt_fncg_amt", "ocl_apl_loan_amt", "pldg_stup_amt",
    "frcr_evlu_tota", "tot_dncl_amt", "cma_evlu_amt", "dncl_amt", "tot_sbst_amt",
    "thdt_rcvb_amt", "ovrs_stck_evlu_amt1", "ovrs_bond_evlu_amt", "mmf_cma_mgge_loan_amt",
    "sbsc_dncl_amt", "pbst_sbsc_fnds_loan_use_amt", "etpr_crdt_grnt_loan_amt",
)


def _parse(body, product):
    rows, summary = body.get("output1"), body.get("output2")
    # Official property contract: fixed order, last row is total; product21 differs.
    expected = 17 if product == "21" else 20
    if not isinstance(rows, list) or len(rows) != expected or any(
        not isinstance(row, dict) for row in rows
    ):
        raise AccountReadError("ASSETS_CATEGORY_TABLE_SHAPE")
    if not isinstance(summary, dict):
        raise AccountReadError("ASSETS_SUMMARY_SHAPE")

    def numbers(row, fields, part, index):
        result = {}
        for field in fields:
            value = row.get(field)
            if not isinstance(value, str) or not re.fullmatch(
                r"-?[0-9]{1,18}(\.[0-9]{1,12})?", value.strip()
            ):
                raise AccountReadError("ASSETS_INVALID_NUMBER", shape=dict(
                    part=part, row=index, field=field,
                ))
            result[field] = Decimal(value)
        return result

    return dict(
        rows=[numbers(row, TABLE_FIELDS + ("whol_weit_rt",), "output1", index)
              for index, row in enumerate(rows)],
        summary=numbers(summary, SUMMARY_FIELDS, "output2", 0),
    )


def _audit(before, after):
    checks = [dict(check="report_stable", status="MATCH" if before == after else "CHANGED")]
    with localcontext() as context:
        context.prec = 80
        categories, total = after["rows"][:-1], after["rows"][-1]
        for field in TABLE_FIELDS:
            equal = sum((row[field] for row in categories), Decimal(0)) == total[field]
            checks.append(dict(check="category_sum_" + field,
                               status="MATCH" if equal else "MISMATCH"))
        checks.append(dict(
            check="table_net_assets_vs_summary",
            status="MATCH" if total["real_nass_amt"] == after["summary"]["nass_tot_amt"]
            else "MISMATCH",
        ))
    statuses = {check["status"] for check in checks}
    return dict(
        schema_version=1,
        status=next((s for s in ("CHANGED", "MISMATCH") if s in statuses), "MATCH"),
        reporting_basis="SETTLEMENT_ACCOUNT_ASSET_TABLE",
        reported_category_table_complete=True,
        category_count=len(categories),
        nonzero_category_count=sum(any(row[f] != 0 for f in TABLE_FIELDS) for row in categories),
        checks=checks,
        execution_nav_verified=False,
        execution_nav_reasons=["SETTLEMENT_BASIS_NOT_INTRADAY",
                               "BROKER_VALUATION_TIMESTAMP_NOT_PROVIDED",
                               "USD_CASH_COMPOSITION_NOT_VERIFIED"],
        orders_submitted=0,
    )


async def observe_account_assets(
    client, *, access_token, app_key, app_secret, account, now=lambda: datetime.now(UTC),
):
    """Return only public counts/conclusions; credentials and amounts stay private.

    Uses the caller's rate-limited bounded-retry client, as the other KIS reads do.
    No actual valuation time or execution NAV is inferred from successful GETs.
    """
    if not isinstance(account, str) or not re.fullmatch(r"[0-9]{10}", account):
        raise AccountReadError("ASSETS_INVALID_ACCOUNT")
    started = _time(now())
    cano, product = _split_account(account)

    def check_age():
        if not 0 <= (_time(now()) - started).total_seconds() <= 30:
            raise AccountReadError("ASSETS_STALE_BATCH")

    async def collect():
        check_age()
        headers = _kis_headers(
            access_token=access_token, app_key=app_key, app_secret=app_secret,
            tr_id="CTRP6548R",
        )
        headers["tr_cont"] = ""
        try:
            response = await client.request("GET", ASSETS_URL, headers=headers, params=dict(
                CANO=cano, ACNT_PRDT_CD=product, INQR_DVSN_1="", BSPR_BF_DT_APLY_YN="",
            ))
            response.raise_for_status()
            body = response.json()
        except Exception:
            raise AccountReadError("ASSETS_TRANSPORT_OR_JSON_ERROR") from None
        check_age()
        if not isinstance(body, dict) or body.get("rt_cd") != "0":
            raise AccountReadError("ASSETS_BROKER_REJECTED")
        continuation = response.headers.get("tr_cont")
        if continuation is None or continuation.strip() not in {"", "D", "E"}:
            raise AccountReadError("ASSETS_INCOMPLETE_RESPONSE")
        return _parse(body, product)

    before = await collect()
    after = await collect()
    check_age()
    return _audit(before, after)
