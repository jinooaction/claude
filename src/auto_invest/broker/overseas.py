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

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from auto_invest.broker.client import ResilientClient
from auto_invest.broker.diagnostics import (
    KisOrderError,
    diagnostics_from_exception,
    diagnostics_from_response,
)
from auto_invest.broker.models import (
    BalanceSnapshot,
    BrokerExecution,
    OrderRequest,
    OrderResult,
    PositionSnapshot,
    Quote,
)
from auto_invest.config.enums import OrderType, Side

# KIS Developers TR_IDs (real-account, overseas-equity v1 endpoints).
TR_ID_QUOTE = "HHDFS00000300"
TR_ID_BALANCE = "TTTS3012R"
TR_ID_PURCHASABLE = "TTTS3007R"
TR_ID_BUY = "TTTT1002U"
TR_ID_SELL = "TTTT1006U"
TR_ID_CANCEL = "TTTT1004U"
TR_ID_EXECUTIONS = "TTTS3035R"  # 해외주식 주문체결내역 (inquire-ccnl)
TR_ID_DAILY_PRICE = "HHDFS76240000"  # 해외주식 기간별시세 (daily/weekly/monthly OHLCV)


@dataclass(frozen=True)
class OverseasDailyBar:
    """One daily OHLCV bar parsed from KIS 해외주식 기간별시세 (read-only market data)."""

    symbol: str
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


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


class QuoteUnavailable(RuntimeError):
    """KIS returned no usable last price for a symbol (blank/garbage field).

    Raised by `get_quote` so callers can skip the symbol with an actionable,
    symbol-tagged message instead of an opaque `decimal.InvalidOperation`.
    """


def _opt_price(raw: object) -> Decimal | None:
    """Parse an optional KIS price field; blank or non-numeric → None.

    KIS intermittently returns empty strings (e.g. ``"bidp": ""``) or, rarely,
    non-numeric junk for price fields when there is no recent trade or a data
    gap. Mirror the tolerant parsing already used by `_parse_daily_bars`.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


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
    last = _opt_price(body.get("last"))
    if last is None or last <= 0:
        raise QuoteUnavailable(
            f"{symbol}: KIS returned no usable last price (got {body.get('last')!r})"
        )
    return Quote(
        symbol=symbol,
        last_price_usd=last,
        bid_usd=_opt_price(body.get("bidp")),
        ask_usd=_opt_price(body.get("askp")),
        quoted_at_utc=datetime.now(UTC),
        resolved_market=market,
    )


# KIS 시세(EXCD)는 거래소별로 분리돼 있다. 같은 미국 ETF 라도 SPY·GLD 는 나스닥이 아니라
# NYSE Arca/AMEX("AMS")에 상장돼 있어, 고정 EXCD 하나로는 일부 심볼이 조용히 빈 값(QuoteUnavailable)
# 으로 실패한다. backfill_daily_bars 가 일봉에서 쓰는 것과 동일한 순서로 거래소를 시도한다.
QUOTE_EXCHANGES: tuple[str, ...] = ("NAS", "NYS", "AMS")


async def get_quote_resolving_market(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    symbol: str,
    markets: tuple[str, ...] = QUOTE_EXCHANGES,
) -> Quote:
    """Fetch a quote, trying each KIS EXCD until one returns a usable last price.

    KIS 시세는 거래소(EXCD) 범위로 조회된다 — 심볼이 상장되지 않은 거래소로 물으면 ``last``
    가 빈 값으로 와 `get_quote` 가 `QuoteUnavailable` 을 던진다. SPY·GLD 같은 미국 ETF 는
    나스닥이 아니라 NYSE Arca/AMEX("AMS")에 상장돼 있어 고정 ``market="NAS"`` 로는 조용히
    실패한다(검증된 글로벌 분산 추세 포트폴리오가 forward 페이퍼에서 NAV 를 못 쌓던 실제
    원인). 이 함수는 `backfill_daily_bars` 의 거래소 순차 탐색과 같은 방식으로 거래소를 자동
    해석해 심볼별 거래소를 하드코딩할 필요를 없앤다. 모든 거래소에서 빈 값이면 마지막
    `QuoteUnavailable` 을 그대로 전파한다(호출자가 그 종목을 건너뛸 수 있게). KIS 가 미상장
    거래소 조회에 빈 값 대신 5xx를 돌려주는 경우에는 다음 거래소를 계속 읽되, 어느 거래소도
    성공하지 않으면 마지막 5xx를 다시 던져 실제 중개사 장애를 숨기지 않는다.
    """
    last_exc: QuoteUnavailable | None = None
    last_http_exc: httpx.HTTPStatusError | None = None
    for excd in markets:
        try:
            return await get_quote(
                client,
                access_token=access_token,
                app_key=app_key,
                app_secret=app_secret,
                symbol=symbol,
                market=excd,
            )
        except QuoteUnavailable as exc:
            last_exc = exc
        except httpx.HTTPStatusError as exc:
            if 500 <= exc.response.status_code < 600:
                last_http_exc = exc
                continue
            raise
    if last_http_exc is not None:
        raise last_http_exc
    raise last_exc or QuoteUnavailable(
        f"{symbol}: KIS returned no usable last price on any of {markets}"
    )


# KIS 시세(EXCD)와 주문(OVRS_EXCG_CD)은 *별개의 거래소 코드 체계*다.
#   시세 조회 EXCD : NAS(나스닥) / NYS(뉴욕증권거래소) / AMS(NYSE Arca·AMEX)
#   주문 OVRS_EXCG_CD: NASD       / NYSE              / AMEX
# 시세 해석기(get_quote_resolving_market)가 *실제로* 어느 거래소에서 시세를 받았는지
# (Quote.resolved_market) 알아내므로, 그 값을 그대로 주문 거래소로 옮기면 SPY·GLD(AMS→AMEX)·
# IEF(NAS→NASD) 처럼 거래소가 섞인 유니버스도 종목별로 올바르게 라우팅된다 — 심볼별 거래소
# 하드코딩이 필요 없다(시세 자동 해석과 동일 원칙). 시세 버그(2026-06-10)의 주문측 대칭 수정.
QUOTE_TO_ORDER_EXCHANGE: dict[str, str] = {"NAS": "NASD", "NYS": "NYSE", "AMS": "AMEX"}


def order_exchange_for_quote_market(excd: str | None) -> str | None:
    """KIS 시세 거래소(EXCD) → 해외주식 주문 거래소(OVRS_EXCG_CD) 변환.

    `Quote.resolved_market`(시세를 실제로 받은 거래소)을 주문 경로의 `OVRS_EXCG_CD` 로
    옮긴다. 매핑에 없거나 ``None`` 이면 ``None`` 을 돌려 호출자가 설정된 기본 주문 거래소로
    폴백하게 한다(단일 거래소 룰 워커는 영향 없음 — 회귀 0).
    """
    if excd is None:
        return None
    return QUOTE_TO_ORDER_EXCHANGE.get(excd.strip().upper())


# 되돌림 읽기 경로(체결·보유·잔고)용 미국 해외주식 거래소 집합 — 주문 OVRS_EXCG_CD 와 같은
# 코드 체계(NASD/NYSE/AMEX). 검증된 멀티에셋 유니버스는 거래소가 섞인다(SPY·GLD=AMEX,
# IEF=NASD). 주문은 종목별 거래소로 나가는데(시세→주문 거래소 자동 해석, 2026-06-10) 체결·
# 보유 *조회* 는 단일 거래소(OVRS_EXCG_CD=NASD)만 보던 대칭 잠복 버그가 있었다 — 그러면 다른
# 거래소 종목(SPY·GLD)의 체결이 동기화 안 되고(→ 로컬 보유 0 → 리밸런서 과매수, 손실 서킷
# 브레이커가 노출을 못 봄) 잔고 정합성이 그 종목을 'ledger_only' 로 오인(→ 허위 drift/halt)했다.
# 이 집합을 전부 훑어 합치되 종목/주문번호로 중복 제거하면, KIS 가 OVRS_EXCG_CD 로 거래소를
# 엄격히 필터하든(각 거래소 자기 것만 반환) 단일값에 전부 반환하든 *양쪽에서* 정확하다 —
# 중복 제거가 멱등성·이중계상 방지를 보장한다(되돌림 경로의 거래소 자동 해석).
US_ORDER_EXCHANGES: tuple[str, ...] = tuple(dict.fromkeys(QUOTE_TO_ORDER_EXCHANGE.values()))


def _parse_daily_bars(rows: list[dict], symbol: str) -> list[OverseasDailyBar]:
    """Parse KIS 기간별시세 output2 rows into ascending-date OHLCV bars.

    KIS field names (verbatim): ``xymd`` (YYYYMMDD), ``open``/``high``/``low``,
    ``clos`` (close), ``tvol`` (volume). Rows that are unparseable, non-positive,
    or duplicate-dated are skipped; low/high are clamped to stay consistent with
    open/close so downstream OHLCV validation never rejects a real bar.
    """
    bars: list[OverseasDailyBar] = []
    seen: set[date] = set()
    for r in rows:
        xymd = str(r.get("xymd", "")).strip()
        if len(xymd) != 8 or not xymd.isdigit():
            continue
        try:
            d = date(int(xymd[:4]), int(xymd[4:6]), int(xymd[6:8]))
            o = Decimal(str(r["open"]))
            h = Decimal(str(r["high"]))
            lo = Decimal(str(r["low"]))
            c = Decimal(str(r["clos"]))
            v = int(float(str(r.get("tvol", "0")).strip() or "0"))
        except (KeyError, ValueError, InvalidOperation):
            continue
        if min(o, h, lo, c) <= 0 or v < 0 or d in seen:
            continue
        seen.add(d)
        lo_adj = min(lo, o, c)
        hi_adj = max(h, o, c)
        bars.append(OverseasDailyBar(symbol, d, o, hi_adj, lo_adj, c, v))
    bars.sort(key=lambda b: b.session_date)
    return bars


async def get_daily_bars(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    symbol: str,
    market: str = "NAS",
    adjusted: bool = True,
    base_date: str = "",
) -> list[OverseasDailyBar]:
    """Fetch recent daily OHLCV bars for an overseas symbol (read-only; no orders).

    Returns the window KIS provides (~100 sessions) ending at/before ``base_date``
    in ascending date order. ``base_date`` is the KIS BYMD (YYYYMMDD); empty = most
    recent. Paginate deeper history by re-calling with an earlier ``base_date`` (스펙
    041 — `backfill_daily_bars(min_bars=…)` does this). ``market`` is the KIS EXCD
    (NAS/NYS/AMS); an empty result usually means the symbol is on a different EXCD.
    """
    response = await client.request(
        "GET",
        "/uapi/overseas-price/v1/quotations/dailyprice",
        headers=_kis_headers(
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            tr_id=TR_ID_DAILY_PRICE,
        ),
        params={
            "AUTH": "",
            "EXCD": market,
            "SYMB": symbol,
            "GUBN": "0",  # 0=daily, 1=weekly, 2=monthly
            "BYMD": base_date,  # base date (YYYYMMDD); empty = most recent
            "MODP": "1" if adjusted else "0",  # split/dividend-adjusted close
        },
    )
    body = response.json()
    rows = body.get("output2") or []
    return _parse_daily_bars(rows, symbol)


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
    endpoint = "/uapi/overseas-stock/v1/trading/order"
    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt,
        "OVRS_EXCG_CD": market,
        "PDNO": request.symbol,
        "ORD_QTY": str(request.qty),
        "OVRS_ORD_UNPR": (
            str(request.limit_price_usd) if request.limit_price_usd is not None else "0"
        ),
        "CTAC_TLNO": "",
        "MGCO_APTM_ODNO": "",
        "SLL_TYPE": "" if request.side.value == "BUY" else "00",
        "ORD_SVR_DVSN_CD": "0",
        "ORD_DVSN": "00" if request.order_type.value == "LIMIT" else "01",
    }
    request_summary = {
        "method": "POST",
        "endpoint": endpoint,
        "tr_id": tr_id,
        "body": body,
    }
    try:
        response = await client.request(
            "POST",
            endpoint,
            retry_transient=False,
            headers=_kis_headers(
                access_token=access_token,
                app_key=app_key,
                app_secret=app_secret,
                tr_id=tr_id,
                extra={"content-type": "application/json"},
            ),
            json=body,
        )
    except Exception as exc:
        diagnostics = diagnostics_from_exception(
            exc,
            request_summary=request_summary,
        )
        raise KisOrderError("KIS order request failed", diagnostics=diagnostics) from exc

    try:
        response_body = response.json()
    except ValueError as exc:
        diagnostics = diagnostics_from_response(
            response,
            request_summary=request_summary,
            message=str(exc),
            exception_type=type(exc).__name__,
        )
        raise KisOrderError("KIS order response was not JSON", diagnostics=diagnostics) from exc

    output = response_body.get("output") if isinstance(response_body, dict) else None
    order_id = output.get("ODNO") if isinstance(output, dict) else None
    rt_cd = response_body.get("rt_cd") if isinstance(response_body, dict) else None
    if rt_cd not in (None, "", "0") or not order_id:
        diagnostics = diagnostics_from_response(
            response,
            request_summary=request_summary,
            message="KIS order response missing accepted order id",
            exception_type="KisOrderResponseError",
        )
        raise KisOrderError("KIS order response missing output", diagnostics=diagnostics)

    return OrderResult(
        kis_order_id=str(order_id),
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


async def _inquire_balance_output1(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    market: str,
) -> list[dict]:
    """해외주식 잔고조회(inquire-balance, TTTS3012R) output1(보유 종목 row) 을 반환.

    `get_positions`/`get_balance` 와 그 거래소 스윕 변형이 공유하는 저수준 조회(읽기 전용,
    주문/취소 안 함)."""
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
    return response.json().get("output1", []) or []


def _parse_positions(rows: list[dict]) -> tuple[PositionSnapshot, ...]:
    """잔고조회 output1 row → PositionSnapshot(보유수량>0 만)."""
    return tuple(
        PositionSnapshot(
            symbol=row["ovrs_pdno"],
            qty=int(row["ovrs_cblc_qty"]),
            avg_cost_usd=Decimal(str(row["pchs_avg_pric"])),
        )
        for row in rows
        if int(row.get("ovrs_cblc_qty", 0)) > 0
    )


def _dedup_balance_rows(rows: list[dict]) -> list[dict]:
    """여러 거래소에서 모은 잔고 row 를 종목(ovrs_pdno)별로 중복 제거(첫 등장 유지).

    한 종목은 한 거래소에 상장돼 거래소별 조회는 자기 것만 반환한다(중복 없음). 그러나 KIS 가
    단일 OVRS_EXCG_CD 값에 계좌의 전 거래소 보유를 반환하는 구현이라면 같은 종목이 여러 번
    들어올 수 있다 — 그대로 합치면 보유·평가금액이 이중계상되므로 종목별 한 row 만 남긴다
    (스윕이 어느 KIS 동작에서도 정확하도록)."""
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        sym = str(row.get("ovrs_pdno", "")).strip()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(row)
    return out


def _holdings_value_usd(rows: list[dict]) -> Decimal:
    """보유 종목 row 들의 외화 평가금액(USD) 합(보유수량>0 만)."""
    return sum(
        (_row_eval_amount_usd(row) for row in rows if int(row.get("ovrs_cblc_qty", 0) or 0) > 0),
        Decimal("0"),
    )


def _position_marks_usd(rows: list[dict]) -> dict[str, Decimal]:
    """Broker balance valuation rows -> per-share marks for positive holdings."""
    marks: dict[str, Decimal] = {}
    for row in _dedup_balance_rows(rows):
        symbol = str(row.get("ovrs_pdno", "")).strip()
        qty = int(row.get("ovrs_cblc_qty", 0) or 0)
        if not symbol or qty <= 0:
            continue
        evaluation = _row_eval_amount_usd(row)
        if evaluation > 0:
            marks[symbol] = evaluation / Decimal(qty)
    return marks


async def get_positions(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    market: str = "NASD",
) -> tuple[PositionSnapshot, ...]:
    """Fetch current overseas-equity holdings for the account (single exchange)."""
    rows = await _inquire_balance_output1(
        client,
        access_token=access_token,
        app_key=app_key,
        app_secret=app_secret,
        account=account,
        market=market,
    )
    return _parse_positions(rows)


async def get_position_marks_resolving_market(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    markets: Sequence[str] = US_ORDER_EXCHANGES,
) -> dict[str, Decimal]:
    """Read authoritative per-share marks from KIS balance valuations.

    This is a fallback for holdings whose standalone quote lookup is unavailable.
    It performs no order or cancel operation and ignores zero/non-positive values.
    """
    rows: list[dict] = []
    for market in markets:
        rows.extend(
            await _inquire_balance_output1(
                client,
                access_token=access_token,
                app_key=app_key,
                app_secret=app_secret,
                account=account,
                market=market,
            )
        )
    return _position_marks_usd(rows)


async def get_positions_resolving_market(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    markets: Sequence[str] = US_ORDER_EXCHANGES,
) -> tuple[PositionSnapshot, ...]:
    """계좌의 해외주식 보유를 *여러 거래소* 에 걸쳐 합쳐 조회(종목별 중복 제거).

    멀티에셋 유니버스(SPY·GLD=AMEX, IEF=NASD)는 거래소가 섞여, 단일 거래소 조회로는 다른
    거래소 종목의 보유가 통째로 빠진다(→ 정합성에서 'ledger_only' 오인 → 허위 halt). 각
    거래소를 조회해 row 를 모으고 종목별 중복 제거 후 파싱한다. 거래소별 조회 오류는 전파한다
    (fail-closed — 불완전한 보유로 정합성/NAV 를 판단하지 않고 호출자가 다음 라운드에 재시도)."""
    rows: list[dict] = []
    for market in markets:
        rows.extend(
            await _inquire_balance_output1(
                client,
                access_token=access_token,
                app_key=app_key,
                app_secret=app_secret,
                account=account,
                market=market,
            )
        )
    return _parse_positions(_dedup_balance_rows(rows))


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
    보유 종목 평가금액을 합산해 총 평가금액을 계산한다(single exchange).
    """
    rows = await _inquire_balance_output1(
        client,
        access_token=access_token,
        app_key=app_key,
        app_secret=app_secret,
        account=account,
        market=market,
    )
    holdings_value = _holdings_value_usd(rows)

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


async def get_balance_resolving_market(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    markets: Sequence[str] = US_ORDER_EXCHANGES,
) -> BalanceSnapshot:
    """USD 예수금 + 총 평가금액을 *여러 거래소* 보유를 합쳐 조회(종목별 중복 제거).

    `get_balance` 의 거래소 스윕 변형 — 멀티에셋 유니버스에서 다른 거래소 종목(SPY·GLD=AMEX)의
    평가금액이 NAV·정합성에서 누락되지 않게 한다. 보유 평가금액은 거래소별 row 를 모아 종목별
    중복 제거 후 합산하고, 외화예수금(cash)은 거래소와 무관하므로 한 번만 조회한다. 거래소별
    조회 오류는 전파한다(fail-closed)."""
    rows: list[dict] = []
    for market in markets:
        rows.extend(
            await _inquire_balance_output1(
                client,
                access_token=access_token,
                app_key=app_key,
                app_secret=app_secret,
                account=account,
                market=market,
            )
        )
    holdings_value = _holdings_value_usd(_dedup_balance_rows(rows))

    cash = await get_purchasable_cash_usd(
        client,
        access_token=access_token,
        app_key=app_key,
        app_secret=app_secret,
        account=account,
        market=markets[0],  # 외화예수금은 거래소 무관(더미 종목으로 계좌 USD 예수금만 추출)
    )

    return BalanceSnapshot(
        account=account,
        cash_usd=cash,
        total_value_usd=cash + holdings_value,
        fetched_at_utc=datetime.now(UTC),
    )


# ----------------------------------------------------------- order executions


def _first_str(row: dict, *keys: str) -> str | None:
    """후보 키를 순서대로 시도해 비어있지 않은 첫 문자열을 반환. spec 015.

    KIS 체결조회 응답 필드명은 실전/모의·시점에 따라 다를 수 있어, 잔고조회의
    `_row_eval_amount_usd`와 같은 폴백 전략을 쓴다."""
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return str(v)
    return None


def _to_int(text: str | None) -> int:
    if text is None:
        return 0
    try:
        return int(Decimal(text))
    except (ArithmeticError, ValueError):
        return 0


def _exec_side(row: dict) -> Side | None:
    """KIS sll_buy_dvsn_cd: 01=매도(SELL), 02=매수(BUY). 모르면 None."""
    code = _first_str(row, "sll_buy_dvsn_cd", "SLL_BUY_DVSN_CD")
    if code == "01":
        return Side.SELL
    if code == "02":
        return Side.BUY
    return None


def _exec_order_type(row: dict) -> OrderType | None:
    """Parse KIS order-type fields: 00/LIMIT=limit, 01/MARKET=market."""
    raw = _first_str(
        row,
        "ord_dvsn",
        "ORD_DVSN",
        "ord_dvsn_cd",
        "ORD_DVSN_CD",
        "ord_dvsn_name",
        "ORD_DVSN_NAME",
    )
    if raw is None:
        return None
    value = raw.strip().upper()
    if value in {"00", "0", "LIMIT", "LMT"} or "지정" in raw:
        return OrderType.LIMIT
    if value in {"01", "1", "MARKET", "MKT"} or "시장" in raw:
        return OrderType.MARKET
    return None


def _exec_order_price(row: dict) -> Decimal | None:
    price = _opt_price(
        _first_str(
            row,
            "ord_unpr",
            "ORD_UNPR",
            "ovrs_ord_unpr",
            "OVRS_ORD_UNPR",
            "ft_ord_unpr3",
            "FT_ORD_UNPR3",
        )
    )
    if price is None or price <= 0:
        return None
    return price


def _exec_ordered_at_utc(row: dict) -> datetime | None:
    raw_date = _first_str(row, "ord_dt", "ORD_DT")
    raw_time = _first_str(row, "ord_tmd", "ORD_TMD", "ord_time", "ORD_TIME")
    if raw_date is None or raw_time is None:
        return None
    date_part = "".join(ch for ch in raw_date if ch.isdigit())
    time_part = "".join(ch for ch in raw_time if ch.isdigit())
    if len(date_part) != 8 or len(time_part) < 6:
        return None
    try:
        return datetime(
            int(date_part[:4]),
            int(date_part[4:6]),
            int(date_part[6:8]),
            int(time_part[:2]),
            int(time_part[2:4]),
            int(time_part[4:6]),
            tzinfo=UTC,
        )
    except ValueError:
        return None


_TERMINAL_MARKERS = ("취소", "거부", "거절", "만료", "cancel", "reject", "expire")


def _exec_terminal(row: dict) -> bool:
    """브로커가 주문을 더 이상 열려 있지 않다고 **명시적으로** 보고하는지.

    처리상태/주문상태 이름 필드에 취소·거부·만료 표식이 있을 때만 True.
    미체결 수량이 남아있다는 사실만으로는 종료로 보지 않는다(보수적)."""
    status = _first_str(row, "prcs_stat_name", "ord_stat_name", "rvse_cncl_dvsn_name")
    if not status:
        return False
    low = status.lower()
    return any(m in status or m in low for m in _TERMINAL_MARKERS)


def _parse_executions(rows: list[dict]) -> list[BrokerExecution]:
    """체결조회 row들을 주문번호(odno)별로 합산해 정규화한다.

    한 주문에 여러 row(부분체결 누적)가 와도 누적 체결량 + 가중평균 체결가로
    합산한다. KIS가 보통 주문당 한 row(누적)를 주므로 단일 row도 자연히 처리된다."""
    by_order: dict[str, dict] = {}
    for row in rows:
        odno = _first_str(row, "odno", "ODNO", "orgn_odno")
        if not odno:
            continue
        symbol = _first_str(row, "pdno", "PDNO", "ovrs_pdno") or ""
        filled = _to_int(_first_str(row, "ft_ccld_qty", "ccld_qty", "tot_ccld_qty"))
        unfilled_str = _first_str(row, "nccs_qty", "ord_psbl_qty")
        price_str = _first_str(
            row, "ft_ccld_unpr3", "avg_prvs", "ft_ccld_unpr", "ccld_unpr", "ovrs_ccld_unpr"
        )
        price = Decimal(price_str) if price_str else Decimal("0")
        side = _exec_side(row)
        terminal = _exec_terminal(row)
        order_type = _exec_order_type(row)
        order_price = _exec_order_price(row)
        ordered_at = _exec_ordered_at_utc(row)

        agg = by_order.setdefault(
            odno,
            {
                "symbol": symbol,
                "filled": 0,
                "px_qty": Decimal("0"),
                "unfilled": None,
                "side": None,
                "terminal": False,
                "order_type": None,
                "order_price": None,
                "ordered_at": None,
            },
        )
        if symbol and not agg["symbol"]:
            agg["symbol"] = symbol
        agg["filled"] += filled
        agg["px_qty"] += price * Decimal(filled)
        if unfilled_str is not None:
            agg["unfilled"] = _to_int(unfilled_str)
        if side is not None:
            agg["side"] = side
        agg["terminal"] = agg["terminal"] or terminal
        if order_type is not None:
            agg["order_type"] = order_type
        if order_price is not None:
            agg["order_price"] = order_price
        if ordered_at is not None:
            agg["ordered_at"] = ordered_at

    executions: list[BrokerExecution] = []
    for odno, agg in by_order.items():
        filled = agg["filled"]
        avg_price = (agg["px_qty"] / Decimal(filled)) if filled > 0 else Decimal("0")
        executions.append(
            BrokerExecution(
                kis_order_id=odno,
                symbol=agg["symbol"],
                filled_qty=filled,
                avg_fill_price_usd=avg_price,
                unfilled_qty=agg["unfilled"],
                side=agg["side"],
                terminal=agg["terminal"],
                order_type=agg["order_type"],
                order_price_usd=agg["order_price"],
                ordered_at_utc=agg["ordered_at"],
            )
        )
    return executions


async def get_order_executions(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    order_date_yyyymmdd: str,
    end_date_yyyymmdd: str | None = None,
    market: str = "NASD",
) -> list[BrokerExecution]:
    """해외주식 주문체결내역(inquire-ccnl)을 조회해 정규화된 체결 상태 목록을 반환.

    읽기 전용(GET). 체결·미체결 모두(CCLD_NCCS_DVSN='00') 가져와 부분체결과 종료
    여부를 함께 파악한다. 주문을 내거나 취소하지 않는다(spec 015 FR-001)."""
    end_date = end_date_yyyymmdd or order_date_yyyymmdd
    try:
        start_value = datetime.strptime(order_date_yyyymmdd, "%Y%m%d").date()
        end_value = datetime.strptime(end_date, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError("order dates must use valid YYYYMMDD values") from exc
    if end_value < start_value:
        raise ValueError("end_date_yyyymmdd must be on or after order_date_yyyymmdd")

    cano, acnt_prdt = _split_account(account)
    response = await client.request(
        "GET",
        "/uapi/overseas-stock/v1/trading/inquire-ccnl",
        headers=_kis_headers(
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            tr_id=TR_ID_EXECUTIONS,
        ),
        params={
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt,
            "OVRS_EXCG_CD": market,
            "PDNO": "%",
            "ORD_STRT_DT": order_date_yyyymmdd,
            "ORD_END_DT": end_date,
            "SLL_BUY_DVSN": "00",
            "CCLD_NCCS_DVSN": "00",
            "SORT_SQN_DVSN": "00",
            "ORD_DT": "",
            "ODNO": "",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        },
    )
    body = response.json()
    rows = body.get("output") or body.get("output1") or []
    if isinstance(rows, dict):
        rows = [rows]
    return [ex.model_copy(update={"market": market}) for ex in _parse_executions(rows)]


def _merge_executions(
    per_market: list[list[BrokerExecution]],
) -> list[BrokerExecution]:
    """여러 거래소에서 모은 체결 내역을 주문번호(kis_order_id)별로 중복 제거해 합친다.

    한 주문은 한 거래소에서만 체결되므로 거래소별 조회는 자기 주문만 반환한다(중복 없음).
    KIS 가 단일 OVRS_EXCG_CD 값에 전 거래소 체결을 반환하는 구현이면 같은 주문이 여러 번
    들어올 수 있어 — 그 경우 누적 체결량이 가장 큰(가장 완전한) row 를 채택한다(중복 제거가
    이중 FILL 계상을 막는다; 멱등 키 `kis_fill_id=odno:누적체결량` 와 함께 이중 안전)."""
    best: dict[str, BrokerExecution] = {}
    for executions in per_market:
        for ex in executions:
            prev = best.get(ex.kis_order_id)
            if prev is None or ex.filled_qty > prev.filled_qty:
                best[ex.kis_order_id] = ex
    return list(best.values())


async def get_order_executions_resolving_market(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    order_date_yyyymmdd: str,
    end_date_yyyymmdd: str | None = None,
    markets: Sequence[str] = US_ORDER_EXCHANGES,
) -> list[BrokerExecution]:
    """주문체결내역을 *여러 거래소* 에 걸쳐 합쳐 조회(주문번호별 중복 제거).

    멀티에셋 유니버스(SPY·GLD=AMEX, IEF=NASD)는 거래소가 섞여, 단일 거래소 조회로는 다른
    거래소 종목의 체결이 통째로 빠진다 — 그러면 그 주문이 SUBMITTED 에 영영 갇히고(체결
    동기화 누락) 로컬 보유가 0 으로 남아 리밸런서가 과매수하며 손실 서킷 브레이커가 실제 노출을
    못 본다. 각 거래소를 조회해 합치고 주문번호로 중복 제거한다. 거래소별 조회 오류는 전파한다
    (fail-closed — `sync_fills` 가 ERROR 감사로 격리하고 다음 라운드에 재시도)."""
    per_market = [
        await get_order_executions(
            client,
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account,
            order_date_yyyymmdd=order_date_yyyymmdd,
            end_date_yyyymmdd=end_date_yyyymmdd,
            market=market,
        )
        for market in markets
    ]
    return _merge_executions(per_market)
