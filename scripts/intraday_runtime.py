#!/usr/bin/env python3
"""장중 자료 수집 및 별도 진단 모의 운용. 실주문 옵션은 없습니다."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx

from auto_invest.analytics.intraday_paper_challenger import (
    load_intraday_dataset,
    load_preregistration,
)
from auto_invest.analytics.intraday_runtime import PaperRuntime, read_status
from auto_invest.market_data.intraday import (
    CALENDAR,
    NY,
    DataError,
    ReadTransport,
    collect_alpaca,
    collect_kis,
    encode,
    iso,
    utc,
    write_batch,
)

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"


def _apply(runtime, bars, *, observed=None):
    grouped = {}
    for bar in bars:
        grouped.setdefault(bar["timestamp_utc"], []).append(bar)
    for stamp in sorted(grouped):
        runtime.process(grouped[stamp], observed or utc(stamp) + timedelta(minutes=5))


async def _collect(args, transport, now, start=None, end=None):
    start = start or utc(args.start)
    end = end or utc(args.end)
    if args.provider == "alpaca":
        return await collect_alpaca(transport, os.environ, start, end, now)
    return await collect_kis(transport, os.environ, start, end, now, args.token_cache)


async def execute(args):
    if args.command == "status":
        return read_status(args.state)
    config = load_preregistration(PREREG)
    if args.command == "paper":
        dataset = load_intraday_dataset(args.bars_dir, args.bars_dir / "manifest.json", config)
        runtime = PaperRuntime(args.state, config, dataset.provider, dataset.synthetic, "replay")
        try:
            rows = [
                dict(
                    symbol=b.symbol,
                    timestamp_utc=iso(b.timestamp_utc),
                    open=b.open,
                    high=b.high,
                    low=b.low,
                    close=b.close,
                    volume=b.volume,
                )
                for values in dataset.bars_by_symbol.values()
                for b in values
            ]
            _apply(runtime, rows)
            return runtime.status()
        finally:
            runtime.close()
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        transport = ReadTransport(client)
        if args.command == "collect":
            batch = await _collect(args, transport, datetime.now(UTC))
            batch["retrieved_at_utc"] = iso(datetime.now(UTC))
            write_batch(args.out, batch)
            return dict(
                status="DATA_COLLECTED",
                provider=batch["provider"],
                bars=len(batch["bars"]),
                out=str(args.out),
                orders_submitted=0,
                live_eligible=False,
            )
        if not 60 <= args.poll_seconds <= 300 or not 0 <= args.cycles <= 10000:
            raise DataError("RUN_BOUNDS")
        runtime = None
        count = 0
        last_status = dict(status="WAIT_SESSION", orders_submitted=0, live_eligible=False)
        try:
            while args.cycles == 0 or count < args.cycles:
                now = datetime.now(UTC)
                session = now.astimezone(NY).date()
                if CALENDAR.is_session(session):
                    opening = CALENDAR.session_open(session).to_pydatetime()
                    closing = CALENDAR.session_close(session).to_pydatetime()
                    if opening + timedelta(minutes=5) <= now <= closing + timedelta(minutes=2):
                        batch = await _collect(args, transport, now, opening, min(now, closing))
                        batch["retrieved_at_utc"] = iso(datetime.now(UTC))
                        directory = args.out / (now.strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex)
                        write_batch(directory, batch)
                        if runtime is None:
                            runtime = PaperRuntime(
                                args.state, config, batch["provider"], False, "forward"
                            )
                        _apply(runtime, batch["bars"], observed=datetime.now(UTC))
                        last_status = runtime.status()
                print(json.dumps(last_status, ensure_ascii=False), flush=True)
                count += 1
                if args.cycles == 0 or count < args.cycles:
                    await asyncio.sleep(args.poll_seconds)
            return last_status
        except Exception as exc:
            # Persist a sanitized failure without rewriting previous bar/audit evidence.
            args.out.mkdir(parents=True, exist_ok=True)
            error = str(exc) if isinstance(exc, DataError) else type(exc).__name__
            with (args.out / ("failure-" + uuid4().hex + ".json")).open("xb") as handle:
                handle.write(
                    encode(
                        dict(
                            status="RUN_FAILED",
                            error=error,
                            orders_submitted=0,
                            observed=iso(datetime.now(UTC)),
                        )
                    )
                )
            raise
        finally:
            if runtime:
                runtime.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect")
    collect.add_argument("--provider", choices=("alpaca", "kis"), required=True)
    collect.add_argument("--start", required=True)
    collect.add_argument("--end", required=True)
    collect.add_argument("--out", type=Path, required=True)
    paper = commands.add_parser("paper")
    paper.add_argument("--bars-dir", type=Path, required=True)
    paper.add_argument("--state", type=Path, required=True)
    status = commands.add_parser("status")
    status.add_argument("--state", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--provider", choices=("kis",), default="kis")
    run.add_argument("--state", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--poll-seconds", type=int, default=60)
    run.add_argument("--cycles", type=int, default=0)
    for command in (collect, run):
        command.add_argument(
            "--token-cache", type=Path, default=ROOT / "data/intraday-auth/token.json"
        )
    args = parser.parse_args(argv)
    try:
        print(json.dumps(asyncio.run(execute(args)), ensure_ascii=False))
        return 0
    except Exception as exc:
        # Never render provider payload, HTTP request/headers or secret validation values.
        code = str(exc) if isinstance(exc, DataError) else type(exc).__name__
        print(
            json.dumps(
                dict(
                    status="DATA_ACCESS_REQUIRED"
                    if code.startswith("DATA_ACCESS_REQUIRED")
                    else "FAILED",
                    reason=code,
                    orders_submitted=0,
                    live_eligible=False,
                ),
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
