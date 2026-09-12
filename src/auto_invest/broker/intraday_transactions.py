"""Read complete KIS transaction reports without inventing cash or fill fees.

Rows have no documented order identifier. Keep duplicate rows and each fee
component; attaching them to individual fills requires a separate reconciliation.
"""

import asyncio
import re
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext

from auto_invest.broker.intraday_account import AccountReadError
from auto_invest.broker.overseas import _kis_headers, _split_account

PATH = "/uapi/overseas-stock/v1/trading/inquire-period-trans"
READ_TIMEOUT_SECONDS = 30
AMOUNTS = (
    "ccld_qty", "tr_frcr_amt2", "frcr_excc_amt_1", "dmst_frcr_fee1", "frcr_fee1",
)


def _day(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8}", value):
        raise AccountReadError("TRANSACTIONS_INVALID_DATE")
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:]))
    except ValueError:
        raise AccountReadError("TRANSACTIONS_INVALID_DATE") from None


def _stamp(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise AccountReadError("TRANSACTIONS_INVALID_TIME")
    return value.astimezone(UTC)


def validate_window(start_date, end_date):
    if _day(start_date) > _day(end_date):
        raise AccountReadError("TRANSACTIONS_DATE_ORDER")


def _row(raw):
    result = {}
    for field in ("trad_dt", "sttl_dt"):
        _day(raw.get(field))
        result[field] = raw[field]
    for field, pattern in (("pdno", r"[A-Za-z0-9._-]{1,32}"),
                           ("crcy_cd", r"[A-Z]{3}"),
                           ("sll_buy_dvsn_cd", r"0[12]")):
        value = raw.get(field)
        if not isinstance(value, str) or not re.fullmatch(pattern, value.strip()):
            raise AccountReadError("TRANSACTIONS_INVALID_IDENTITY")
        result[field] = value.strip()
    for field in AMOUNTS:
        value = raw.get(field)
        if not isinstance(value, str) or not re.fullmatch(
            r"[0-9]{1,18}(\.[0-9]{1,12})?", value.strip()
        ):
            raise AccountReadError("TRANSACTIONS_INVALID_AMOUNT")
        result[field] = str(Decimal(value))
    if Decimal(result["ccld_qty"]) <= 0:
        raise AccountReadError("TRANSACTIONS_INVALID_QUANTITY")
    return result


def audit_settlements(rows):
    """Check report arithmetic, not completeness of account cash or actual fees.

    A match only means that the two reported fee components explain the reported
    settlement difference. It cannot identify individual orders, other cash flows,
    fee schedules or whether these registration-date rows cover a trade window.
    """
    if not isinstance(rows, list) or len(rows) > 100_000:
        raise AccountReadError("TRANSACTIONS_INVALID_OUTPUT")
    totals, mismatches = {}, []
    with localcontext() as context:
        context.prec = 64
        for index, raw in enumerate(rows):
            if not isinstance(raw, dict):
                raise AccountReadError("TRANSACTIONS_INVALID_OUTPUT")
            value = _row(raw)
            gross, settled, domestic, foreign = (
                Decimal(value[key]) for key in (
                    "tr_frcr_amt2", "frcr_excc_amt_1", "dmst_frcr_fee1", "frcr_fee1",
                )
            )
            buying = value["sll_buy_dvsn_cd"] == "02"
            fees = domestic + foreign
            expected = gross + fees if buying else gross - fees
            if settled != expected:
                mismatches.append(index)
            currency = totals.setdefault(value["crcy_cd"], dict.fromkeys((
                "gross_buy", "gross_sell", "domestic_fee", "foreign_fee", "net_settlement",
            ), Decimal(0)))
            currency["gross_buy" if buying else "gross_sell"] += gross
            currency["domestic_fee"] += domestic
            currency["foreign_fee"] += foreign
            currency["net_settlement"] += -settled if buying else settled
    verified = bool(rows) and not mismatches
    return dict(
        status="NO_TRANSACTIONS" if not rows else "MATCH" if verified else "MISMATCH",
        row_count=len(rows), matched_row_count=len(rows) - len(mismatches),
        mismatched_row_count=len(mismatches), currency_count=len(totals),
        arithmetic_verified=verified, mismatched_row_indices=mismatches,
        currency_totals={currency: {key: str(value) for key, value in amounts.items()}
                         for currency, amounts in totals.items()} if verified else None,
    )


async def observe_transactions(
    client, *, account, access_token, app_key, app_secret, start_date, end_date,
    exchange="", max_pages=20, now=lambda: datetime.now(UTC),
):
    """GET the requested reporting scope, failing without any partial result.

    Dates are registration-date filters, not proof of a complete trade-date
    window. The current CTOS4001R property contract requires an empty exchange
    filter. This is the endpoint's all-exchange report, not all account cash flows.
    Caller supplies the existing rate-limited client and credential authority.
    """
    validate_window(start_date, end_date)
    if not isinstance(account, str) or not re.fullmatch(r"[0-9]{10}", account):
        raise AccountReadError("TRANSACTIONS_INVALID_ACCOUNT")
    if not isinstance(exchange, str) or exchange != "":
        raise AccountReadError("TRANSACTIONS_INVALID_EXCHANGE")
    if type(max_pages) is not int or not 1 <= max_pages <= 100:
        raise AccountReadError("TRANSACTIONS_INVALID_PAGE_LIMIT")
    started = _stamp(now())
    cano, product = _split_account(account)
    rows, source_rows, summaries, seen = [], [], [], set()
    cursor = ("", "")
    async with asyncio.timeout(READ_TIMEOUT_SECONDS):
        for page in range(max_pages):
            elapsed = (_stamp(now()) - started).total_seconds()
            if not 0 <= elapsed <= 30:
                raise AccountReadError("TRANSACTIONS_STALE_BATCH")
            headers = _kis_headers(
                access_token=access_token, app_key=app_key, app_secret=app_secret,
                tr_id="CTOS4001R",
            )
            headers["tr_cont"] = "N" if page else ""
            try:
                response = await client.request("GET", PATH, headers=headers, params=dict(
                    CANO=cano, ACNT_PRDT_CD=product, ERLM_STRT_DT=start_date,
                    ERLM_END_DT=end_date, OVRS_EXCG_CD=exchange, PDNO="",
                    SLL_BUY_DVSN_CD="00", LOAN_DVSN_CD="",
                    CTX_AREA_FK100=cursor[0], CTX_AREA_NK100=cursor[1],
                ))
                response.raise_for_status()
                body = response.json()
            except Exception:
                raise AccountReadError("TRANSACTIONS_TRANSPORT_OR_JSON_ERROR") from None
            completed = _stamp(now())
            if not 0 <= (completed - started).total_seconds() <= 30:
                raise AccountReadError("TRANSACTIONS_STALE_BATCH")
            if not isinstance(body, dict) or body.get("rt_cd") != "0":
                raise AccountReadError("TRANSACTIONS_BROKER_REJECTED")
            for name, target in (("output1", rows), ("output2", summaries)):
                raw = body.get(name)
                if isinstance(raw, dict) and raw:
                    raw = [raw]
                if (not isinstance(raw, list) or len(raw) > 1000
                        or any(not isinstance(value, dict) for value in raw)):
                    raise AccountReadError("TRANSACTIONS_INVALID_OUTPUT")
                # Summary rows can repeat across pages. Never sum/deduplicate.
                if name == "output1":
                    target.extend(_row(value) for value in raw)
                    source_rows.extend(dict(value) for value in raw)
                else:
                    target.append(raw)
            continuation = response.headers.get("tr_cont")
            if continuation not in {"", "D", "E", "M", "F"}:
                raise AccountReadError("TRANSACTIONS_CONTINUATION_HEADER")
            if continuation in {"", "D", "E"}:
                return dict(
                    observation_started_at=started.isoformat(),
                    observation_completed_at=completed.isoformat(),
                    registration_start_date=start_date, registration_end_date=end_date,
                    requested_exchange=exchange, rows=rows, source_rows=source_rows,
                    summary_pages=summaries,
                    page_count=page + 1, pagination_complete=True,
                    settlement_audit=audit_settlements(rows),
                    cash_verified=False, execution_parity_verified=False,
                )
            following = tuple(body.get(key) for key in ("ctx_area_fk100", "ctx_area_nk100"))
            if (any(not isinstance(value, str) or len(value) > 100 for value in following)
                    or not any(value.strip() for value in following)
                    or following == cursor or following in seen):
                raise AccountReadError("TRANSACTIONS_CURSOR_STALLED")
            seen.add(following)
            cursor = following
    raise AccountReadError("TRANSACTIONS_PAGE_LIMIT")


def public_transactions(snapshot):
    """Counts only: no account data, amounts, symbols, dates or source rows."""
    return dict(
        status="TRANSACTION_REPORT_OBSERVED", row_count=len(snapshot["rows"]),
        page_count=snapshot["page_count"], pagination_complete=snapshot["pagination_complete"],
        settlement_audit={key: snapshot["settlement_audit"][key] for key in (
            "status", "row_count", "matched_row_count", "mismatched_row_count",
            "currency_count", "arithmetic_verified",
        )},
        cash_verified=False, execution_parity_verified=False,
        live_eligible=False, orders_submitted=0,
    )
