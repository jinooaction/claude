"""Bounded SPY history observation, independent of collection/qualification policy."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from auto_invest.broker.auth import get_valid_token
from auto_invest.market_data.intraday import (
    KIS_BARS,
    KIS_BASE,
    NY,
    DataError,
    digest,
    encode,
    iso,
    normalize,
)


def _save(path, value, secrets):
    raw = encode(value)
    if any(secret.encode() in raw for secret in secrets):
        raise DataError("DEPTH_SECRET_REFLECTION")
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(raw)
    return digest(raw)


async def probe_kis_history_depth(transport, env, cache_path, output_root, *, max_pages=80):
    if type(max_pages) is not int or not 1 <= max_pages <= 80:
        raise DataError("DEPTH_PAGE_LIMIT_INVALID")
    key, secret = env.get("KIS_APP_KEY"), env.get("KIS_APP_SECRET")
    if not isinstance(key, str) or not key or not isinstance(secret, str) or not secret:
        raise DataError("DEPTH_ACCESS_REQUIRED")
    root = Path(output_root)
    if root.is_symlink():
        raise DataError("DEPTH_OUTPUT_LINK")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not root.is_dir() or root.stat().st_mode & 0o077:
        raise DataError("DEPTH_PRIVATE_OUTPUT_REQUIRED")
    run = root / ("run-" + uuid4().hex)
    run.mkdir(mode=0o700)
    started = datetime.now(UTC)
    token = await get_valid_token(transport, base_url=KIS_BASE, app_key=key,
                                 app_secret=secret, cache_path=cache_path, now=started)
    secrets = (key, secret, token.access_token)
    headers = dict(authorization="Bearer " + token.access_token, appkey=key,
                   appsecret=secret, tr_id="HHDFS76950200", custtype="P", tr_cont="")
    params = dict(AUTH="", EXCD="AMS", SYMB="SPY", NMIN="5", PINC="1", NEXT="",
                  NREC="120", FILL="", KEYB="")
    previous, first, last = None, None, None
    bars, raw_rows, lineage = {}, {}, []
    reason = "PAGE_LIMIT_REACHED"
    for page in range(max_pages):
        requested = datetime.now(UTC)
        response = await transport.request("GET", KIS_BARS, headers=headers, params=dict(params))
        observed = datetime.now(UTC)
        try:
            body = response.json()
        except ValueError:
            raise DataError("DEPTH_RESPONSE_JSON") from None
        page_digest = _save(run / f"page-{page:03}.json", dict(
            request=params, requested_at_utc=iso(requested), observed_at_utc=iso(observed),
            response=body,
        ), secrets)
        lineage.append(page_digest)
        if (not isinstance(body, dict) or body.get("rt_cd") != "0"
                or not isinstance(body.get("output2"), list) or len(body["output2"]) > 120):
            raise DataError("DEPTH_RESPONSE_CONTRACT")
        times = []
        for raw in body["output2"]:
            try:
                stamp = datetime.strptime(raw["xymd"] + raw["xhms"], "%Y%m%d%H%M%S")
                stamp = stamp.replace(tzinfo=NY).astimezone(UTC)
                if stamp > observed:
                    raise DataError("DEPTH_FUTURE_BAR")
                values = dict(t=iso(stamp), o=raw["open"], h=raw["high"], l=raw["low"],
                              c=raw["last"], v=raw["evol"])
                if stamp in raw_rows and raw_rows[stamp] != values:
                    raise DataError("DEPTH_CONFLICTING_BAR")
                raw_rows[stamp] = values
                row = normalize("SPY", values, observed)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                if isinstance(exc, DataError):
                    raise
                raise DataError("DEPTH_BAR_SCHEMA") from None
            times.append(stamp)
            if row:
                bars[stamp] = row
        if not times:
            reason = "EMPTY_PAGE"
            break
        oldest, newest = min(times), max(times)
        first = min(first, oldest) if first else oldest
        last = max(last, newest) if last else newest
        if previous is not None and oldest >= previous:
            reason = "CURSOR_NOT_ADVANCING"
            break
        previous = oldest
        params.update(NEXT="1", KEYB=(oldest - timedelta(minutes=5)).astimezone(NY)
                      .strftime("%Y%m%d%H%M%S"))
    _save(run / "regular-bars.json", [bars[k] for k in sorted(bars)], secrets)
    result = dict(
        status="OBSERVED", symbol="SPY", provider="kis-nasdaq-partial-unadjusted",
        page_limit=max_pages, pages=len(lineage), raw_unique_bars=len(raw_rows),
        regular_bars=len(bars), regular_sessions=len({t.astimezone(NY).date() for t in bars}),
        oldest_utc=iso(first) if first else None, newest_utc=iso(last) if last else None,
        oldest_regular_utc=iso(min(bars)) if bars else None,
        observed_older_than_30_days=bool(first and first < started - timedelta(days=30)),
        stop_reason=reason, provider_history_limit_proven=False,
        source_path=str(run), page_digests=lineage, orders_submitted=0, live_eligible=False,
    )
    _save(run / "completed.json", result, secrets)
    return result
