"""Compile existing preregistered signals using confirmed broker holdings."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from auto_invest.analytics.intraday_paper_challenger import _entry_signal, _exit_signal
from auto_invest.analytics.intraday_runtime import PaperRuntime
from auto_invest.execution.intraday import Decision
from auto_invest.market_data.intraday import CALENDAR, NY, SYMBOLS, normalize, utc
from auto_invest.market_data.intraday_pricing import limit_price


def execution_fingerprint(candidate, provider):
    if provider != "kis-nasdaq-partial-unadjusted":
        raise ValueError("EXECUTION_PROVIDER")
    sources = [
        Path(__file__),
        Path(__file__).with_name("intraday.py"),
        Path(__file__).with_name("intraday_runtime.py"),
        Path(__file__).with_name("intraday_observation.py"),
        Path(__file__).with_name("intraday_selection.py"),
        Path(__file__).with_name("intraday_program.py"),
        Path(__file__).with_name("intraday_forward.py"),
        Path(__file__).with_name("intraday_registration.py"),
        Path(__file__).parents[1] / "analytics/intraday_paper_challenger.py",
        Path(__file__).parents[1] / "analytics/intraday_runtime.py",
        Path(__file__).parents[1] / "market_data/intraday_pricing.py",
    ]
    identity = dict(
        candidate=candidate.as_dict(),
        provider=provider,
        sources=[hashlib.sha256(p.read_bytes()).hexdigest() for p in sources],
    )
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def compile_decision(
    candidate, *, provider, bars, now, owned, entry_times, entered_symbols, capital, cash
):
    """Never use the paper account's simulated positions to size real orders."""
    if not bars:
        raise ValueError("MISSING_BARS")
    session = now.astimezone(NY).date()
    if not CALENDAR.is_session(str(session)):
        raise ValueError("MARKET_CLOSED")
    opening = CALENDAR.session_open(str(session)).to_pydatetime()
    closing = CALENDAR.session_close(str(session)).to_pydatetime()
    frames = {}
    for row in bars:
        symbol = row["symbol"]
        if symbol not in SYMBOLS:
            raise ValueError("SIGNAL_UNIVERSE")
        value = normalize(
            symbol,
            dict(
                t=row["timestamp_utc"],
                o=row["open"],
                h=row["high"],
                l=row["low"],
                c=row["close"],
                v=row["volume"],
            ),
            now,
        )
        if value is None:
            raise ValueError("UNFINISHED_SIGNAL_BAR")
        stamp = value["timestamp_utc"]
        if symbol in frames.setdefault(stamp, {}):
            raise ValueError("DUPLICATE_SIGNAL_BAR")
        frames[stamp][symbol] = value
    history = []
    for index, stamp in enumerate(sorted(frames)):
        if utc(stamp) != opening + timedelta(minutes=index * 5) or set(frames[stamp]) != set(
            SYMBOLS
        ):
            raise ValueError("SIGNAL_BAR_GAP")
        history.append(frames[stamp])
    end = utc(sorted(frames)[-1]) + timedelta(minutes=5)
    if not 0 <= (now - end).total_seconds() <= 90:
        raise ValueError("STALE_SIGNAL")
    if not isinstance(capital, Decimal) or not capital.is_finite() or capital < 0:
        raise ValueError("INVALID_CAPITAL")
    if not isinstance(cash, Decimal) or not cash.is_finite() or cash < 0:
        raise ValueError("INVALID_CASH")
    targets, limits = {}, {}
    for symbol in SYMBOLS:
        qty = owned.get(symbol, 0)
        if type(qty) is not int or qty < 0:
            raise ValueError("OWNERSHIP_MISMATCH")
        targets[symbol] = qty
        series = PaperRuntime._aggregate(
            history, symbol, candidate.timeframe_minutes, opening, closing
        )
        boundary = series[-1].complete and series[-1].end_utc == end
        price = Decimal(str(history[-1][symbol]["close"]))
        exit_signal = end >= closing - timedelta(minutes=15)
        if qty:
            if symbol not in entry_times:
                raise ValueError("ENTRY_TIME_MISSING")
            entry = entry_times[symbol]
            if entry.tzinfo is None or entry > now:
                raise ValueError("ENTRY_TIME_INVALID")
            entry_index = max(
                0, int((entry - opening).total_seconds() // (60 * candidate.timeframe_minutes))
            )
            exit_signal = (
                exit_signal
                or entry < opening
                or (boundary and _exit_signal(candidate, series, len(series) - 1, entry_index))
            )
        if qty and exit_signal:
            targets[symbol] = 0
        elif (
            not qty
            and not exit_signal
            and boundary
            and not (candidate.family == "opening_range_breakout" and symbol in entered_symbols)
            and _entry_signal(candidate, series, len(series) - 1)
        ):
            limit = limit_price(price, buy=True)
            notional = min(capital * Decimal(".16"), cash / Decimal("1.003"))
            targets[symbol] = int(notional / limit)
            cash -= targets[symbol] * limit * Decimal("1.003")
        buying = targets[symbol] > qty
        limits[symbol] = limit_price(price, buy=buying)
    return Decision(execution_fingerprint(candidate, provider), end, targets, limits)
