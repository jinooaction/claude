"""KIS overseas-equity REST endpoint wrappers.

The v1 surface exposed to the rest of the worker:

  - `get_quote(symbol)`         -> Quote
  - `place_order(req)`          -> OrderResult
  - `cancel_order(kis_order_id)`-> None
  - `get_positions(account)`    -> tuple[PositionSnapshot, ...]
  - `get_balance(account)`      -> BalanceSnapshot

These functions encode KIS's documented field names (CANO, ACNT_PRDT_CD,
ORD_QTY, ODNO, etc.) verbatim. The optional live smoke test (T064)
exercises the same shapes against the real broker so any drift
surfaces explicitly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from auto_invest.broker.client import ResilientClient
from auto_invest.broker.models import (
    BalanceSnapshot,
    OrderRequest,
    OrderResult,
    PositionSnapshot,
    Quote,
)

# KIS Developers TR_IDs (real-account, overseas-equity v1 endpoints).
TR_ID_QUOTE = "HHDFS00000300"
TR_ID_BALANCE = "TTTS3012R"
TR_ID_BUY = "TTTT1002U"
TR_ID_SELL = "TTTT1006U"
TR_ID_CANCEL = "TTTT1004U"


def _split_account(combined: str) -> tuple[str, str]:
    """Split CANO (first N) | ACNT_PRDT_CD (last 2) from the operator's account string."""
    if len(combined) < 10:
        raise ValueError(
            "KIS_ACCOUNT_NO must be at least 10 chars (CANO + 2-digit product code); "
            f"got {len(combined)} chars"
        )
    return combined[:-2], combined[-2:]


def _kis_headers(
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    tr_id: str,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    headers = {
        "authorization": f"Bearer {access_token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
    }
    if extra:
        headers.update(extra)
    return headers


async def get_quote(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    symbol: str,
    market: str = "NAS",
) -> Quote:
    """Fetch the most recent quote for an overseas-listed symbol."""
    response = await client.request(
        "GET",
        "/uapi/overseas-price/v1/quotations/price",
        headers=_kis_headers(
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            tr_id=TR_ID_QUOTE,
        ),
        params={"AUTH": "", "EXCD": market, "SYMB": symbol},
    )
    body = response.json()["output"]
    return Quote(
        symbol=symbol,
        last_price_usd=Decimal(str(body["last"])),
        bid_usd=Decimal(str(body["bidp"])) if body.get("bidp") else None,
        ask_usd=Decimal(str(body["askp"])) if body.get("askp") else None,
        quoted_at_utc=datetime.now(UTC),
    )


async def place_order(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    request: OrderRequest,
    market: str = "NASD",
) -> OrderResult:
    """Submit an overseas order. Returns the broker-assigned order id."""
    cano, acnt_prdt = _split_account(request.account)
    tr_id = TR_ID_BUY if request.side.value == "BUY" else TR_ID_SELL
    response = await client.request(
        "POST",
        "/uapi/overseas-stock/v1/trading/order",
        headers=_kis_headers(
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            tr_id=tr_id,
            extra={"content-type": "application/json"},
        ),
        json={
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt,
            "OVRS_EXCG_CD": market,
            "PDNO": request.symbol,
            "ORD_QTY": str(request.qty),
            "OVRS_ORD_UNPR": (
                str(request.limit_price_usd) if request.limit_price_usd is not None else "0"
            ),
            "ORD_DVSN": "00" if request.order_type.value == "LIMIT" else "01",
        },
    )
    body = response.json()["output"]
    return OrderResult(
        kis_order_id=body["ODNO"],
        accepted_at_utc=datetime.now(UTC),
    )


async def cancel_order(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    kis_order_id: str,
    market: str = "NASD",
) -> None:
    """Cancel an open KIS order by id."""
    cano, acnt_prdt = _split_account(account)
    await client.request(
        "POST",
        "/uapi/overseas-stock/v1/trading/order-rvsecncl",
        headers=_kis_headers(
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            tr_id=TR_ID_CANCEL,
            extra={"content-type": "application/json"},
        ),
        json={
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt,
            "OVRS_EXCG_CD": market,
            "ORGN_ODNO": kis_order_id,
            "RVSE_CNCL_DVSN_CD": "02",  # 02 = cancel; 01 = modify
            "ORD_QTY": "0",
            "OVRS_ORD_UNPR": "0",
            "MGCO_APTM_ODNO": "",
        },
    )


async def get_positions(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    market: str = "NASD",
) -> tuple[PositionSnapshot, ...]:
    """Fetch current overseas-equity holdings for the account."""
    cano, acnt_prdt = _split_account(account)
    response = await client.request(
        "GET",
        "/uapi/overseas-stock/v1/trading/inquire-balance",
        headers=_kis_headers(
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            tr_id=TR_ID_BALANCE,
        ),
        params={
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt,
            "OVRS_EXCG_CD": market,
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        },
    )
    rows = response.json().get("output1", [])
    return tuple(
        PositionSnapshot(
            symbol=row["ovrs_pdno"],
            qty=int(row["ovrs_cblc_qty"]),
            avg_cost_usd=Decimal(str(row["pchs_avg_pric"])),
        )
        for row in rows
        if int(row.get("ovrs_cblc_qty", 0)) > 0
    )


async def get_balance(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    market: str = "NASD",
) -> BalanceSnapshot:
    """Fetch USD cash balance and total account value."""
    cano, acnt_prdt = _split_account(account)
    response = await client.request(
        "GET",
        "/uapi/overseas-stock/v1/trading/inquire-balance",
        headers=_kis_headers(
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            tr_id=TR_ID_BALANCE,
        ),
        params={
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt,
            "OVRS_EXCG_CD": market,
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        },
    )
    summary = response.json().get("output2", {})
    return BalanceSnapshot(
        account=account,
        cash_usd=Decimal(str(summary.get("frcr_dncl_amt_2", "0"))),
        total_value_usd=Decimal(str(summary.get("tot_evlu_pfls_amt", "0"))),
        fetched_at_utc=datetime.now(UTC),
    )
