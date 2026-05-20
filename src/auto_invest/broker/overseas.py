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
TR_ID_PURCHASABLE = "TTTS3007R"
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


async def get_purchasable_cash_usd(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    market: str = "NASD",
) -> Decimal:
    """주문가능 외화 예수금(USD)을 조회.

    해외주식 잔고조회(TTTS3012R)의 output2에는 외화예수금 필드 자체가 없어
    잔고를 0으로 잘못 표시하는 문제가 있었음. KIS는 외화예수금을 별도
    엔드포인트 `inquire-psamount`(TTTS3007R)로 제공한다.

    inquire-psamount는 종목 코드와 단가를 필수로 요구하지만, 응답의
    `ord_psbl_frcr_amt`(주문가능 외화금액)는 종목과 무관하게 계좌의 USD
    예수금을 그대로 반환한다. 따라서 더미 종목(AAPL @ $1)으로 호출해
    외화예수금만 추출한다.
    """
    cano, acnt_prdt = _split_account(account)
    response = await client.request(
        "GET",
        "/uapi/overseas-stock/v1/trading/inquire-psamount",
        headers=_kis_headers(
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            tr_id=TR_ID_PURCHASABLE,
        ),
        params={
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt,
            "OVRS_EXCG_CD": market,
            "OVRS_ORD_UNPR": "1",
            "ITEM_CD": "AAPL",
        },
    )
    body = response.json().get("output", {})
    # KIS 응답 후보 필드명 — 시점/모의/실전에 따라 키가 다를 수 있어 순차 시도.
    cash_str = (
        body.get("ord_psbl_frcr_amt")
        or body.get("frcr_ord_psbl_amt1")
        or body.get("frcr_dncl_amt1")
        or "0"
    )
    return Decimal(str(cash_str))


def _coerce_summary(raw: object) -> dict:
    """KIS는 output2를 dict로도 list[dict]로도 반환할 수 있어 둘 다 처리."""
    if isinstance(raw, list):
        return raw[0] if raw else {}
    if isinstance(raw, dict):
        return raw
    return {}


def _row_eval_amount_usd(row: dict) -> Decimal:
    """보유 종목 row의 외화 평가금액(USD)을 추출."""
    val = (
        row.get("frcr_evlu_amt2")
        or row.get("ovrs_stck_evlu_amt")
        or row.get("evlu_amt")
    )
    if val:
        return Decimal(str(val))
    # 평가금액 필드가 없으면 수량 * 현재가로 추정.
    qty = int(row.get("ovrs_cblc_qty", 0) or 0)
    price = row.get("now_pric2") or row.get("ovrs_now_pric1") or "0"
    return Decimal(qty) * Decimal(str(price))


async def get_balance(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    market: str = "NASD",
) -> BalanceSnapshot:
    """USD 예수금 + 총 평가금액(예수금 + 보유 종목 평가금액)을 조회.

    KIS 해외주식 잔고조회(TTTS3012R)는 보유 종목별 평가금액(output1)을
    반환하지만 외화예수금(cash) 필드는 포함하지 않으므로, 별도
    `get_purchasable_cash_usd`를 호출해 cash를 얻고 inquire-balance에서
    보유 종목 평가금액을 합산해 총 평가금액을 계산한다.
    """
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
    body = response.json()
    rows = body.get("output1", []) or []
    holdings_value = sum(
        (_row_eval_amount_usd(row) for row in rows if int(row.get("ovrs_cblc_qty", 0) or 0) > 0),
        Decimal("0"),
    )

    cash = await get_purchasable_cash_usd(
        client,
        access_token=access_token,
        app_key=app_key,
        app_secret=app_secret,
        account=account,
        market=market,
    )

    return BalanceSnapshot(
        account=account,
        cash_usd=cash,
        total_value_usd=cash + holdings_value,
        fetched_at_utc=datetime.now(UTC),
    )
