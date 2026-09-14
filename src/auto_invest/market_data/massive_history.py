"""Independent historical research from Massive. No broker or order access."""

import asyncio
import csv
import fcntl
import io
import json
import os
import re
import subprocess
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx

from auto_invest.analytics.intraday_paper_challenger import (
    load_intraday_dataset,
    load_preregistration,
    render_intraday_markdown,
    run_intraday_paper_challenger,
)
from auto_invest.analytics.intraday_paper_challenger_evidence import assess_intraday_evidence
from auto_invest.market_data.intraday import (
    CALENDAR,
    SYMBOLS,
    DataError,
    digest,
    encode,
    iso,
    normalize,
)

ROOT = Path(__file__).resolve().parents[3]
PREREG = ROOT / "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"
PROVIDER = "massive-sip-unadjusted"
HOST = "https://api.massive.com"


def _write(path, value):
    _blob(path, encode(value))


def _blob(path, raw):
    if path.is_symlink():
        raise DataError("HISTORY_LINK_DENIED")
    if path.exists():
        if path.read_bytes() != raw:
            raise DataError("HISTORY_EXISTING_DATA_CHANGED")
        return
    temporary = path.with_name(path.name + ".partial-" + uuid4().hex)
    with temporary.open("xb") as stream:
        os.chmod(temporary, 0o600)
        stream.write(raw)
    temporary.rename(path)


def _directory(path):
    if path.is_symlink():
        raise DataError("HISTORY_LINK_DENIED")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or path.stat().st_mode & 0o077:
        raise DataError("HISTORY_PRIVATE_DIRECTORY_REQUIRED")


def _rows(body, symbol, start, end, observed):
    if (not isinstance(body, dict) or body.get("status") not in {"OK", "DELAYED"}
            or body.get("ticker") != symbol or body.get("adjusted") is not False
            or body.get("next_url") or not isinstance(body.get("results", []), list)):
        raise DataError("HISTORY_RESPONSE_CONTRACT")
    values = body.get("results", [])
    if (len(values) > 50000 or body.get("resultsCount") != len(values)):
        raise DataError("HISTORY_RESPONSE_COUNT")
    rows = []
    for raw in values:
        if not isinstance(raw, dict) or type(raw.get("t")) is not int:
            raise DataError("HISTORY_TIMESTAMP_INVALID")
        stamp = datetime.fromtimestamp(raw["t"] / 1000, UTC)
        row = normalize(symbol, dict(raw, t=iso(stamp)), observed)
        if row:
            session = stamp.astimezone(CALENDAR.tz).date()
            if not start <= session <= end:
                raise DataError("HISTORY_RESPONSE_RANGE")
            rows.append(row)
    return rows


async def _fetch(client, key, path):
    # path is built only from the five fixed symbols and parsed ISO dates.
    for attempt in range(4):
        try:
            response = await client.get(
                HOST + path, params={"adjusted": "false", "sort": "asc", "limit": 50000},
                headers={"Authorization": "Bearer " + key}, follow_redirects=False, timeout=30,
            )
        except httpx.TransportError:
            if attempt == 3:
                raise DataError("HISTORY_TRANSPORT_FAILURE") from None
            await asyncio.sleep(2 ** attempt)
            continue
        if response.status_code == 200:
            if len(response.content) > 20_000_000 or key.encode() in response.content:
                raise DataError("HISTORY_RESPONSE_REJECTED")
            try:
                return response.json()
            except ValueError:
                raise DataError("HISTORY_RESPONSE_JSON") from None
        if response.status_code not in {429, 500, 502, 503, 504} or attempt == 3:
            raise DataError(f"HISTORY_HTTP_{response.status_code}")
        await asyncio.sleep(2 ** attempt)
    raise DataError("HISTORY_RETRY_EXHAUSTED")


def _dataset(path, rows, lineage, observed):
    _directory(path)
    source = dict(provider=PROVIDER, synthetic=False, retrieved_at_utc=iso(observed),
                  adjustment_policy="unadjusted; consolidated US eligible trades",
                  pages=lineage, bars=rows)
    _write(path / "source.json", source)
    files = {}
    columns = ("timestamp_utc", "symbol", "open", "high", "low", "close", "volume")
    for symbol in SYMBOLS:
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=columns)
        writer.writeheader()
        selected = [r for r in rows if r["symbol"] == symbol]
        writer.writerows(selected)
        raw = buffer.getvalue().encode()
        target = path / f"{symbol}.csv"
        _blob(target, raw)
        files[symbol] = dict(path=target.name, rows=len(selected), sha256=digest(raw))
    _write(path / "manifest.json", dict(
        schema_version="1.0", dataset_id=digest(encode(source)), provider=PROVIDER,
        synthetic=False, retrieved_at_utc=iso(observed), base_timeframe_minutes=5,
        adjustment_policy=source["adjustment_policy"], files=files,
        raw_sha256=digest(encode(source)),
    ))


async def acquire_and_review(*, start, end, output, api_key, client, now=None, interval=0.5):
    now = now or datetime.now(UTC)
    if (not isinstance(api_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", api_key)):
        raise DataError("MASSIVE_API_KEY_REQUIRED")
    start, end, output = date.fromisoformat(start), date.fromisoformat(end), Path(output)
    if not start <= end or (end - start).days > 1827 or now.utcoffset() is None:
        raise DataError("HISTORY_RANGE_INVALID")
    expected = CALENDAR.sessions_in_range(start, end)
    if len(expected) == 0 or CALENDAR.session_close(expected[-1]).to_pydatetime() >= now:
        raise DataError("HISTORY_COMPLETE_SESSIONS_REQUIRED")
    _directory(output)
    lock_fd = os.open(output / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        raise DataError("HISTORY_ALREADY_RUNNING") from None
    try:
        return await _run(start, end, expected, output, api_key, client, now, interval)
    finally:
        os.close(lock_fd)


async def _run(start, end, expected, output, key, client, now, interval):
    prereg_bytes = PREREG.read_bytes()
    _write(output / "plan.json", dict(
        schema=1, provider=PROVIDER, symbols=list(SYMBOLS), start=str(start), end=str(end),
        timeframe_minutes=5, adjusted=False, preregistration_digest=digest(prereg_bytes),
    ))
    _directory(output / "pages")
    rows, lineage, observations = {}, [], []
    for symbol in SYMBOLS:
        left = start
        while left <= end:
            right = min(end, left + timedelta(days=13))
            request = dict(symbol=symbol, start=str(left), end=str(right))
            page = output / "pages" / f"{symbol}-{left}-{right}.json"
            if page.is_symlink():
                raise DataError("HISTORY_LINK_DENIED")
            if page.exists():
                record = json.loads(page.read_bytes())
            else:
                await asyncio.sleep(interval)
                body = await _fetch(
                    client, key, f"/v2/aggs/ticker/{symbol}/range/5/minute/{left}/{right}",
                )
                _rows(body, symbol, left, right, now)
                record = dict(request=request, response=body, response_digest=digest(encode(body)),
                              retrieved_at_utc=iso(now))
                _write(page, record)
            observed = datetime.fromisoformat(record["retrieved_at_utc"].replace("Z", "+00:00"))
            if (observed.utcoffset() is None or observed > now or record["request"] != request
                    or record["response_digest"] != digest(encode(record["response"]))):
                raise DataError("HISTORY_CACHE_INVALID")
            for row in _rows(record["response"], symbol, left, right, observed):
                identity = (row["timestamp_utc"], row["symbol"])
                if identity in rows and rows[identity] != row:
                    raise DataError("HISTORY_CONFLICTING_BAR")
                rows[identity] = row
            observations.append(observed)
            lineage.append(dict(path="pages/" + page.name, sha256=digest(page.read_bytes())))
            left = right + timedelta(days=1)
    _dataset(output / "dataset", [rows[k] for k in sorted(rows)], lineage, max(observations))
    config = load_preregistration(PREREG)
    if digest(PREREG.read_bytes()) != digest(prereg_bytes):
        raise DataError("HISTORY_PREREGISTRATION_CHANGED")
    dataset = load_intraday_dataset(output / "dataset", output / "dataset/manifest.json", config)
    missing = {day.date() for day in expected} - set(dataset.sessions)
    if missing:
        dataset = replace(dataset, quality_reasons=dataset.quality_reasons + (
            "requested_calendar_sessions_missing",
        ))
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report, ledger = run_intraday_paper_challenger(
        dataset, config, preregistration_bytes=prereg_bytes, code_commit=commit,
        generated_at_utc=iso(now),
    )
    assessed = assess_intraday_evidence(report, config, preregistration_bytes=prereg_bytes,
                                       ledger_bytes=ledger)
    if not assessed.valid:
        raise DataError("HISTORY_INDEPENDENT_REVIEW_FAILED")
    review = output / ("research-" + uuid4().hex)
    _directory(review)
    _write(review / "research.json", report)
    (review / "ledger.csv").write_bytes(ledger)
    (review / "summary.md").write_text(render_intraday_markdown(report))
    result = dict(
        status="HISTORY_REVIEWED", provider=PROVIDER, requested_sessions=len(expected),
        complete_sessions=len(dataset.sessions), missing_sessions=len(missing),
        research_required_sessions=config["minimum_evidence"]["minimum_total_sessions"],
        decision=report["decision"], independent_evidence_valid=True,
        live_eligible=False, orders_submitted=0, research_path=str(review),
    )
    _write(review / "completed.json", result)
    return result
