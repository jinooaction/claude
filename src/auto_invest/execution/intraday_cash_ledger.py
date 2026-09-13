"""Recompute net cash from a trusted reader's complete cash-event stream.

This is an in-process normalization contract, not a KIS wire format or an
operator-supplied proof. The reader must separately establish account, currency,
scope and source completeness. A valid running balance alone cannot prove them.
"""

import re
from datetime import UTC, datetime
from decimal import Decimal, localcontext

KINDS = frozenset({
    "SETTLEMENT", "TRANSFER", "FX", "DIVIDEND", "INTEREST", "FEE",
    "LIABILITY_ADJUSTMENT",
})


class CashLedgerError(ValueError):
    """Closed reasons; no account data in exception messages."""


def _amount(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]{1,18}(\.[0-9]{1,12})?", value):
        raise CashLedgerError("CASH_LEDGER_AMOUNT_INVALID")
    return Decimal(value)


def _time(value):
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except Exception:
        raise CashLedgerError("CASH_LEDGER_TIME_INVALID") from None


def _sequence(value):
    if type(value) is not int or not 0 <= value <= 10**18:
        raise CashLedgerError("CASH_LEDGER_SEQUENCE_INVALID")
    return value


def compute_net_cash(ledger, *, observation_started_at, observation_completed_at):
    """Return a Decimal after replaying every signed net-cash change exactly.

Balances and deltas include outstanding liabilities and unsettled amounts;
execution cash remains a separate observation. Never add fees again when the
settlement delta already includes them. Sequence numbers must be original
source counters, never numbers generated after filtering or sorting rows.
"""
    if not isinstance(ledger, dict) or ledger.get("currency") != "USD":
        raise CashLedgerError("CASH_LEDGER_CURRENCY_OR_SHAPE")
    opening = ledger.get("opening")
    closing = ledger.get("closing")
    events = ledger.get("events")
    if (not isinstance(opening, dict) or not isinstance(closing, dict)
            or not isinstance(events, list) or len(events) > 100000):
        raise CashLedgerError("CASH_LEDGER_SHAPE_INVALID")
    previous_time, closing_time = _time(opening.get("at")), _time(closing.get("at"))
    started, completed = _time(observation_started_at), _time(observation_completed_at)
    if not previous_time <= closing_time or not started <= closing_time <= completed:
        raise CashLedgerError("CASH_LEDGER_SNAPSHOT_TIME_INVALID")
    sequence = _sequence(opening.get("sequence"))
    final_sequence = _sequence(closing.get("sequence"))
    if final_sequence - sequence != len(events):
        raise CashLedgerError("CASH_LEDGER_SEQUENCE_INVALID")
    total = _amount(opening.get("net_cash"))
    seen = set()
    with localcontext() as context:
        context.prec = 80
        for event in events:
            if not isinstance(event, dict) or event.get("currency") != "USD":
                raise CashLedgerError("CASH_LEDGER_EVENT_INVALID")
            identity = event.get("id")
            if (not isinstance(identity, str)
                    or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", identity)
                    or identity in seen):
                raise CashLedgerError("CASH_LEDGER_EVENT_ID_INVALID")
            seen.add(identity)
            kind = event.get("kind")
            if not isinstance(kind, str) or kind not in KINDS:
                raise CashLedgerError("CASH_LEDGER_EVENT_KIND_INVALID")
            sequence += 1
            if _sequence(event.get("sequence")) != sequence:
                raise CashLedgerError("CASH_LEDGER_SEQUENCE_INVALID")
            stamp = _time(event.get("at"))
            if not previous_time <= stamp <= closing_time:
                raise CashLedgerError("CASH_LEDGER_EVENT_TIME_INVALID")
            previous_time = stamp
            total += _amount(event.get("net_cash_delta"))
            if total != _amount(event.get("net_cash_after")):
                raise CashLedgerError("CASH_LEDGER_RUNNING_BALANCE_MISMATCH")
        if total != _amount(closing.get("net_cash")):
            raise CashLedgerError("CASH_LEDGER_CLOSING_BALANCE_MISMATCH")
    return total
