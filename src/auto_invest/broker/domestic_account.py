"""Read current domestic holdings separately from the settlement-basis asset table."""

import asyncio
import re
from datetime import UTC, datetime
from decimal import Decimal

from auto_invest.broker.intraday_account import AccountReadError
from auto_invest.broker.overseas import _kis_headers, _split_account

URL = "/uapi/domestic-stock/v1/trading/inquire-balance"
READ_TIMEOUT_SECONDS = 30
ROW_FIELDS = ("hldg_qty", "ord_psbl_qty", "evlu_amt", "loan_amt", "stln_slng_chgs")
SUMMARY_FIELDS = (
    "dnca_tot_amt", "nxdy_excc_amt", "prvs_rcdl_excc_amt", "cma_evlu_amt",
    "tot_loan_amt", "scts_evlu_amt", "tot_evlu_amt", "nass_amt", "tot_stln_slng_chgs",
    "bfdy_buy_amt", "thdt_buy_amt", "bfdy_sll_amt", "thdt_sll_amt",
)


def _number(row, field, *, signed=False):
    value = row.get(field)
    if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]{1,18}(\.[0-9]{1,12})?",
                                                     value.strip()):
        raise AccountReadError("DOMESTIC_INVALID_NUMBER", shape=dict(field=field))
    number = Decimal(value.strip())
    if not signed and number < 0:
        raise AccountReadError("DOMESTIC_NEGATIVE_HOLDING", shape=dict(field=field))
    return number


def _time(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise AccountReadError("DOMESTIC_INVALID_TIME")
    return value.astimezone(UTC)


async def observe_domestic_account(client, *, access_token, app_key, app_secret, account,
                                   now=lambda: datetime.now(UTC), max_pages=20):
    """Own a bounded GET-only sequence on the caller's resilient client."""
    try:
        return await asyncio.wait_for(_collect(client, access_token=access_token,
            app_key=app_key, app_secret=app_secret, account=account, now=now,
            max_pages=max_pages), READ_TIMEOUT_SECONDS)
    except TimeoutError:
        raise AccountReadError("DOMESTIC_READ_TIMEOUT") from None


async def _collect(client, *, access_token, app_key, app_secret, account, now, max_pages):
    if not isinstance(account, str) or not re.fullmatch(r"[0-9]{10}", account):
        raise AccountReadError("DOMESTIC_INVALID_ACCOUNT")
    if type(max_pages) is not int or not 1 <= max_pages <= 20:
        raise AccountReadError("DOMESTIC_INVALID_PAGE_LIMIT")
    started = previous = _time(now())
    cano, product = _split_account(account)
    cursor, seen = ("", ""), set()
    positions, summary = {}, None

    def check_time():
        nonlocal previous
        stamp = _time(now())
        if not previous <= stamp or not 0 <= (stamp - started).total_seconds() <= 30:
            raise AccountReadError("DOMESTIC_STALE_BATCH")
        previous = stamp
        return stamp

    for page in range(max_pages):
        check_time()
        headers = _kis_headers(access_token=access_token, app_key=app_key,
                               app_secret=app_secret, tr_id="TTTC8434R")
        headers["tr_cont"] = "N" if page else ""
        params = dict(CANO=cano, ACNT_PRDT_CD=product, AFHR_FLPR_YN="N", OFL_YN="",
            INQR_DVSN="02", UNPR_DVSN="01", FUND_STTL_ICLD_YN="Y",
            FNCG_AMT_AUTO_RDPT_YN="N", PRCS_DVSN="00",
            CTX_AREA_FK100=cursor[0], CTX_AREA_NK100=cursor[1])
        try:
            response = await client.request("GET", URL, headers=headers, params=params)
            response.raise_for_status()
            body = response.json()
        except Exception:
            raise AccountReadError("DOMESTIC_TRANSPORT_OR_JSON_ERROR") from None
        completed = check_time()
        if not isinstance(body, dict) or body.get("rt_cd") != "0":
            raise AccountReadError("DOMESTIC_BROKER_REJECTED")
        rows, summaries = body.get("output1"), body.get("output2")
        if not isinstance(rows, list) or len(rows) > 50 or any(
                not isinstance(row, dict) for row in rows):
            raise AccountReadError("DOMESTIC_HOLDINGS_SHAPE")
        if isinstance(summaries, dict):
            summaries = [summaries]
        if (not isinstance(summaries, list) or len(summaries) != 1
                or not isinstance(summaries[0], dict)):
            raise AccountReadError("DOMESTIC_SUMMARY_SHAPE")
        current = {field: _number(summaries[0], field, signed=True)
                   for field in SUMMARY_FIELDS}
        if summary is not None and current != summary:
            raise AccountReadError("DOMESTIC_SUMMARY_CHANGED")
        summary = current
        for row in rows:
            symbol = row.get("pdno")
            if (not isinstance(symbol, str)
                    or not re.fullmatch(r"[A-Z0-9._-]{1,32}", symbol.strip())):
                raise AccountReadError("DOMESTIC_SYMBOL_INVALID")
            symbol = symbol.strip()
            if symbol in positions:
                raise AccountReadError("DOMESTIC_DUPLICATE_HOLDING")
            values = {field: _number(row, field) for field in ROW_FIELDS}
            if values["ord_psbl_qty"] > values["hldg_qty"]:
                raise AccountReadError("DOMESTIC_SELLABLE_EXCEEDS_HOLDING")
            positions[symbol] = {field: str(value) for field, value in values.items()}
        continuation = response.headers.get("tr_cont")
        if continuation is None or continuation.strip() not in {"", "D", "E", "M", "F"}:
            raise AccountReadError("DOMESTIC_CONTINUATION_INVALID")
        continuation = continuation.strip()
        keys = ("ctx_area_fk100", "ctx_area_nk100")
        if any(not isinstance(body.get(key), str) for key in keys):
            raise AccountReadError("DOMESTIC_CURSOR_INVALID")
        next_cursor = tuple(body[key] for key in keys)
        if continuation in {"D", "E"} or (
                not continuation and not any(part.strip() for part in next_cursor)):
            return dict(reporting_basis="KIS_DOMESTIC_CURRENT_BALANCE", currency="KRW",
                observation_started_at=started.isoformat(),
                observation_completed_at=completed.isoformat(),
                positions=positions, summary={key: str(value) for key, value in summary.items()},
                pagination_complete=True,
                page_count=page + 1, full_account_verified=False)
        if (not any(part.strip() for part in next_cursor)
                or next_cursor == cursor or next_cursor in seen):
            raise AccountReadError("DOMESTIC_CURSOR_STALLED")
        seen.add(next_cursor)
        cursor = next_cursor
    raise AccountReadError("DOMESTIC_PAGE_LIMIT")


def public_domestic_account(snapshot):
    """Expose counts and signs, never account holdings or money amounts."""
    return dict(reporting_basis=snapshot["reporting_basis"], currency="KRW",
        pagination_complete=snapshot["pagination_complete"], page_count=snapshot["page_count"],
        holding_count=sum(Decimal(row["hldg_qty"]) > 0 for row in snapshot["positions"].values()),
        zero_quantity_row_count=sum(Decimal(row["hldg_qty"]) == 0
                                    for row in snapshot["positions"].values()),
        summary_states={field: "ZERO" if Decimal(value) == 0 else
                        "POSITIVE" if Decimal(value) > 0 else "NEGATIVE"
                        for field, value in snapshot["summary"].items()},
        full_account_verified=False)
