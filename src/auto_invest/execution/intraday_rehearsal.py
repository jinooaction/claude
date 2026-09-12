"""Offline KIS contract rehearsal; never reads environment or opens a socket."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from auto_invest.analytics.intraday_runtime import COMMISSION
from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.config.caps import SizingCaps
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.authority import ExecutionAuthority
from auto_invest.execution.intraday import Decision, IntradayExecutor, Observation
from auto_invest.execution.order_router import OrderRouter
from auto_invest.persistence import db

FINGERPRINT = "a" * 64


class RehearsalAuthority(ExecutionAuthority):
    async def submit_broker_order(self, *, request, market):
        result = await super().submit_broker_order(request=request, market=market)
        return result.model_copy(update={"accepted_at_utc": self.now()})


class Rehearsal:
    """Small broker state used only by rehearsal and contract tests."""

    def __init__(self):
        self.now = datetime(2026, 9, 8, 15, 0, tzinfo=UTC)
        self.orders = {}
        self.requests = []
        self.initial_cash = Decimal("10000")
        self.mark = Decimal("100")
        self.submit_timeout = False
        self.cancel_timeout = False
        self.cancel_reject = False
        self.engine = None
        self.conn = None

    def handle(self, request):
        path = request.url.path
        if request.method == "POST":
            body = json.loads(request.content)
            self.requests.append((path, body))
            if path.endswith("/order"):
                number = str(len(self.orders) + 1)
                self.orders[number] = dict(
                    odno=number,
                    pdno=body["PDNO"],
                    ft_ccld_qty="0",
                    ft_ccld_unpr3="0",
                    nccs_qty=body["ORD_QTY"],
                    sll_buy_dvsn_cd="02" if request.headers["tr_id"].endswith("1002U") else "01",
                    ord_dvsn_cd="00",
                    ft_ord_unpr3=body["OVRS_ORD_UNPR"],
                    market=body["OVRS_EXCG_CD"],
                    qty=int(body["ORD_QTY"]),
                    ord_dt=self.now.astimezone(UTC).strftime("%Y%m%d"),
                    ord_tmd=self.now.strftime("%H%M%S"),
                )
                if self.submit_timeout:
                    raise httpx.ReadTimeout("test response loss", request=request)
                return httpx.Response(200, json={"rt_cd": "0", "output": {"ODNO": number}})
            if path.endswith("/order-rvsecncl"):
                assert body["PDNO"] == self.orders[body["ORGN_ODNO"]]["pdno"]
                if self.cancel_timeout:
                    raise httpx.ReadTimeout("test response loss", request=request)
                if self.cancel_reject:
                    return httpx.Response(200, json={"rt_cd": "1", "msg1": "test rejection"})
                return httpx.Response(200, json={"rt_cd": "0", "output": {"ODNO": "C1"}})
        if request.method == "GET" and path.endswith("/inquire-ccnl"):
            market = request.url.params["OVRS_EXCG_CD"]
            rows = [o for o in self.orders.values() if o["market"] == market]
            return httpx.Response(200, json={"rt_cd": "0", "output": rows})
        raise AssertionError("unexpected network contract")

    def fill(self, number, cumulative, average, *, terminal=False):
        order = self.orders[number]
        order.update(
            ft_ccld_qty=str(cumulative),
            ft_ccld_unpr3=str(average),
            nccs_qty=str(0 if terminal else order["qty"] - cumulative),
        )
        if terminal:
            order["prcs_stat_name"] = "취소"

    async def observe(self):
        positions = {}
        cash = self.initial_cash
        open_ids = []
        for number, order in self.orders.items():
            qty = int(order["ft_ccld_qty"])
            sign = 1 if order["sll_buy_dvsn_cd"] == "02" else -1
            positions[order["pdno"]] = positions.get(order["pdno"], 0) + sign * qty
            notional = qty * Decimal(order["ft_ccld_unpr3"])
            # Rebuild from cumulative executions, including modeled fees on
            # both sides. Repeated observations and restarts must not charge
            # a partial fill twice. This is not an actual KIS fee schedule.
            cash -= sign * notional + notional * Decimal(str(COMMISSION))
            if int(order["nccs_qty"]) and not order.get("prcs_stat_name"):
                open_ids.append(number)
        positions = {s: q for s, q in positions.items() if q}
        return Observation(
            self.now,
            cash,
            cash + sum(positions.values()) * self.mark,
            positions,
            {s: self.mark for s in ("SPY", "QQQ", "IWM", "TLT", "GLD")},
            tuple(open_ids),
            dict(positions),
            {s: self.now for s in ("SPY", "QQQ", "IWM", "TLT", "GLD")},
        )

    def decision(self, target, *, end=None):
        return Decision(
            FINGERPRINT,
            end or self.now.replace(minute=self.now.minute // 5 * 5, second=0, microsecond=0),
            {"SPY": target},
            {"SPY": self.mark},
        )


@asynccontextmanager
async def rehearsal_session(path: Path, *, capital_limit=Decimal("10000"), mark=Decimal("100")):
    book = Rehearsal()
    book.initial_cash, book.mark = capital_limit, mark
    conn = db.get_connection(path)
    db.migrate(conn)
    async with httpx.AsyncClient(
        base_url="https://kis.invalid", transport=httpx.MockTransport(book.handle)
    ) as http:
        broker = ResilientClient(
            http,
            rate_limiter=AsyncTokenBucket(1000, 1000),
            breaker=CircuitBreaker(10, 1),
            max_retries=1,
        )
        router = OrderRouter(
            conn=conn,
            broker=broker,
            access_token="offline",
            app_key="offline",
            app_secret="offline",
            account_no="1234567801",
            whitelist=Whitelist(
                symbols={"SPY", "QQQ", "IWM", "TLT", "GLD"}, accounts={"1234567801"}
            ),
            caps=SizingCaps(
                per_trade_pct=Decimal("20"),
                per_symbol_pct=Decimal("20"),
                global_exposure_pct=Decimal("80"),
                canary_capital_pct=Decimal("10"),
                canary_min_duration_days=60,
                canary_acceptance_drawdown_pct=Decimal("2"),
            ),
            halt_path=path.with_suffix(".halt"),
        )
        router.execution_authority = RehearsalAuthority(
            conn=conn,
            broker=broker,
            access_token="offline",
            app_key="offline",
            app_secret="offline",
            account_no="1234567801",
            now=lambda: book.now,
        )
        book.conn = conn
        book.engine = IntradayExecutor(
            router,
            fingerprint=FINGERPRINT,
            observe=book.observe,
            authority_guard=lambda: None,
            capital_limit=capital_limit,
            now=lambda: book.now,
        )
        try:
            yield book
        finally:
            conn.close()


async def rehearse(*, capital_limit=Decimal("10000"), mark=Decimal("100")):
    with TemporaryDirectory(prefix="intraday-rehearsal-") as directory:
        async with rehearsal_session(
            Path(directory) / "rehearsal.db", capital_limit=capital_limit, mark=mark
        ) as book:
            engine = book.engine
            first = await engine.step(book.decision(5))
            assert first["actions"][0]["kind"] == "SUBMITTED", first
            book.fill("1", 2, str(mark * Decimal(".99")))
            partial = await engine.step(book.decision(5))
            assert partial["status"] == "WAIT_BROKER", partial
            cancelling = await engine.step(book.decision(0))
            assert cancelling["actions"][0]["result"] == "ACKNOWLEDGED", cancelling
            # A fill arrives after cancellation was accepted.
            book.fill("1", 3, str(mark * Decimal(".993")), terminal=True)
            liquidation = await engine.step(book.decision(0))
            assert liquidation["actions"][0]["kind"] == "SUBMITTED", liquidation
            assert book.orders["2"]["qty"] == 3
            book.fill("2", 3, str(mark))
            done = await engine.step(book.decision(0))
            assert done["status"] == "PROCESSED", done
            assert engine._owned() == {}
            again = await engine.step(book.decision(0))
            assert again["actions"] == [], again
            return dict(
                schema_version=182,
                mode="offline_rehearsal",
                orders_submitted=0,
                live_eligible=False,
                simulated_capital_limit_usd=str(capital_limit),
                simulated_mark_usd=str(mark),
                simulated_broker_requests=len(book.requests),
                final_owned_positions=engine._owned(),
                partial_cancel_late_fill_liquidation="PASS",
                duplicate_broker_requests=0,
            )
