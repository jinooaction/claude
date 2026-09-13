from copy import deepcopy
from decimal import Decimal, localcontext

import pytest

from auto_invest.execution.intraday_cash_ledger import CashLedgerError, compute_net_cash

NOW = "2026-09-10T12:00:00+00:00"


def ledger():
    balance = Decimal("600")
    events = []
    for index, (kind, delta) in enumerate([
        ("SETTLEMENT", "-40.1"), ("TRANSFER", "100"), ("FX", "25.123456789012"),
        ("DIVIDEND", "1"), ("INTEREST", "0.01"), ("FEE", "-0.02"),
        ("LIABILITY_ADJUSTMENT", "-700"),
    ], 11):
        balance += Decimal(delta)
        events.append(dict(id=f"original-{index}", sequence=index, kind=kind, currency="USD",
                           at=NOW, net_cash_delta=delta, net_cash_after=str(balance)))
    return dict(currency="USD", opening=dict(sequence=10, at=NOW, net_cash="600"),
                closing=dict(sequence=17, at=NOW, net_cash=str(balance)), events=events)


def calculate(raw):
    return compute_net_cash(raw, observation_started_at=NOW, observation_completed_at=NOW)


def test_all_cash_movements_exact_and_read_only_even_with_small_decimal_context():
    raw = ledger()
    before = deepcopy(raw)
    with localcontext() as context:
        context.prec = 2
        assert calculate(raw) == Decimal("-13.986543210988")
    assert raw == before
    assert calculate(raw) == Decimal("-13.986543210988")


@pytest.mark.parametrize("change,reason", [
    ("gap", "SEQUENCE_INVALID"), ("duplicate", "EVENT_ID_INVALID"),
    ("reorder", "SEQUENCE_INVALID"), ("counter_bool", "SEQUENCE_INVALID"),
    ("foreign", "EVENT_INVALID"), ("unknown", "EVENT_KIND_INVALID"),
    ("nan", "AMOUNT_INVALID"), ("float", "AMOUNT_INVALID"),
    ("running", "RUNNING_BALANCE_MISMATCH"), ("closing", "CLOSING_BALANCE_MISMATCH"),
    ("stale", "SNAPSHOT_TIME_INVALID"), ("future", "EVENT_TIME_INVALID"),
    ("naive", "TIME_INVALID"), ("reverse_time", "EVENT_TIME_INVALID"),
])
def test_incomplete_or_inconsistent_original_records_are_rejected(change, reason):
    raw = ledger()
    if change == "gap":
        del raw["events"][2]
    elif change == "duplicate":
        raw["events"][1]["id"] = raw["events"][0]["id"]
    elif change == "reorder":
        raw["events"].reverse()
    elif change == "counter_bool":
        raw["closing"]["sequence"] = True
    elif change == "foreign":
        raw["events"][0]["currency"] = "KRW"
    elif change == "unknown":
        raw["events"][0]["kind"] = "UNMAPPED_SOURCE_KIND"
    elif change == "nan":
        raw["events"][0]["net_cash_delta"] = "NaN"
    elif change == "float":
        raw["events"][0]["net_cash_delta"] = -40.1
    elif change == "running":
        raw["events"][0]["net_cash_after"] = "560"
    elif change == "closing":
        raw["closing"]["net_cash"] = "600"
    elif change == "stale":
        raw["closing"]["at"] = "2026-09-10T11:59:59+00:00"
    elif change == "future":
        raw["events"][0]["at"] = "2026-09-10T12:00:01+00:00"
    elif change == "naive":
        raw["opening"]["at"] = "2026-09-10T12:00:00"
    elif change == "reverse_time":
        raw["events"][1]["at"] = "2026-09-10T11:59:59+00:00"
    with pytest.raises(CashLedgerError, match=reason):
        calculate(raw)


def test_no_movement_requires_same_original_counter_and_balance():
    raw = ledger()
    raw["events"] = []
    raw["closing"] = dict(raw["opening"])
    assert calculate(raw) == 600
    raw["closing"]["sequence"] += 1
    with pytest.raises(CashLedgerError, match="SEQUENCE_INVALID"):
        calculate(raw)
