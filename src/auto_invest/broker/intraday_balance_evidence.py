"""GET-only balance evidence; equal reported fields do not establish execution NAV."""

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from auto_invest.broker.intraday_account import AccountReadError
from auto_invest.broker.overseas import _kis_headers, _split_account

ROOT = "/uapi/overseas-stock/v1/trading/"
CURRENT = "inquire-present-balance"
SETTLED = "inquire-paymt-stdr-balance"
OUTPUTS = ("output1", "output2", "output3")


def _time(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise AccountReadError("BALANCE_INVALID_TIME")
    return value


def _currency_rows(rows):
    result, blank = [], 0
    for row in rows:
        currency = row.get("crcy_cd")
        if not isinstance(currency, str):
            raise AccountReadError("BALANCE_INVALID_CURRENCY")
        currency = currency.strip()
        if not currency:
            blank += 1
            continue
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise AccountReadError("BALANCE_INVALID_CURRENCY")
        amount = row.get("frcr_dncl_amt_2")
        if not isinstance(amount, str) or not re.fullmatch(
            r"-?[0-9]{1,18}(\.[0-9]{1,12})?", amount.strip()
        ):
            raise AccountReadError("BALANCE_INVALID_REPORTED_AMOUNT")
        result.append(dict(currency=currency, reported_amount=str(Decimal(amount))))
    return result, blank


async def observe_balance_evidence(
    client,
    *,
    access_token,
    app_key,
    app_secret,
    account,
    now=lambda: datetime.now(UTC),
    max_pages=10,
):
    """Preserve both reporting bases and detect changes between sequential reads.

    The caller supplies the existing rate-limited, bounded-retry broker client.
    No amounts are aggregated, treated as spendable cash, or passed to an executor.
    """
    if type(max_pages) is not int or not 1 <= max_pages <= 20:
        raise AccountReadError("BALANCE_INVALID_PAGE_LIMIT")
    if not isinstance(account, str) or not re.fullmatch(r"[0-9]{10}", account):
        raise AccountReadError("BALANCE_INVALID_ACCOUNT")
    started = _time(now())
    basis_date = started.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
    cano, product = _split_account(account)

    def check_age():
        current = _time(now())
        if not 0 <= (current - started).total_seconds() <= 30:
            raise AccountReadError("BALANCE_STALE_BATCH")
        return current

    async def collect(endpoint):
        params = dict(CANO=cano, ACNT_PRDT_CD=product, WCRC_FRCR_DVSN_CD="02", INQR_DVSN_CD="00")
        if endpoint == CURRENT:
            params.update(NATN_CD="000", TR_MKET_CD="00")
        else:
            params["BASS_DT"] = basis_date
        accumulated, seen = {key: [] for key in OUTPUTS}, set()
        currency_page_digests = []
        for page in range(max_pages):
            check_age()
            headers = _kis_headers(
                access_token=access_token,
                app_key=app_key,
                app_secret=app_secret,
                tr_id="CTRP6504R" if endpoint == CURRENT else "CTRP6010R",
            )
            headers["tr_cont"] = "N" if page else ""
            try:
                response = await client.request(
                    "GET", ROOT + endpoint, headers=headers, params=params
                )
                response.raise_for_status()
                body = response.json()
            except Exception:
                raise AccountReadError("BALANCE_TRANSPORT_OR_JSON_ERROR") from None
            check_age()
            if not isinstance(body, dict) or body.get("rt_cd") != "0":
                raise AccountReadError("BALANCE_BROKER_REJECTED", shape=dict(endpoint=endpoint))
            page_rows = {}
            for key in OUTPUTS:
                rows = body.get(key)
                if isinstance(rows, dict) and rows:
                    rows = [rows]
                if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                    raise AccountReadError(
                        "BALANCE_INVALID_OUTPUT", shape=dict(endpoint=endpoint, output=key)
                    )
                if len(rows) > 1000:
                    raise AccountReadError("BALANCE_OUTPUT_LIMIT")
                page_rows[key] = rows
            digest = hashlib.sha256(json.dumps(page_rows, sort_keys=True).encode()).digest()
            if digest in seen:
                raise AccountReadError("BALANCE_REPEATED_PAGE")
            seen.add(digest)
            # Keep this digest private; even a stable response is not a live valuation timestamp.
            currency_page_digests.append(
                hashlib.sha256(
                    json.dumps(page_rows["output2"], sort_keys=True).encode()
                ).hexdigest()
            )
            for key in OUTPUTS:
                accumulated[key].extend(page_rows[key])
            raw_continuation = response.headers.get("tr_cont")
            continuation = raw_continuation.strip() if raw_continuation is not None else None
            # These endpoints' official clients continue only on M/F. An explicit
            # empty header means no continuation; a missing header is not evidence.
            if continuation not in {"", "D", "E", "M", "F"}:
                raise AccountReadError(
                    "BALANCE_CONTINUATION_HEADER",
                    shape=dict(
                        endpoint=endpoint,
                        continuation_kind="MISSING" if continuation is None else "UNKNOWN",
                    ),
                )
            if continuation in {"M", "F"}:
                continue
            currencies, blank = _currency_rows(accumulated["output2"])
            return dict(
                reporting_basis="current" if endpoint == CURRENT else "settlement",
                output_row_counts={key: len(rows) for key, rows in accumulated.items()},
                currency_rows=currencies,
                blank_currency_rows=blank,
                currency_page_digests=currency_page_digests,
                pagination_complete=True,
                pagination_end="NO_CONTINUATION" if continuation == "" else "EXPLICIT_END",
            )
        raise AccountReadError("BALANCE_PAGE_LIMIT")

    first = await collect(CURRENT)
    settlement = await collect(SETTLED)
    last = await collect(CURRENT)
    completed = check_age()
    stable = first["currency_page_digests"] == last["currency_page_digests"]
    current_usd = [
        row["reported_amount"] for row in last["currency_rows"] if row["currency"] == "USD"
    ]
    settled_usd = [
        row["reported_amount"] for row in settlement["currency_rows"] if row["currency"] == "USD"
    ]
    comparison = "UNAVAILABLE"
    if stable and len(current_usd) == len(settled_usd) == 1:
        comparison = "EQUAL" if Decimal(current_usd[0]) == Decimal(settled_usd[0]) else "DIFFERENT"
    return dict(
        observation_started_at=started.isoformat(),
        observation_completed_at=completed.isoformat(),
        settlement_basis_date=basis_date,
        current_before=first,
        settlement=settlement,
        current_after=last,
        current_read_stable=stable,
        reported_usd_field_comparison=comparison,
        cash_verified=False,
        nav_verified=False,
        full_account_scope_verified=False,
        live_eligible=False,
        orders_submitted=0,
    )


def public_balance_evidence(snapshot):
    """Count-only output: no currency, amounts, holdings, identities, or source digests."""
    return dict(
        schema_version=182,
        status="BALANCE_REPORTS_OBSERVED",
        current_read_stable=snapshot["current_read_stable"],
        reported_usd_field_comparison=snapshot["reported_usd_field_comparison"],
        observations={
            key: dict(
                output_row_counts=snapshot[key]["output_row_counts"],
                blank_currency_rows=snapshot[key]["blank_currency_rows"],
                usd_row_count=sum(
                    row["currency"] == "USD" for row in snapshot[key]["currency_rows"]
                ),
                pagination_complete=snapshot[key]["pagination_complete"],
                pagination_end=snapshot[key]["pagination_end"],
            )
            for key in ("current_before", "settlement", "current_after")
        },
        issues=["REPORTING_BASES_DIFFER", "INTRADAY_REFLECTION_NOT_GUARANTEED", "NAV_UNVERIFIED"],
        cash_verified=False,
        nav_verified=False,
        full_account_scope_verified=False,
        live_eligible=False,
        orders_submitted=0,
    )
