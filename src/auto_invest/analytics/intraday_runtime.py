"""Spec 181 persistent diagnostic paper runtime. There is no live-order adapter.

One event commits a complete five-symbol bar and all 18 isolated virtual accounts.
Late/gapped inputs cannot retrospectively create entries. Unfilled exits retain exposure.
"""

from __future__ import annotations

import copy
import json
import math
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from auto_invest.analytics.intraday_paper_challenger import (
    ResampledBar,
    _entry_signal,
    _exit_signal,
    build_candidate_registry,
)
from auto_invest.market_data.intraday import (
    CALENDAR,
    NY,
    SYMBOLS,
    DataError,
    digest,
    encode,
    iso,
    normalize,
    utc,
)
from auto_invest.market_data.intraday_pricing import limit_price

MODEL = "limit-next-5m-v1"
INITIAL = 100_000.0
COMMISSION = 0.0025
PARTICIPATION = 0.01


def _connect(path: Path, *, readonly=False):
    if path.is_symlink():
        raise DataError("STATE_SYMLINK_DENIED")
    if readonly:
        if not path.is_file():
            raise DataError("STATE_NOT_INITIALIZED")
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def _verify(conn):
    if conn.execute("PRAGMA user_version").fetchone()[0] != 181:
        raise DataError("FOREIGN_STATE_DATABASE")
    previous = "genesis"
    for row in conn.execute("SELECT * FROM intraday_events ORDER BY id"):
        payload = json.loads(row["payload"])
        if row["previous_hash"] != previous or row["hash"] != digest(encode([previous, payload])):
            raise DataError("AUDIT_INTEGRITY")
        if payload["timestamp"] != row["timestamp"]:
            raise DataError("AUDIT_TIMESTAMP")
        previous = row["hash"]


def _summary(conn):
    last = conn.execute("SELECT payload FROM intraday_events ORDER BY id DESC LIMIT 1").fetchone()
    state = json.loads(last[0])["state"] if last else {"accounts": {}, "halt_reasons": []}
    accounts = state["accounts"]
    halts = sorted(
        set(
            state["halt_reasons"]
            + [reason for account in accounts.values() for reason in account["halt_reasons"]]
        )
    )
    return dict(
        execution_model=MODEL,
        status="DIAGNOSTIC_PAPER" if not halts else "ENTRY_HALTED",
        processed_bars=conn.execute("SELECT COUNT(*) FROM intraday_events").fetchone()[0],
        last_bar=state.get("last_bar"),
        simulated_fills=sum(a["fills"] for a in accounts.values()),
        open_quantity=sum(sum(a["positions"].values()) for a in accounts.values()),
        accounts={
            k: {
                "cash": v["cash"],
                "positions": v["positions"],
                "fees_usd": v["fees_usd"],
                "halt_reasons": v["halt_reasons"],
                "nav_usd": round(
                    v["cash"] + sum(q * state["marks"][s] for s, q in v["positions"].items()), 8
                ),
                "net_pnl_usd": round(
                    v["cash"]
                    + sum(q * state["marks"][s] for s, q in v["positions"].items())
                    - INITIAL,
                    8,
                ),
            }
            for k, v in accounts.items()
        },
        halt_reasons=halts,
        live_eligible=False,
        forward_promotion_eligible=False,
        orders_submitted=0,
    )


def read_status(path: Path):
    conn = _connect(path, readonly=True)
    try:
        _verify(conn)
        return _summary(conn)
    finally:
        conn.close()


class PaperRuntime:
    def __init__(
        self, path: Path, preregistration: dict, provider: str, synthetic: bool, mode: str
    ):
        if mode not in {"replay", "forward"} or type(synthetic) is not bool or not provider:
            raise DataError("RUNTIME_IDENTITY")
        self.candidates = build_candidate_registry(preregistration)
        self.mode = mode
        self.identity = dict(
            model=MODEL,
            runtime_source=digest(Path(__file__).read_bytes()),
            signal_source=digest(
                Path(__file__).with_name("intraday_paper_challenger.py").read_bytes()
            ),
            pricing_source=digest(
                (Path(__file__).parents[1] / "market_data/intraday_pricing.py").read_bytes()
            ),
            config=digest(encode(preregistration)),
            provider=provider,
            synthetic=synthetic,
            mode=mode,
        )
        self.conn = _connect(path)
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            tables = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if not tables:
                self.conn.execute("PRAGMA user_version=181")
                self.conn.execute("CREATE TABLE intraday_meta(identity TEXT NOT NULL)")
                self.conn.execute(
                    "INSERT INTO intraday_meta VALUES(?)", (encode(self.identity).decode(),)
                )
                self.conn.execute(
                    "CREATE TABLE intraday_events(id INTEGER PRIMARY KEY, "
                    "timestamp TEXT UNIQUE NOT NULL, previous_hash TEXT NOT NULL, "
                    "hash TEXT NOT NULL, payload TEXT NOT NULL)"
                )
                for table in ("intraday_meta", "intraday_events"):
                    for operation in ("UPDATE", "DELETE"):
                        self.conn.execute(
                            f"CREATE TRIGGER {table}_{operation} BEFORE {operation} ON {table} "
                            "BEGIN SELECT RAISE(ABORT, 'append-only'); END"
                        )
            if {
                row[0]
                for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            } != {"intraday_meta", "intraday_events"}:
                raise DataError("FOREIGN_STATE_DATABASE")
            _verify(self.conn)
            identities = self.conn.execute("SELECT identity FROM intraday_meta").fetchall()
            if len(identities) != 1 or json.loads(identities[0][0]) != self.identity:
                raise DataError("RUNTIME_IDENTITY_MISMATCH")
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            self.conn.close()
            raise

    def close(self):
        self.conn.close()

    def status(self):
        return _summary(self.conn)

    def _initial(self):
        return dict(
            session=None,
            last_bar=None,
            halt_reasons=[],
            accounts={
                c.candidate_id: dict(
                    cash=INITIAL,
                    positions={s: 0 for s in SYMBOLS},
                    pending={},
                    entries={},
                    entered=[],
                    fills=0,
                    fees_usd=0.0,
                    halt_reasons=[],
                    session_nav=INITIAL,
                )
                for c in self.candidates
            },
        )

    def process(self, bars: list[dict], observed: datetime) -> bool:
        if len(bars) != 5 or {b.get("symbol") for b in bars} != set(SYMBOLS):
            raise DataError("BAR_COVERAGE")
        rows = {}
        for b in bars:
            row = normalize(
                b["symbol"],
                dict(
                    t=b["timestamp_utc"],
                    o=b["open"],
                    h=b["high"],
                    l=b["low"],
                    c=b["close"],
                    v=b["volume"],
                ),
                observed,
            )
            if row is None:
                raise DataError("BAR_NOT_CLOSED_REGULAR")
            rows[b["symbol"]] = row
        timestamps = {b["timestamp_utc"] for b in rows.values()}
        if len(timestamps) != 1:
            raise DataError("BAR_TIMESTAMP_MISMATCH")
        stamp = timestamps.pop()
        moment = utc(stamp)
        end = moment + timedelta(minutes=5)
        source_digest = digest(encode(rows))
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            old = conn.execute(
                "SELECT payload FROM intraday_events WHERE timestamp=?", (stamp,)
            ).fetchone()
            if old:
                if json.loads(old[0])["bar_digest"] != source_digest:
                    raise DataError("PROCESSED_BAR_REVISION")
                conn.commit()
                return False
            last = conn.execute("SELECT * FROM intraday_events ORDER BY id DESC LIMIT 1").fetchone()
            if last and stamp <= last["timestamp"]:
                raise DataError("OUT_OF_ORDER_BAR")
            state = json.loads(last["payload"])["state"] if last else self._initial()
            session = moment.astimezone(NY).date()
            opening = CALENDAR.session_open(session).to_pydatetime()
            closing = CALENDAR.session_close(session).to_pydatetime()
            history = []
            if state["session"] != str(session):
                state["halt_reasons"] = []
                for account in state["accounts"].values():
                    account["pending"] = {
                        s: o for s, o in account["pending"].items() if o["side"] == "SELL"
                    }
                    account["halt_reasons"] = (
                        ["OVERNIGHT_RESIDUAL"] if any(account["positions"].values()) else []
                    )
                    account["entered"] = []
                    account["session_nav"] = self._nav(account, rows)
                if moment != opening:
                    state["halt_reasons"].append("SESSION_START_MISSING")
            else:
                if moment != utc(state["last_bar"]) + timedelta(minutes=5):
                    state["halt_reasons"].append("DATA_GAP")
                history = [
                    json.loads(r[0])["bars"]
                    for r in conn.execute(
                        "SELECT payload FROM intraday_events WHERE timestamp>=? ORDER BY timestamp",
                        (iso(opening),),
                    )
                ]
            if self.mode == "forward" and observed - end > timedelta(seconds=90):
                state["halt_reasons"].append("STALE_BAR")
            state["halt_reasons"] = sorted(set(state["halt_reasons"]))
            history.append(rows)
            actions = []
            for candidate in self.candidates:
                account = state["accounts"][candidate.candidate_id]
                prior_marks = state.get("marks", {s: rows[s]["open"] for s in SYMBOLS})
                self._fill(
                    account,
                    rows,
                    moment,
                    bool(state["halt_reasons"] or account["halt_reasons"]),
                    actions,
                    candidate,
                    prior_marks,
                )
                if self._nav(account, rows) < account["session_nav"] * 0.98:
                    account["halt_reasons"] = sorted(
                        set(account["halt_reasons"] + ["PAPER_DAILY_LOSS"])
                    )
                for symbol in SYMBOLS:
                    series = self._aggregate(
                        history, symbol, candidate.timeframe_minutes, opening, closing
                    )
                    latest = series[-1]
                    signal_boundary = latest.complete and latest.end_utc == end
                    qty = account["positions"][symbol]
                    force_exit = end >= closing - timedelta(minutes=15) or bool(
                        state["halt_reasons"] or account["halt_reasons"]
                    )
                    exiting = account["pending"].get(symbol, {}).get("side") == "SELL"
                    if qty and (
                        force_exit
                        or exiting
                        or (
                            signal_boundary
                            and _exit_signal(
                                candidate,
                                series,
                                len(series) - 1,
                                account["entries"].get(symbol, 0),
                            )
                        )
                    ):
                        # Keep an existing liquidation limit after an unfilled/partial exit.
                        existing = account["pending"].get(symbol)
                        limit = (
                            existing["limit"]
                            if existing and existing["side"] == "SELL"
                            else float(limit_price(Decimal(str(rows[symbol]["close"])), buy=False))
                        )
                        account["pending"][symbol] = dict(
                            side="SELL", qty=qty, limit=limit, eligible=iso(end)
                        )
                    elif (
                        not qty
                        and not force_exit
                        and signal_boundary
                        and _entry_signal(candidate, series, len(series) - 1)
                    ):
                        if (
                            candidate.family == "opening_range_breakout"
                            and symbol in account["entered"]
                        ):
                            continue
                        limit = float(limit_price(Decimal(str(rows[symbol]["close"])), buy=True))
                        allocation = min(
                            self._nav(account, rows) * 0.16, account["cash"] / (1 + COMMISSION)
                        )
                        requested = math.floor(allocation / limit)
                        if requested:
                            account["pending"][symbol] = dict(
                                side="BUY", qty=requested, limit=limit, eligible=iso(end)
                            )
                    else:
                        continue
                    actions.append(
                        dict(
                            kind="ORDER",
                            candidate=candidate.candidate_id,
                            symbol=symbol,
                            **account["pending"][symbol],
                        )
                    )
            state.update(
                session=str(session), last_bar=stamp, marks={s: rows[s]["close"] for s in SYMBOLS}
            )
            previous = last["hash"] if last else "genesis"
            payload = dict(
                timestamp=stamp,
                observed=iso(observed),
                bar_digest=source_digest,
                bars=rows,
                actions=actions,
                state=state,
            )
            conn.execute(
                "INSERT INTO intraday_events(timestamp,previous_hash,hash,payload) VALUES(?,?,?,?)",
                (stamp, previous, digest(encode([previous, payload])), encode(payload).decode()),
            )
            conn.commit()
            return True
        except BaseException:
            conn.rollback()
            raise

    @staticmethod
    def _nav(account, rows):
        return account["cash"] + sum(q * rows[s]["close"] for s, q in account["positions"].items())

    @staticmethod
    def _aggregate(history, symbol, timeframe, opening, closing):
        buckets = {}
        for frame in history:
            row = frame[symbol]
            idx = int((utc(row["timestamp_utc"]) - opening).total_seconds() // (60 * timeframe))
            buckets.setdefault(idx, []).append(row)
        output = []
        for idx, values in buckets.items():
            start = utc(values[0]["timestamp_utc"])
            end = utc(values[-1]["timestamp_utc"]) + timedelta(minutes=5)
            output.append(
                ResampledBar(
                    symbol,
                    opening.astimezone(NY).date(),
                    start,
                    end,
                    timeframe,
                    idx,
                    values[0]["open"],
                    max(v["high"] for v in values),
                    min(v["low"] for v in values),
                    values[-1]["close"],
                    sum(v["volume"] for v in values),
                    len(values),
                    len(values) == timeframe // 5,
                    end < closing - timedelta(minutes=15),
                )
            )
        return output

    def _fill(self, account, rows, moment, halted, actions, candidate, prior_marks):
        for symbol, order in list(account["pending"].items()):
            bar = rows[symbol]
            side, limit = order["side"], order["limit"]
            del account["pending"][symbol]
            on_time = utc(order["eligible"]) == moment
            touched = bar["low"] <= limit if side == "BUY" else bar["high"] >= limit
            qty = (
                min(order["qty"], math.floor(bar["volume"] * PARTICIPATION))
                if on_time and touched
                else 0
            )
            if side == "BUY":
                exposure = sum(q * prior_marks[s] for s, q in account["positions"].items())
                nav = account["cash"] + exposure
                capacity = max(
                    0, min(nav * 0.2, nav * 0.8 - exposure, account["cash"] / (1 + COMMISSION))
                )
                qty = 0 if halted else min(qty, math.floor(capacity / limit))
            else:
                qty = min(qty, account["positions"][symbol])
            fee = qty * limit * COMMISSION
            if qty:
                sign = 1 if side == "BUY" else -1
                account["cash"] = round(account["cash"] - sign * qty * limit - fee, 8)
                account["positions"][symbol] += sign * qty
                account["fills"] += 1
                account["fees_usd"] = round(account["fees_usd"] + fee, 8)
                if side == "BUY":
                    opening = CALENDAR.session_open(moment.astimezone(NY).date()).to_pydatetime()
                    account["entries"][symbol] = int(
                        (moment - opening).total_seconds() // (candidate.timeframe_minutes * 60)
                    )
                    account["entered"].append(symbol)
            if side == "SELL" and account["positions"][symbol]:
                account["pending"][symbol] = copy.deepcopy(order)
            actions.append(
                dict(
                    kind="FILL" if qty else "UNFILLED",
                    candidate=candidate.candidate_id,
                    symbol=symbol,
                    side=side,
                    qty=qty,
                    limit=limit,
                    commission=fee,
                    requested=order["qty"],
                    eligible=order["eligible"],
                )
            )
