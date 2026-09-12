"""Reconciled zero-adjustment USD baseline, not full-account net cash authority."""

import asyncio
import re
from datetime import UTC, datetime

from auto_invest.broker.account_source_profile import CASH_FIELDS, _number
from auto_invest.broker.intraday_account import AccountReadError
from auto_invest.broker.overseas import _kis_headers, _split_account

ROOT = "/uapi/overseas-stock/v1/trading/"
CURRENT = ROOT + "inquire-present-balance"
MARGIN = ROOT + "foreign-margin"
READ_TIMEOUT_SECONDS = 30


class BaselineUnavailable(ValueError):
    pass


def _require(condition, reason):
    if not condition:
        raise BaselineUnavailable(reason)


def _rows(data, field):
    value = data.get(field)
    if isinstance(value, dict):
        value = [value]
    _require(isinstance(value, list) and len(value) <= 2000
             and all(isinstance(row, dict) for row in value), "BASELINE_ROWS_INVALID")
    return value


def _value(row, field):
    amount = _number(row.get(field))
    _require(amount is not None and amount >= 0, "BASELINE_AMOUNT_INVALID")
    return amount


def _stamp(value):
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except (ValueError, TypeError, OverflowError):
        raise BaselineUnavailable("BASELINE_TIME_INVALID") from None


def _current_cash(data):
    rows = _rows(data, "output2")
    usd = []
    for row in rows:
        code = row.get("crcy_cd")
        _require(isinstance(code, str) and re.fullmatch(r"[A-Z]{3}", code.strip()),
                 "BASELINE_CURRENCY_INVALID")
        amount = _value(row, "frcr_dncl_amt_2")
        _require(_value(row, "frcr_buy_mgn_amt") == _value(row, "frcr_etc_mgna") == 0,
                 "BASELINE_ADJUSTMENT_PRESENT")
        if code.strip() == "USD":
            usd.append(amount)
        else:
            _require(amount == 0, "BASELINE_OTHER_CURRENCY_PRESENT")
    _require(len(usd) == 1, "BASELINE_USD_ROW_NOT_UNIQUE")
    summaries = _rows(data, "output3")
    _require(len(summaries) == 1, "BASELINE_SUMMARY_NOT_UNIQUE")
    _require(all(_value(summaries[0], field) == 0 for field in (
        "dncl_amt", "cma_evlu_amt", "tot_loan_amt", "ustl_buy_amt_smtl", "ustl_sll_amt_smtl",
    )), "BASELINE_OTHER_CASH_OR_LIABILITY_PRESENT")
    return usd[0]


def normalize_cash_baseline(records, *, observed_at):
    result = dict(status="UNAVAILABLE", cash=None, full_account_verified=False,
                  scope="REPORTED_ZERO_ADJUSTMENT_USD_BASELINE", live_eligible=False)
    try:
        _require(isinstance(records, list) and len(records) == 3, "BASELINE_BATCH_SHAPE")
        clock, previous = _stamp(observed_at), None
        for index, (record, endpoint) in enumerate(zip(records, (CURRENT, MARGIN, CURRENT),
                                                       strict=True)):
            _require(isinstance(record, dict) and record.get("endpoint") == endpoint,
                     "BASELINE_REQUEST_SCOPE")
            _require(isinstance(record.get("continuation"), str)
                     and record["continuation"] in {"", "D", "E"},
                     "BASELINE_INCOMPLETE_REPORT")
            start, end = _stamp(record.get("started_at")), _stamp(record.get("received_at"))
            _require(start <= end <= clock and (previous is None or previous <= start),
                     "BASELINE_TIME_ORDER")
            _require(0 <= (clock - start).total_seconds() <= 30, "BASELINE_STALE")
            previous = end
            data = record.get("data")
            _require(record.get("http_status") == 200 and isinstance(data, dict)
                     and data.get("rt_cd") == "0", "BASELINE_BROKER_RESPONSE_INVALID")
            if index != 1:
                amount = _current_cash(data)
                if index == 0:
                    cash = amount
                else:
                    _require(amount == cash, "BASELINE_CASH_CHANGED")
            else:
                usd_count = 0
                for row in _rows(data, "output"):
                    code = row.get("crcy_cd")
                    _require(isinstance(code, str) and (
                        not code.strip() or re.fullmatch(r"[A-Z]{3}", code.strip())
                    ), "BASELINE_CURRENCY_INVALID")
                    values = [_value(row, field) for field in CASH_FIELDS]
                    if code.strip() == "USD":
                        usd_count += 1
                        _require(values[0] == cash, "BASELINE_MARGIN_DEPOSIT_DIFFERS")
                        _require(all(value == 0 for value in values[1:]),
                                 "BASELINE_ADJUSTMENT_PRESENT")
                    else:
                        _require(all(value == 0 for value in values),
                                 "BASELINE_OTHER_CASH_OR_LIABILITY_PRESENT")
                _require(usd_count > 0, "BASELINE_USD_MARGIN_MISSING")
        result.update(status="CALCULATED", cash=str(cash), usd_margin_row_count=usd_count,
                      observation_started_at=_stamp(records[0]["started_at"]).isoformat(),
                      observation_completed_at=_stamp(records[-1]["received_at"]).isoformat())
    except BaselineUnavailable as error:
        result["reason"] = str(error)
    return result


async def observe_cash_baseline(client, *, access_token, app_key, app_secret, account,
                                now=lambda: datetime.now(UTC)):
    """Own the fixed GET sequence; no operator-supplied reports or approval flags."""
    try:
        return await asyncio.wait_for(_collect_cash_baseline(
            client, access_token=access_token, app_key=app_key, app_secret=app_secret,
            account=account, now=now), timeout=READ_TIMEOUT_SECONDS)
    except TimeoutError:
        raise AccountReadError("BASELINE_READ_TIMEOUT") from None
    except BaselineUnavailable as error:
        raise AccountReadError(str(error)) from None


async def _collect_cash_baseline(client, *, access_token, app_key, app_secret, account, now):
    if not isinstance(account, str) or not re.fullmatch(r"[0-9]{10}", account):
        raise AccountReadError("BASELINE_ACCOUNT_INVALID")
    cano, product = _split_account(account)
    records = []
    for endpoint in (CURRENT, MARGIN, CURRENT):
        start = _stamp(now())
        if records:
            _require(_stamp(records[-1]["received_at"]) <= start,
                     "BASELINE_TIME_ORDER")
            _require((start - _stamp(records[0]["started_at"])).total_seconds() <= 30,
                     "BASELINE_STALE")
        headers = _kis_headers(access_token=access_token, app_key=app_key,
                               app_secret=app_secret,
                               tr_id="TTTC2101R" if endpoint == MARGIN else "CTRP6504R")
        headers["tr_cont"] = ""
        params = dict(CANO=cano, ACNT_PRDT_CD=product)
        if endpoint == CURRENT:
            params.update(WCRC_FRCR_DVSN_CD="02", NATN_CD="000", TR_MKET_CD="00",
                          INQR_DVSN_CD="00")
        try:
            response = await client.request("GET", endpoint, headers=headers, params=params)
            data = response.json()
        except Exception:
            raise AccountReadError("BASELINE_TRANSPORT_OR_JSON_ERROR") from None
        records.append(dict(endpoint=endpoint, started_at=start.isoformat(),
                            received_at=_stamp(now()).isoformat(), http_status=response.status_code,
                            continuation=response.headers.get("tr_cont", "").strip(), data=data))
    return normalize_cash_baseline(records, observed_at=now())
