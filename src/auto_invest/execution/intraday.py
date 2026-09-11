"""Persistent intraday coordinator using the existing KIS execution boundary.

No scheduler or credentials are created here. Production activation requires a
separate reviewed authority; by default even broker reads are denied.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, PriceTrigger, TradingRule
from auto_invest.execution.cancellation import request_cancellation
from auto_invest.execution.fill_sync import sync_fills
from auto_invest.execution.order_router import OrderRouter
from auto_invest.market_data.intraday import CALENDAR, NY, SYMBOLS
from auto_invest.market_data.intraday_pricing import limit_price

EXCHANGES = {"SPY": "AMEX", "QQQ": "NASD", "IWM": "AMEX", "TLT": "NASD", "GLD": "AMEX"}
OPEN = {"INTENT", "SUBMITTING", "SUBMISSION_UNKNOWN", "SUBMITTED", "PARTIALLY_FILLED"}


@dataclass(frozen=True)
class Decision:
    fingerprint: str
    bar_end: datetime
    targets: dict[str, int]
    limits: dict[str, Decimal]


@dataclass(frozen=True)
class Observation:
    observed_at: datetime
    cash: Decimal
    nav: Decimal
    positions: dict[str, int]
    marks: dict[str, Decimal]
    open_order_ids: tuple[str, ...]
    sellable_positions: dict[str, int]
    mark_times: dict[str, datetime]


def _decimal(value, *, zero=False):
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError("INVALID_MONEY")
    if not zero and not value:
        raise ValueError("INVALID_MONEY")


def validate_decision(d: Decision, fingerprint: str):
    if d.fingerprint != fingerprint or not re.fullmatch("[a-f0-9]{64}", fingerprint):
        raise ValueError("STRATEGY_IDENTITY")
    if (
        d.bar_end.tzinfo is None
        or d.bar_end.utcoffset() != timedelta(0)
        or d.bar_end.second
        or d.bar_end.microsecond
        or d.bar_end.minute % 5
    ):
        raise ValueError("BAR_TIMESTAMP")
    if not d.targets or set(d.targets) - set(SYMBOLS) or set(d.targets) != set(d.limits):
        raise ValueError("TARGET_UNIVERSE")
    for symbol, qty in d.targets.items():
        if type(qty) is not int or qty < 0:
            raise ValueError("TARGET_QUANTITY")
        _decimal(d.limits[symbol])
        if d.limits[symbol] != d.limits[symbol].quantize(Decimal(".01")):
            raise ValueError("LIMIT_TICK")


def validate_observation(
    v: Observation, now: datetime, required: set[str], *, require_fresh_marks=True
):
    if v.observed_at.tzinfo is None or not 0 <= (now - v.observed_at).total_seconds() <= 30:
        raise ValueError("STALE_ACCOUNT")
    _decimal(v.cash, zero=True)
    _decimal(v.nav)
    if v.cash > v.nav:
        raise ValueError("INVALID_NAV")
    for qty in v.positions.values():
        if type(qty) is not int or qty < 0:
            raise ValueError("INVALID_POSITION")
    if set(v.sellable_positions) != set(v.positions) or any(
        type(qty) is not int or not 0 <= qty <= v.positions[symbol]
        for symbol, qty in v.sellable_positions.items()
    ):
        raise ValueError("INVALID_SELLABLE_POSITION")
    if (required | {s for s, q in v.positions.items() if q}) - set(v.marks):
        raise ValueError("MISSING_MARKS")
    for mark in v.marks.values():
        _decimal(mark)
    if set(v.mark_times) != set(v.marks) or any(
        not isinstance(stamp, datetime)
        or stamp.tzinfo is None
        or stamp.utcoffset() is None
        or (require_fresh_marks and not 0 <= (now - stamp).total_seconds() <= 30)
        for stamp in v.mark_times.values()
    ):
        raise ValueError("STALE_EXECUTION_MARK")
    if len(v.open_order_ids) != len(set(v.open_order_ids)) or any(
        not isinstance(s, str) or not s for s in v.open_order_ids
    ):
        raise ValueError("INVALID_OPEN_ORDERS")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class IntradayExecutor:
    def __init__(
        self,
        router: OrderRouter,
        *,
        fingerprint: str,
        observe: Callable[[], Awaitable[Observation]],
        authority_guard: Callable[[], str | None] | None = None,
        capital_limit: Decimal = Decimal("0"),
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        external_holdings: Mapping[str, int] | None = None,
        entry_guard: Callable[[], str | None] | None = None,
        refresh_auth: Callable[[], Awaitable[None]] | None = None,
    ):
        if not re.fullmatch("[a-f0-9]{64}", fingerprint) or router.paper_mode:
            raise ValueError("EXECUTOR_CONFIGURATION")
        if external_holdings is not None and not isinstance(external_holdings, Mapping):
            raise ValueError("INVALID_EXTERNAL_HOLDINGS")
        baseline = dict(external_holdings) if external_holdings is not None else {}
        if any(
            not isinstance(symbol, str)
            or not symbol
            or symbol != symbol.strip().upper()
            or type(qty) is not int
            or qty <= 0
            for symbol, qty in baseline.items()
        ):
            raise ValueError("INVALID_EXTERNAL_HOLDINGS")
        # Explicit versioned baseline, never inferred from broker/local differences.
        # Copy before freezing so caller mutations cannot silently change ownership.
        self.external_holdings = MappingProxyType(baseline)
        self.external_holdings_digest = hashlib.sha256(_json(baseline).encode()).hexdigest()
        self.router, self.conn = router, router.conn
        self.fingerprint, self.observe, self.now = fingerprint, observe, now
        self.guard = authority_guard or (lambda: "INTRADAY_AUTHORIZATION_REQUIRED")
        self.entry_guard = entry_guard or (lambda: None)
        self.refresh_auth = refresh_auth
        _decimal(capital_limit, zero=True)
        self.capital_limit = capital_limit
        self._entry = True
        self._last_view_at = None
        self._last_mark_times = ()
        self.prefix = "intraday:" + fingerprint + ":"
        database = self.conn.execute("PRAGMA database_list").fetchone()[2]
        if not database:
            raise ValueError("PERSISTENT_DATABASE_REQUIRED")
        self.lock_path = Path(database + ".intraday.lock")
        # A driver may never silently remove the router's last-moment guard.
        prior_guard = getattr(router, "_intraday_original_guard", router.live_order_guard)
        router._intraday_original_guard = prior_guard
        router.live_order_guard = lambda: (
            self._write_guard(entry=self._entry) or (prior_guard() if prior_guard else None)
        )
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS intraday_execution_claims "
                "(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS intraday_execution_events "
                "(id INTEGER PRIMARY KEY, claim_id TEXT NOT NULL, kind TEXT NOT NULL, "
                "payload TEXT NOT NULL)"
            )
            for table in ("intraday_execution_claims", "intraday_execution_events"):
                for operation in ("UPDATE", "DELETE"):
                    self.conn.execute(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_{operation} "
                        f"BEFORE {operation} ON {table} "
                        "BEGIN SELECT RAISE(ABORT, 'append-only'); END"
                    )
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def _event(self, claim, kind, **payload):
        self.conn.execute(
            "INSERT INTO intraday_execution_events(claim_id,kind,payload) VALUES(?,?,?)",
            (claim, kind, _json(payload)),
        )

    def _mark_refusal(self, now):
        if not self._last_mark_times or any(
            not 0 <= (now - stamp).total_seconds() <= 30 for stamp in self._last_mark_times
        ):
            return "STALE_EXECUTION_MARK"
        return None

    def drain_requested(self):
        row = self.conn.execute(
            "SELECT kind FROM intraday_execution_events WHERE claim_id=? "
            "AND kind IN ('STOP_REQUESTED','STOP_COMPLETED') ORDER BY id DESC LIMIT 1",
            (self.prefix + "control",),
        ).fetchone()
        return bool(row and row["kind"] == "STOP_REQUESTED")

    def _drain_id(self):
        row = self.conn.execute(
            "SELECT id FROM intraday_execution_events WHERE claim_id=? "
            "AND kind='STOP_REQUESTED' ORDER BY id DESC LIMIT 1",
            (self.prefix + "control",),
        ).fetchone()
        return row["id"] if row else None

    def request_drain(self):
        """Persist intent only; a broker-confirmed flat observation completes it."""
        if not self.drain_requested():
            self._event(self.prefix + "control", "STOP_REQUESTED")

    def management_state(self):
        """Local counts for status; never a substitute for broker reconciliation."""
        rows = self.conn.execute(
            "SELECT state FROM orders WHERE substr(rule_id,1,?)=?",
            (len(self.prefix), self.prefix),
        ).fetchall()
        return dict(
            owned_symbols=len(self._owned()),
            pending_orders=sum(row["state"] in OPEN for row in rows),
            drain_requested=self.drain_requested(),
        )

    def _write_guard(self, *, entry, cancellation=False):
        if refusal := self.guard():
            return refusal
        if entry:
            if self.drain_requested():
                return "OPERATOR_STOP_REQUESTED"
            if refusal := self.entry_guard():
                return refusal
        now = self.now()
        day = str(now.astimezone(NY).date())
        if not CALENDAR.is_session(day):
            return "MARKET_CLOSED"
        opening = CALENDAR.session_open(day).to_pydatetime()
        closing = CALENDAR.session_close(day).to_pydatetime()
        if not opening <= now < closing:
            return "MARKET_CLOSED"
        if entry and (now >= closing - timedelta(minutes=15) or self.capital_limit <= 0):
            return "ENTRY_NOT_AUTHORIZED"
        if self._last_view_at is None or not 0 <= (now - self._last_view_at).total_seconds() <= 30:
            return "STALE_ACCOUNT"
        if not cancellation:
            return self._mark_refusal(now)
        return None

    def _owned(self):
        rows = self.conn.execute(
            "SELECT o.symbol, SUM(CASE WHEN o.side='BUY' THEN f.qty ELSE -f.qty END) qty "
            "FROM fills f JOIN orders o ON f.order_correlation_id=o.correlation_id "
            "WHERE substr(o.rule_id,1,?)=? GROUP BY o.symbol",
            (len(self.prefix), self.prefix),
        ).fetchall()
        owned = {r["symbol"]: int(r["qty"]) for r in rows if r["qty"]}
        if any(q < 0 for q in owned.values()):
            raise ValueError("OWNERSHIP_MISMATCH")
        return owned

    def _holding_cycles(self):
        inventory, cycles = {}, {}
        for row in self.conn.execute(
            "SELECT o.symbol,o.side,f.qty,f.seq FROM fills f JOIN orders o "
            "ON o.correlation_id=f.order_correlation_id WHERE substr(o.rule_id,1,?)=? "
            "ORDER BY f.seq", (len(self.prefix), self.prefix),
        ):
            symbol = row["symbol"]
            if row["side"] == "BUY":
                if not inventory.get(symbol, 0):
                    cycles[symbol] = row["seq"]
                inventory[symbol] = inventory.get(symbol, 0) + row["qty"]
            else:
                inventory[symbol] = inventory.get(symbol, 0) - row["qty"]
        return {symbol: cycles[symbol] for symbol, qty in inventory.items() if qty > 0}

    def _strategy_exits(self, cycles):
        result = {}
        for symbol, cycle in cycles.items():
            key = self.prefix + f"strategy-exit:{symbol}:{cycle}"
            rows = self.conn.execute(
                "SELECT kind,payload FROM intraday_execution_events WHERE claim_id=? LIMIT 2",
                (key,),
            ).fetchall()
            if not rows:
                continue
            try:
                payload = json.loads(rows[0]["payload"])
                if (len(rows) != 1 or rows[0]["kind"] != "STRATEGY_EXIT_REQUESTED"
                        or set(payload) not in (
                            {"symbol", "buy_fill_seq", "limit"},
                            {"symbol", "buy_fill_seq", "limit", "signal_bar_end"},
                        )
                        or payload["symbol"] != symbol
                        or type(payload["buy_fill_seq"]) is not int
                        or payload["buy_fill_seq"] != cycle
                        or not isinstance(payload["limit"], str)):
                    raise ValueError
                limit = Decimal(payload["limit"])
                _decimal(limit)
                if limit != limit.quantize(Decimal(".01")):
                    raise ValueError
                if "signal_bar_end" in payload:
                    stamp = datetime.fromisoformat(payload["signal_bar_end"])
                    if (stamp.utcoffset() != timedelta(0) or stamp.second or stamp.microsecond
                            or stamp.minute % 5):
                        raise ValueError
                result[symbol] = limit
            except Exception:
                raise ValueError("STRATEGY_EXIT_STATE_INVALID") from None
        return result

    async def _refresh(self, required, now):
        r = self.router
        if self.refresh_auth is not None:
            await self.refresh_auth()
            if refusal := self.guard():
                raise ValueError(refusal)
        earliest = self.conn.execute(
            "SELECT MIN(submitted_at_utc) FROM orders WHERE state IN "
            "('SUBMITTED','PARTIALLY_FILLED','SUBMISSION_UNKNOWN','SUBMITTING')"
        ).fetchone()[0]
        first_date = now.astimezone(NY).strftime("%Y%m%d")
        if earliest:
            first_date = min(
                first_date,
                datetime.fromisoformat(earliest.replace("Z", "+00:00"))
                .astimezone(NY)
                .strftime("%Y%m%d"),
            )
        result = await sync_fills(
            self.conn,
            r.broker,
            access_token=r.access_token,
            app_key=r.app_key,
            app_secret=r.app_secret,
            account=r.account_no,
            now=now,
            strict_contract=True,
            order_start_date_yyyymmdd=first_date,
            order_end_date_yyyymmdd=now.astimezone(NY).strftime("%Y%m%d"),
        )
        if result.error or result.warnings:
            raise ValueError("FILL_SYNC_UNCERTAIN")
        view = await self.observe()
        # Existing-order cancellation needs fresh reconciled account data, not
        # a new valuation price. Pricing is checked before any new order or P&L.
        validate_observation(view, self.now(), required, require_fresh_marks=False)
        self._last_view_at = view.observed_at
        self._last_mark_times = tuple(view.mark_times.values())
        local = {
            r["symbol"]: r["qty"]
            for r in self.conn.execute("SELECT symbol,qty FROM current_positions")
            if r["qty"]
        }
        for symbol, qty in self.external_holdings.items():
            local[symbol] = local.get(symbol, 0) + qty
        local = {s: q for s, q in local.items() if q}
        if local != {s: q for s, q in view.positions.items() if q}:
            raise ValueError("POSITION_RECONCILIATION_MISMATCH")
        rows = [
            dict(row)
            for row in self.conn.execute(
                "SELECT o.*,r.order_exchange FROM orders o "
                "LEFT JOIN order_routing r USING(correlation_id)"
            )
            if row["state"] in OPEN
        ]
        if any(row["state"] in {"INTENT", "SUBMITTING", "SUBMISSION_UNKNOWN"} for row in rows):
            raise ValueError("SUBMISSION_UNCERTAIN")
        if set(view.open_order_ids) != {row["kis_order_id"] for row in rows}:
            raise ValueError("OPEN_ORDER_RECONCILIATION_MISMATCH")
        if any(not row["rule_id"].startswith(self.prefix) for row in rows):
            raise ValueError("OTHER_STRATEGY_OPEN_ORDER")
        return view, rows

    async def on_bars(self, candidate, *, provider, bars):
        """Compile the preregistered strategy from bars and actual fill ownership."""
        from auto_invest.execution.intraday_signals import compile_decision, execution_fingerprint

        async def prepare():
            if execution_fingerprint(candidate, provider) != self.fingerprint:
                raise ValueError("STRATEGY_IDENTITY")
            now = self.now()
            day = str(now.astimezone(NY).date())
            if not CALENDAR.is_session(day):
                raise ValueError("MARKET_CLOSED")
            opening = CALENDAR.session_open(day).to_pydatetime()
            closing = CALENDAR.session_close(day).to_pydatetime()
            if not opening <= now < closing:
                raise ValueError("MARKET_CLOSED")
            view, _ = await self._refresh(set(SYMBOLS), now)
            owned = self._owned()
            if now >= closing - timedelta(minutes=15):
                # Closing protection does not depend on a working signal feed.
                return Decision(
                    self.fingerprint,
                    now.replace(minute=now.minute // 5 * 5, second=0, microsecond=0),
                    {s: 0 for s in SYMBOLS},
                    {s: view.marks[s].quantize(Decimal(".01")) for s in SYMBOLS},
                )
            entries, inventory, entered = {}, {}, set()
            for row in self.conn.execute(
                "SELECT o.symbol,o.side,f.qty,f.executed_at_utc FROM fills f JOIN orders o "
                "ON o.correlation_id=f.order_correlation_id WHERE substr(o.rule_id,1,?)=? "
                "ORDER BY f.seq",
                (len(self.prefix), self.prefix),
            ):
                symbol = row["symbol"]
                moment = datetime.fromisoformat(row["executed_at_utc"].replace("Z", "+00:00"))
                if row["side"] == "BUY":
                    if not inventory.get(symbol, 0):
                        entries[symbol] = moment
                    if moment >= opening:
                        entered.add(symbol)
                    inventory[symbol] = inventory.get(symbol, 0) + row["qty"]
                else:
                    inventory[symbol] = inventory.get(symbol, 0) - row["qty"]
            decision = compile_decision(
                candidate,
                provider=provider,
                bars=bars,
                now=now,
                owned=owned,
                entry_times=entries,
                entered_symbols=entered,
                capital=min(view.nav, self.capital_limit),
                cash=view.cash,
            )
            validate_decision(decision, self.fingerprint)
            cycles = self._holding_cycles()
            exits = self._strategy_exits(cycles)
            for symbol, quantity in owned.items():
                if quantity and decision.targets.get(symbol) == 0 and symbol not in exits:
                    cycle = cycles[symbol]
                    self._event(
                        self.prefix + f"strategy-exit:{symbol}:{cycle}",
                        "STRATEGY_EXIT_REQUESTED", symbol=symbol, buy_fill_seq=cycle,
                        limit=str(decision.limits[symbol]),
                        signal_bar_end=decision.bar_end.isoformat(),
                    )
            return decision

        return await self.step(prepare)

    async def step(self, decision: Decision | Callable[[], Awaitable[Decision]]) -> dict:
        return await self._locked_step(decision)

    async def manage(self) -> dict:
        """Maintain existing orders and exits even when bar collection is unavailable."""
        return await self._locked_step(None)

    async def _locked_step(self, decision) -> dict:
        if refusal := self.guard():
            return dict(status="DENIED", reason=refusal, actions=[])
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return dict(status="BUSY", actions=[])
            try:
                prepared = await decision() if callable(decision) else decision
                return await self._step(prepared)
            except Exception as exc:
                # Private account values and broker response text stay out of the result.
                code = (
                    str(exc)
                    if isinstance(exc, ValueError) and re.fullmatch("[A-Z_]+", str(exc))
                    else "EXECUTION_UNCERTAIN"
                )
                self._event("system", "HALTED", reason=code)
                return dict(status="HALTED", reason=code, actions=[])
        finally:
            os.close(fd)

    async def _step(self, d):
        if d is not None:
            validate_decision(d, self.fingerprint)
        now = self.now()
        if now.tzinfo is None:
            raise ValueError("CLOCK_INVALID")
        session = now.astimezone(NY).date()
        if not CALENDAR.is_session(str(session)):
            return dict(status="WAIT_SESSION", actions=[])
        opening = CALENDAR.session_open(str(session)).to_pydatetime()
        closing = CALENDAR.session_close(str(session)).to_pydatetime()
        if not opening <= now < closing:
            return dict(status="WAIT_SESSION", actions=[])
        exit_only = now >= closing - timedelta(minutes=15) or self.drain_requested()
        if d is not None and not exit_only and not 0 <= (now - d.bar_end).total_seconds() <= 300:
            raise ValueError("STALE_SIGNAL")
        if d is not None and not exit_only and d.bar_end < opening + timedelta(minutes=5):
            raise ValueError("INCOMPLETE_SESSION_SIGNAL")
        view, orders = await self._refresh(set(d.targets) if d is not None else set(), now)
        owned = self._owned()
        if d is None and not owned and not orders:
            if self.drain_requested():
                self._event(self.prefix + "control", "STOP_COMPLETED")
                return dict(status="STOPPED", actions=[])
            return dict(status="FLAT", actions=[])
        carried = {}
        for row in self.conn.execute(
            "SELECT o.symbol,o.side,f.qty,f.executed_at_utc FROM fills f JOIN orders o "
            "ON o.correlation_id=f.order_correlation_id WHERE substr(o.rule_id,1,?)=?",
            (len(self.prefix), self.prefix),
        ):
            if datetime.fromisoformat(row["executed_at_utc"].replace("Z", "+00:00")) < opening:
                carried[row["symbol"]] = carried.get(row["symbol"], 0) + (
                    row["qty"] if row["side"] == "BUY" else -row["qty"]
                )
        carryover = any(q > 0 and owned.get(s, 0) for s, q in carried.items())
        if any(
            view.positions.get(s, 0) - self.external_holdings.get(s, 0) < q
            for s, q in owned.items()
        ):
            raise ValueError("OWNERSHIP_MISMATCH")
        if refusal := self._mark_refusal(self.now()):
            if not orders:
                raise ValueError(refusal)
            day_id = self.prefix + str(session)
            loss_halted = self.conn.execute(
                "SELECT 1 FROM intraday_execution_events WHERE claim_id=? AND kind='LOSS_HALT'",
                (day_id,),
            ).fetchone()
            exit_only = (
                exit_only or bool(loss_halted) or self.router.halt_path.exists() or carryover
            )
            strategy_exits = {} if exit_only else self._strategy_exits(self._holding_cycles())
            targets = {s: 0 for s in owned} if exit_only else (
                dict(d.targets) if d is not None else None
            )
            if strategy_exits:
                targets = dict(targets or owned)
                targets.update({s: 0 for s in strategy_exits})
            result = await self._manage_pending(orders, targets, exit_only)
            result.setdefault("reason", refusal)
            return result
        profit = sum(q * view.marks[s] for s, q in owned.items())
        for row in self.conn.execute(
            "SELECT o.side,f.qty,f.price_usd FROM fills f JOIN orders o "
            "ON o.correlation_id=f.order_correlation_id WHERE substr(o.rule_id,1,?)=?",
            (len(self.prefix), self.prefix),
        ):
            value = row["qty"] * Decimal(row["price_usd"])
            profit += value * (-1 if row["side"] == "BUY" else 1) - value * Decimal(".0025")
        day_id = self.prefix + str(session)
        previous = self.conn.execute(
            "SELECT payload FROM intraday_execution_claims WHERE id=?", (day_id,)
        ).fetchone()
        if previous is None:
            self.conn.execute(
                "INSERT INTO intraday_execution_claims VALUES(?,?,?)",
                (
                    day_id,
                    self.fingerprint,
                    _json(
                        dict(
                            nav=str(view.nav),
                            profit=str(profit),
                            external_holdings_digest=self.external_holdings_digest,
                        )
                    ),
                ),
            )
            starting_nav = view.nav
            starting_profit = profit
        else:
            starting_nav = Decimal(json.loads(previous["payload"])["nav"])
            starting_profit = Decimal(json.loads(previous["payload"])["profit"])
        halted = self.conn.execute(
            "SELECT 1 FROM intraday_execution_events WHERE claim_id=? AND kind='LOSS_HALT'",
            (day_id,),
        ).fetchone()
        if (
            view.nav <= starting_nav * Decimal(".98")
            or (
                self.capital_limit > 0
                and profit - starting_profit <= -self.capital_limit * Decimal(".02")
            )
        ) and not halted:
            self._event(day_id, "LOSS_HALT")
            halted = True
        exit_only = exit_only or bool(halted) or self.router.halt_path.exists() or carryover
        cycles = {} if exit_only else self._holding_cycles()
        strategy_exits = self._strategy_exits(cycles)
        targets = {s: 0 for s in owned} if exit_only else (
            dict(d.targets) if d is not None else dict(owned)
        )
        if not exit_only:
            targets.update({s: 0 for s in strategy_exits})
        if orders:
            return await self._manage_pending(
                orders, targets if exit_only or d is not None or strategy_exits else None, exit_only
            )
        if d is None and not exit_only and not strategy_exits:
            return dict(status="MANAGED", actions=[])
        actions = []
        ordered_symbols = sorted(targets, key=lambda s: targets[s] - owned.get(s, 0))
        for symbol in ordered_symbols:
            # Reobserve after every prior order. No batch uses a stale cash snapshot.
            view, orders = await self._refresh(set(targets), self.now())
            if orders:
                return dict(status="WAIT_BROKER", actions=actions)
            if refusal := self._mark_refusal(self.now()):
                return dict(status="HALTED", reason=refusal, actions=actions)
            owned = self._owned()
            delta = targets[symbol] - owned.get(symbol, 0)
            if not delta:
                continue
            side = Side.BUY if delta > 0 else Side.SELL
            mark = view.marks[symbol]
            limit = (
                limit_price(mark, buy=False)
                if exit_only
                else strategy_exits[symbol] if symbol in strategy_exits else d.limits[symbol]
            )
            if side is Side.SELL and -delta > owned.get(symbol, 0):
                raise ValueError("SELL_EXCEEDS_OWNERSHIP")
            if side is Side.SELL and -delta > view.sellable_positions.get(symbol, 0):
                actions.append(
                    dict(kind="DENIED", symbol=symbol, reason="SELLABLE_QUANTITY_INSUFFICIENT")
                )
                continue
            notional = abs(delta) * max(mark, limit)
            capital = min(view.nav, self.capital_limit)
            global_exposure = sum(q * view.marks[s] for s, q in view.positions.items())
            if side is Side.BUY and (
                notional > capital * Decimal(".20")
                or view.positions.get(symbol, 0) * mark + notional > capital * Decimal(".20")
                or global_exposure + notional > capital * Decimal(".80")
                or notional * Decimal("1.003") > view.cash
            ):
                actions.append(dict(kind="DENIED", symbol=symbol, reason="CASH_OR_EXPOSURE"))
                continue
            if exit_only:
                decision_key = (
                    "drain:" + str(self._drain_id()) if self.drain_requested() else "close"
                )
            elif symbol in strategy_exits:
                period = now.replace(minute=now.minute // 5 * 5, second=0, microsecond=0)
                decision_key = f"strategy-exit:{cycles[symbol]}:" + period.isoformat()
            else:
                decision_key = d.bar_end.isoformat()
            key = self.prefix + _json(
                [
                    str(session),
                    decision_key,
                    symbol,
                    side.value,
                ]
            )
            claim = hashlib.sha256(key.encode()).hexdigest()
            previous = self.conn.execute(
                "SELECT payload FROM intraday_execution_claims WHERE id=?", (claim,)
            ).fetchone()
            if previous and exit_only and side is Side.SELL:
                # Bounded residual liquidation after an explicit terminal
                # cancellation. Keep the original limit; never chase the price.
                limit = Decimal(json.loads(previous["payload"])["limit"])
                for _ in range(2):
                    prior_order = self.conn.execute(
                        "SELECT state,correlation_id FROM orders WHERE rule_id=?",
                        (self.prefix + claim,),
                    ).fetchall()
                    if len(prior_order) != 1 or prior_order[0]["state"] not in {
                        "EXPIRED",
                        "CANCELLED",
                    }:
                        break
                    claim = hashlib.sha256(
                        (claim + ":" + prior_order[0]["correlation_id"]).encode()
                    ).hexdigest()
                    previous = self.conn.execute(
                        "SELECT payload FROM intraday_execution_claims WHERE id=?", (claim,)
                    ).fetchone()
                    if previous is None:
                        break
            if previous:
                actions.append(dict(kind="DUPLICATE_OR_PENDING", symbol=symbol))
                continue
            signal_bar_end = None
            decision_kind = "DRAIN" if exit_only else "SIGNAL"
            if not exit_only:
                if symbol in strategy_exits:
                    decision_kind = "STRATEGY_EXIT"
                    original = self.conn.execute(
                        "SELECT payload FROM intraday_execution_events WHERE claim_id=?",
                        (self.prefix + f"strategy-exit:{symbol}:{cycles[symbol]}",),
                    ).fetchone()
                    signal_bar_end = json.loads(original[0]).get("signal_bar_end")
                else:
                    signal_bar_end = d.bar_end.isoformat()
            payload = _json(dict(symbol=symbol, side=side.value, qty=abs(delta), limit=str(limit),
                                 signal_bar_end=signal_bar_end, decision_kind=decision_kind))
            self.conn.execute(
                "INSERT INTO intraday_execution_claims VALUES(?,?,?)",
                (claim, self.fingerprint, payload),
            )
            self._entry = side is Side.BUY
            rule = TradingRule(
                id=self.prefix + claim,
                symbol=symbol,
                stage=StrategyStage.CANARY,
                priority=1,
                trigger=PriceTrigger(direction="<=", threshold=limit, cooldown_seconds=300),
                action=Action(
                    side=side, order_type=OrderType.LIMIT, qty=abs(delta), limit_price=str(limit)
                ),
            )
            outcome = await self.router.submit_order(
                rule=rule,
                quote_price_usd=mark,
                total_capital_usd=capital,
                current_symbol_exposure_usd=view.positions.get(symbol, 0) * mark,
                current_global_exposure_usd=global_exposure,
                order_exchange=EXCHANGES[symbol],
            )
            self._event(
                claim,
                "ROUTER_RESULT",
                state=outcome.state,
                correlation_id=outcome.correlation_id,
                external_holdings_digest=self.external_holdings_digest,
            )
            actions.append(dict(kind=outcome.state, symbol=symbol))
        return dict(status="EXIT_ONLY" if exit_only else "PROCESSED", actions=actions)

    async def _manage_pending(self, orders, targets, exit_only):
        """Only manage already reconciled orders; never calculate a new price."""
        actions, owned = [], self._owned()
        for order in orders:
            stamp = order["submitted_at_utc"]
            age = (
                (self.now() - datetime.fromisoformat(stamp.replace("Z", "+00:00"))).total_seconds()
                if stamp
                else 999
            )
            target = (
                targets.get(order["symbol"], owned.get(order["symbol"], 0))
                if targets is not None else None
            )
            if age >= 300 or (
                order["side"] == "BUY" and (
                    exit_only or (
                        target is not None and target <= owned.get(order["symbol"], 0)
                    )
                )
            ):
                if refusal := self._write_guard(entry=False, cancellation=True):
                    return dict(status="HALTED", reason=refusal, actions=actions)
                phase = await request_cancellation(
                    self.router.execution_authority,
                    correlation_id=order["correlation_id"],
                    market=order["order_exchange"] or EXCHANGES[order["symbol"]],
                    reason="intraday_exit" if exit_only else "intraday_target_or_ttl",
                    before_write_guard=lambda: self._write_guard(entry=False, cancellation=True),
                )
                actions.append(dict(kind="CANCEL_REQUEST", result=phase))
        return dict(status="WAIT_BROKER", actions=actions)
