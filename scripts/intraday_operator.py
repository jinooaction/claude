#!/usr/bin/env python3
"""한국투자 단타 모의 운용·시세·구매력·실주문 운용기 상태와 정리 요청."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib.util
import json
import os
import signal
import subprocess
from pathlib import Path
from types import SimpleNamespace

import httpx

from auto_invest.analytics.intraday_operator import request_stop, run, status
from auto_invest.analytics.intraday_runtime import read_status
from auto_invest.broker.auth import get_valid_token
from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.intraday_inputs import (
    EXCHANGES,
    REST_URL,
    InputError,
    StrictQuoteFeed,
    approval_key,
    buying_power,
)
from auto_invest.execution import intraday_runtime as execution_runtime
from auto_invest.market_data.intraday import DataError

ROOT = Path(__file__).resolve().parents[1]


def emit(result):
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False), flush=True)


def runtime_execute():
    spec = importlib.util.spec_from_file_location(
        "intraday_runtime", ROOT / "scripts/intraday_runtime.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.execute


async def execute(args):
    if args.command == "self-test":
        from auto_invest.execution.intraday_selftest import self_test

        return await self_test()
    if args.command == "history-review":
        from auto_invest.analytics.intraday_archive import review_archives

        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
        return review_archives(
            args.archives, args.out,
            ROOT / "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json",
            commit,
        )
    if args.command == "execution-status":
        return execution_runtime.status(args.db)
    if args.command == "execution-stop":
        return execution_runtime.request_stop(args.db)
    if args.command == "status":
        return status(args.root)
    if args.command == "stop":
        return request_stop(args.root)
    if args.command == "run":
        if any(not os.environ.get(k) for k in ("KIS_APP_KEY", "KIS_APP_SECRET")):
            raise InputError("KIS_CREDENTIALS_REQUIRED")
        existing_execute = runtime_execute()
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        async def cycle():
            result = await existing_execute(SimpleNamespace(
                command="run", provider="kis", state=args.root / "paper.db",
                out=args.root / "batches", token_cache=args.token_cache, poll_seconds=60, cycles=1,
            ))
            if result.get("status") == "WAIT_SESSION" and (args.root / "paper.db").is_file():
                result = dict(read_status(args.root / "paper.db"), status="WAIT_SESSION")
            return result

        try:
            return await run(
                args.root, cycle=cycle, poll_seconds=args.poll_seconds, cycles=args.cycles,
                stop_event=stop,
            )
        finally:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)
    if any(not os.environ.get(k) for k in ("KIS_APP_KEY", "KIS_APP_SECRET")):
        raise InputError("KIS_CREDENTIALS_REQUIRED")
    app_key, app_secret = os.environ["KIS_APP_KEY"], os.environ["KIS_APP_SECRET"]
    async with httpx.AsyncClient(base_url=REST_URL, timeout=10, follow_redirects=False) as http:
        broker = ResilientClient(
            http, rate_limiter=AsyncTokenBucket(1, 1), breaker=CircuitBreaker(3, 30), max_retries=2,
        )
        if args.command == "buying-power":
            account = os.environ.get("KIS_ACCOUNT_NO")
            if not account:
                raise InputError("KIS_ACCOUNT_REQUIRED")
            token = await get_valid_token(
                http, base_url=REST_URL, app_key=app_key, app_secret=app_secret,
                cache_path=args.token_cache,
            )
            power = await buying_power(
                broker, symbol=args.symbol, limit_price=args.limit_price, account=account,
                access_token=token.access_token, app_key=app_key, app_secret=app_secret,
            )
            return dict(
                status="BUYING_POWER_OBSERVED", symbol=power.symbol, exchange=power.exchange,
                limit_price=str(power.limit_price),
                foreign_orderable_amount=str(power.foreign_orderable_amount),
                foreign_orderable_qty=power.foreign_orderable_qty,
                observed_at=power.started_at.isoformat(), orders_submitted=0,
            )
        if not 1 <= args.seconds <= 300:
            raise InputError("QUOTE_DURATION_BOUNDS")
        feed = StrictQuoteFeed()

        async def approval():
            return await approval_key(broker, app_key=app_key, app_secret=app_secret)

        task = asyncio.create_task(feed.serve(approval=approval))
        result = dict(status="WAIT_QUOTES", quotes={}, orders_submitted=0)
        try:
            for _ in range(args.seconds):
                await asyncio.sleep(1)
                current = feed.snapshot()
                result = dict(
                    status="QUOTES_OBSERVED" if current else "WAIT_QUOTES",
                    reason=feed.reason, quotes={s: q.public() for s, q in current.items()},
                    complete=set(current) == set(EXCHANGES), orders_submitted=0,
                )
                emit(result)
                if task.done():
                    await task
                    result["status"] = "FAILED"
                    break
            return result
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test", help="외부 접속 없는 주문 엔진·중지·재시작 자체 시험")
    command = commands.add_parser("history-review", help="보관 자료 결합·연구 검증")
    command.add_argument("--archives", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    for name in ("run", "status", "stop"):
        command = commands.add_parser(name)
        command.add_argument("--root", type=Path, default=Path("data/intraday-operator"))
        if name == "run":
            command.add_argument("--poll-seconds", type=int, default=60)
            command.add_argument("--cycles", type=int, default=0)
            command.add_argument("--token-cache", type=Path, default=Path("data/kis_token.json"))
    for name in ("execution-status", "execution-stop"):
        command = commands.add_parser(
            name,
            help="상태 조회" if name == "execution-status" else "중지·정리 요청",
        )
        command.add_argument("--db", type=Path, required=True)
    command = commands.add_parser("quotes")
    command.add_argument("--seconds", type=int, default=30)
    command = commands.add_parser("buying-power")
    command.add_argument("--symbol", required=True, choices=tuple(EXCHANGES))
    command.add_argument("--limit-price", required=True)
    command.add_argument("--token-cache", type=Path, default=Path("data/kis_token.json"))
    return result


def main():
    args = parser().parse_args()
    try:
        result = asyncio.run(execute(args))
    except (InputError, DataError) as exc:
        result = dict(status="FAILED", reason=str(exc), orders_submitted=0)
    except KeyboardInterrupt:
        result = dict(
            status="INTERRUPTED" if args.command.startswith("execution-") else "STOPPED",
            orders_submitted=0,
        )
    except Exception:
        result = dict(status="FAILED", reason="OPERATOR_FAILED", orders_submitted=0)
    emit(result)
    if args.command == "quotes" and not result.get("complete"):
        return 2
    return 2 if result.get("status", result.get("phase")) in {"FAILED", "ALREADY_RUNNING"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
