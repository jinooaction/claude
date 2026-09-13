"""Own one bounded, GET-only account frame with real request receipt times."""

import asyncio
import re
from copy import deepcopy
from datetime import UTC, datetime

from auto_invest.broker.account_asset_evidence import ASSETS_URL, observe_account_assets
from auto_invest.broker.domestic_account import URL as DOMESTIC_URL
from auto_invest.broker.domestic_account import _time, observe_domestic_account
from auto_invest.broker.intraday_account import ENDPOINTS, ROOT, AccountReadError, observe_account
from auto_invest.broker.intraday_cash_baseline import (
    CURRENT,
    MARGIN,
    normalize_cash_baseline,
    normalize_usd_settlement_cash,
)
from auto_invest.broker.intraday_holdings_coverage import normalize_current_holdings
from auto_invest.broker.overseas import _kis_headers, _split_account

READ_TIMEOUT_SECONDS = 30
ALLOWED = frozenset({ROOT + endpoint for endpoint in ENDPOINTS}
                    | {CURRENT, DOMESTIC_URL, ASSETS_URL})


class _FrameClient:
    def __init__(self, client, account, now, check_connection):
        self.client, self.now, self.check_connection = client, now, check_connection
        self.cano, self.product = _split_account(account)
        self.started = self.previous = _time(now())
        self.records = []

    def clock(self):
        self.check_connection()
        current = _time(self.now())
        if not self.previous <= current or (current - self.started).total_seconds() > 30:
            raise AccountReadError("FRAME_INTERVAL_INVALID")
        self.previous = current
        return current

    async def request(self, method, endpoint, *, headers, params):
        start = self.clock()
        if (method != "GET" or endpoint not in ALLOWED or len(self.records) >= 66
                or params.get("CANO") != self.cano
                or params.get("ACNT_PRDT_CD") != self.product):
            raise AccountReadError("FRAME_REQUEST_SCOPE_INVALID")
        try:
            response = await self.client.request(method, endpoint, headers=headers, params=params)
        except Exception:
            raise AccountReadError("FRAME_TRANSPORT_UNAVAILABLE") from None
        end = self.clock()
        try:
            response.raise_for_status()
            body = response.json()
        except Exception:
            raise AccountReadError("FRAME_RESPONSE_INVALID") from None
        if not isinstance(body, dict) or body.get("rt_cd") != "0":
            raise AccountReadError("FRAME_BROKER_REJECTED")
        self.records.append(dict(endpoint=endpoint, started_at=start.isoformat(),
            received_at=end.isoformat(), http_status=response.status_code,
            continuation=response.headers.get("tr_cont", "").strip(),
            data=deepcopy({key: body[key] for key in
                          ("rt_cd", "output", "output1", "output2", "output3") if key in body})))
        return response


async def observe_account_frame(client, *, access_token, app_key, app_secret, account,
                                check_connection, now=lambda: datetime.now(UTC)):
    """Private result; amounts must never be copied into a public diagnostic log."""
    if not isinstance(account, str) or not re.fullmatch(r"[0-9]{10}", account):
        raise AccountReadError("FRAME_ACCOUNT_INVALID")

    async def collect():
        frame = _FrameClient(client, account, now, check_connection)
        kwargs = dict(access_token=access_token, app_key=app_key, app_secret=app_secret,
                      account=account, now=frame.clock)
        headers = _kis_headers(access_token=access_token, app_key=app_key,
                               app_secret=app_secret, tr_id="CTRP6504R")
        headers["tr_cont"] = ""
        params = dict(CANO=frame.cano, ACNT_PRDT_CD=frame.product,
                      WCRC_FRCR_DVSN_CD="02", NATN_CD="000", TR_MKET_CD="00", INQR_DVSN_CD="00")
        await frame.request("GET", CURRENT, headers=headers, params=params)
        result = await observe_account(frame, **kwargs)
        result["reported_domestic_account"] = await observe_domestic_account(frame, **kwargs)
        result["reported_account_assets"] = await observe_account_assets(frame, **kwargs)
        await frame.request("GET", CURRENT, headers=headers, params=params)
        clock = frame.clock()
        records = [record for record in frame.records if record["endpoint"] in {CURRENT, MARGIN}]
        baseline = normalize_cash_baseline(records, observed_at=clock)
        baseline["settlement_cash"] = normalize_usd_settlement_cash(records, observed_at=clock)
        baseline["current_holdings"] = normalize_current_holdings(records, observed_at=clock)
        result["reported_cash_baseline"] = baseline
        result["account_frame"] = dict(
            observation_started_at=frame.records[0]["started_at"],
            observation_completed_at=frame.records[-1]["received_at"],
            request_count=len(frame.records),
            asset_reports=[record for record in frame.records if record["endpoint"] == ASSETS_URL],
            full_account_verified=False,
        )
        return result

    try:
        return await asyncio.wait_for(collect(), READ_TIMEOUT_SECONDS)
    except TimeoutError:
        raise AccountReadError("FRAME_READ_TIMEOUT") from None
