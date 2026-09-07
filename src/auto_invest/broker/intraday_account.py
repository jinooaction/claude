"""Strict GET-only account observations. These do not establish execution NAV."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from auto_invest.broker.overseas import _kis_headers, _split_account

ROOT = "/uapi/overseas-stock/v1/trading/"
ENDPOINTS = {
    "inquire-balance": ("TTTS3012R", "output1", 100),
    "inquire-nccs": ("TTTS3018R", "output", 40),
    "inquire-psamount": ("TTTS3007R", "output", 1),
    "foreign-margin": ("TTTC2101R", "output", 100),
}


class AccountReadError(ValueError):
    """Only closed, locally defined codes, never the broker's free-form error."""

    def __init__(self, code, *, shape=None):
        super().__init__(code)
        self.shape = shape or {}


def _number(row, field, *, whole=False, positive=False):
    value = row.get(field)
    if not isinstance(value, str) or not re.fullmatch(
        r"-?[0-9]{1,18}(\.[0-9]{1,12})?", value.strip()
    ):
        raise AccountReadError("INVALID_" + field.upper())
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise AccountReadError("INVALID_" + field.upper()) from None
    if amount < 0 or (positive and amount == 0) or (whole and amount != amount.to_integral_value()):
        raise AccountReadError("INVALID_" + field.upper())
    return int(amount) if whole else amount


def _identifier(row, field):
    value = row.get(field)
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", value.strip()):
        raise AccountReadError("INVALID_" + field.upper())
    return value.strip()


def _usd_currency(row):
    currency = row.get("tr_crcy_cd", "USD")
    if not isinstance(currency, str) or currency.strip() != "USD":
        raise AccountReadError("NON_USD_ROW")


def _usd(row, endpoint):
    _usd_currency(row)
    market = row.get("ovrs_excg_cd", "NASD")
    # KIS documents NASD as all US markets and NAS as Nasdaq on live accounts.
    if not isinstance(market, str) or market.strip() not in {"NASD", "NAS", "NYSE", "AMEX"}:
        category = "INVALID_TYPE"
        if isinstance(market, str):
            category = market.strip() if market.strip() in {"NYS", "AMS", "SEHK"} else "OTHER"
            if not market.strip():
                category = "EMPTY"
        # An exchange identifier is public protocol metadata, not account data.
        # Publish only a short uppercase code; never arbitrary response text.
        public_code = "REDACTED"
        if isinstance(market, str) and re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", market.strip()):
            public_code = market.strip()
        raise AccountReadError(
            "NON_US_MARKET",
            shape=dict(endpoint=endpoint, market_category=category, market_code=public_code),
        )


async def observe_account(
    client,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    now=lambda: datetime.now(UTC),
    max_pages=20,
):
    """Return segregated observations, not a synthetic whole-account NAV."""
    if type(max_pages) is not int or not 1 <= max_pages <= 100:
        raise AccountReadError("INVALID_PAGE_LIMIT")
    if not isinstance(account, str) or not re.fullmatch(r"[0-9]{10}", account):
        raise AccountReadError("INVALID_ACCOUNT_FORMAT")
    cano, product = _split_account(account)
    started = now()
    if started.tzinfo is None:
        raise AccountReadError("INVALID_OBSERVATION_TIME")

    def check_age():
        elapsed = (now() - started).total_seconds()
        if not 0 <= elapsed <= 30:
            raise AccountReadError("STALE_ACCOUNT_OBSERVATION")

    async def collect(endpoint, **extra):
        tr_id, field, page_size = ENDPOINTS[endpoint]
        paged = endpoint in {"inquire-balance", "inquire-nccs"}
        cursor, seen, rows = ("", ""), set(), []
        for page in range(max_pages if paged else 1):
            check_age()
            headers = _kis_headers(
                access_token=access_token, app_key=app_key, app_secret=app_secret, tr_id=tr_id
            )
            headers["tr_cont"] = "N" if page else ""
            params = dict(CANO=cano, ACNT_PRDT_CD=product, **extra)
            if paged:
                params.update(CTX_AREA_FK200=cursor[0], CTX_AREA_NK200=cursor[1])
            try:
                response = await client.request(
                    "GET", ROOT + endpoint, headers=headers, params=params
                )
                response.raise_for_status()
                body = response.json()
            except Exception:
                raise AccountReadError("ACCOUNT_TRANSPORT_OR_JSON_ERROR") from None
            check_age()
            if not isinstance(body, dict) or body.get("rt_cd") != "0":
                raise AccountReadError("ACCOUNT_BROKER_REJECTED")
            raw = body.get(field)
            if isinstance(raw, dict) and raw:
                raw = [raw]
            if not isinstance(raw, list) or any(not isinstance(row, dict) for row in raw):
                raise AccountReadError("INVALID_" + endpoint.replace("-", "_").upper() + "_ROWS")
            if len(raw) > page_size:
                raise AccountReadError("ACCOUNT_PAGE_SIZE")
            rows.extend(raw)
            continuation = response.headers.get("tr_cont", "").strip()
            if continuation not in {"", "D", "E", "M", "F"}:
                raise AccountReadError("ACCOUNT_CONTINUATION_HEADER")
            if not paged:
                if continuation in {"M", "F"}:
                    raise AccountReadError("ACCOUNT_UNSUPPORTED_CONTINUATION")
                return rows
            keys = ("ctx_area_fk200", "ctx_area_nk200")
            if any(not isinstance(body.get(k), str) for k in keys):
                raise AccountReadError("ACCOUNT_CURSOR_MISSING")
            next_cursor = tuple(body[k] for k in keys)
            # Both official account examples use D/E as terminal; returned search
            # context is not proof of another page. M/F still requires progress.
            if continuation in {"D", "E"}:
                return rows
            has_cursor = any(part.strip() for part in next_cursor)
            if continuation not in {"M", "F"} and not has_cursor:
                return rows
            if not has_cursor or next_cursor == cursor or next_cursor in seen:
                raise AccountReadError(
                    "ACCOUNT_CURSOR_STALLED",
                    shape=dict(
                        endpoint=endpoint,
                        page_number=page + 1,
                        row_count=len(raw),
                        tr_cont=continuation,
                        fk_empty=not next_cursor[0].strip(),
                        nk_empty=not next_cursor[1].strip(),
                        cursor_repeated=next_cursor == cursor or next_cursor in seen,
                    ),
                )
            seen.add(next_cursor)
            cursor = next_cursor
        raise AccountReadError("ACCOUNT_PAGE_LIMIT")

    balance_rows = await collect("inquire-balance", OVRS_EXCG_CD="NASD", TR_CRCY_CD="USD")
    order_rows = await collect("inquire-nccs", OVRS_EXCG_CD="NASD", SORT_SQN="DS")
    cash_rows = await collect(
        "inquire-psamount", OVRS_EXCG_CD="NASD", OVRS_ORD_UNPR="1", ITEM_CD="AAPL"
    )
    margin_rows = await collect("foreign-margin")
    if len(cash_rows) != 1:
        raise AccountReadError("ACCOUNT_PURCHASABLE_ROW_COUNT")
    _usd(cash_rows[0], "inquire-psamount")
    orderable = _number(cash_rows[0], "ovrs_ord_psbl_amt")
    positions, unverified_assets = {}, {}
    for row in balance_rows:
        if isinstance(row.get("ovrs_excg_cd"), str) and row["ovrs_excg_cd"].strip() == "OTCB":
            _usd_currency(row)
            symbol = _identifier(row, "ovrs_pdno")
            if symbol in positions or symbol in unverified_assets:
                raise AccountReadError("DUPLICATE_ACCOUNT_POSITION")
            unverified_assets[symbol] = dict(
                reported_quantity=str(_number(row, "ovrs_cblc_qty")),
                reported_market_code="OTCB",
                reported_valuation_usd=None,
                valuation_verified=False,
                exchange_verified=False,
                tradability_verified=False,
                reason="UNSUPPORTED_EXECUTION_MARKET",
            )
            continue
        _usd(row, "inquire-balance")
        qty = _number(row, "ovrs_cblc_qty", whole=True)
        if not qty:
            continue
        symbol = _identifier(row, "ovrs_pdno")
        if symbol in positions or symbol in unverified_assets:
            raise AccountReadError("DUPLICATE_ACCOUNT_POSITION")
        sellable = _number(row, "ord_psbl_qty", whole=True)
        if sellable > qty:
            raise AccountReadError("SELLABLE_EXCEEDS_HOLDING")
        positions[symbol] = dict(
            quantity=qty,
            sellable_quantity=sellable,
            reported_mark_usd=str(_number(row, "now_pric2", positive=True)),
            reported_valuation_usd=str(_number(row, "ovrs_stck_evlu_amt", positive=True)),
        )
    orders, seen_orders = [], set()
    for row in order_rows:
        _usd(row, "inquire-nccs")
        remaining = _number(row, "nccs_qty", whole=True, positive=True)
        ordered = _number(row, "ft_ord_qty", whole=True, positive=True)
        filled = _number(row, "ft_ccld_qty", whole=True)
        if remaining + filled > ordered or row.get("sll_buy_dvsn_cd") not in {"01", "02"}:
            raise AccountReadError("OPEN_ORDER_QUANTITY_OR_SIDE")
        number = _identifier(row, "odno")
        if number in seen_orders:
            raise AccountReadError("DUPLICATE_OPEN_ORDER")
        seen_orders.add(number)
        orders.append(
            dict(
                order_id=number,
                symbol=_identifier(row, "pdno"),
                side="BUY" if row["sll_buy_dvsn_cd"] == "02" else "SELL",
                remaining_quantity=remaining,
                filled_quantity=filled,
                ordered_quantity=ordered,
            )
        )
    usd_margin = []
    for row in margin_rows:
        currency = row.get("crcy_cd")
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency.strip()):
            raise AccountReadError("INVALID_MARGIN_CURRENCY")
        if currency.strip() == "USD":
            usd_margin.append(row)
    if len(usd_margin) > 1:
        raise AccountReadError("USD_MARGIN_ROW_COUNT", shape=dict(usd_margin_rows=len(usd_margin)))
    cash_components = None
    if usd_margin:
        cash_components = {
            field: str(_number(usd_margin[0], field))
            for field in (
                "frcr_dncl_amt1",
                "ustl_buy_amt",
                "ustl_sll_amt",
                "frcr_rcvb_amt",
                "frcr_mgn_amt",
                "frcr_gnrl_ord_psbl_amt",
            )
        }
    check_age()
    return dict(
        schema_version=182,
        observation_started_at=started.isoformat(),
        observation_completed_at=now().isoformat(),
        account_scope="US_ORDINARY_OVERSEAS_STOCK",
        currency="USD",
        usd_orderable_amount=str(orderable),
        reported_cash_components=cash_components,
        usd_margin_reported=bool(usd_margin),
        positions=positions,
        unverified_assets=unverified_assets,
        open_orders=orders,
        pagination_complete=True,
        nav=None,
        nav_verified=False,
        full_account_scope_verified=False,
        execution_marks_verified=False,
        live_eligible=False,
        orders_submitted=0,
        issues=["USD_NAV_CONTRACT_UNVERIFIED", "FRACTIONAL_AND_OTHER_ACCOUNT_SCOPE_UNVERIFIED"]
        + (["UNSUPPORTED_ACCOUNT_ASSETS_PRESENT"] if unverified_assets else [])
        + ([] if usd_margin else ["USD_MARGIN_COMPONENTS_NOT_REPORTED"]),
    )


def public_contract_result(snapshot):
    """Publish only contract/count facts; no account, position or order identifiers."""
    return dict(
        schema_version=182,
        status=(
            "INTRADAY_ACCOUNT_READ_WITH_UNVERIFIED_ASSETS"
            if snapshot["unverified_assets"]
            else (
                "INTRADAY_ACCOUNT_READ_CONTRACT_OK"
                if snapshot["usd_margin_reported"]
                else "INTRADAY_ACCOUNT_READ_WITH_UNVERIFIED_CASH"
            )
        ),
        position_count=len(snapshot["positions"]),
        unverified_asset_count=len(snapshot["unverified_assets"]),
        usd_margin_reported=snapshot["usd_margin_reported"],
        open_order_count=len(snapshot["open_orders"]),
        pagination_complete=snapshot["pagination_complete"],
        nav_verified=False,
        live_eligible=False,
        orders_submitted=0,
    )
