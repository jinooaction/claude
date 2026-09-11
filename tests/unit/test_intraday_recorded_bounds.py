import copy
import json
from datetime import datetime

import pytest

from auto_invest.execution.intraday_execution_evidence import _recorded_upper_bound


@pytest.mark.parametrize("change", [None, "legacy", "partial", "duplicate", "quantity",
                                    "price", "future", "early", "naive", "other_order"])
def test_partial_fill_bounds_require_every_matching_receipt(change):
    order = dict(correlation_id="order", symbol="SPY", rule_id="strategy")
    fills = [dict(order_correlation_id="order", kis_fill_id=f"fill-{n}", qty=1,
                  price_usd="100") for n in range(2)]
    events = [dict(kis_fill_id=f"fill-{n}", qty=1, price_usd="100",
                   broker_response_received_at_utc=f"2026-09-10T14:0{n + 2}:00+00:00")
              for n in range(2)]
    if change == "legacy":
        events[0].pop("broker_response_received_at_utc")
        events[0]["observed_at_utc"] = "2026-09-10T14:01:00Z"
    if change == "partial":
        events.pop()
    if change == "duplicate":
        events[1] = copy.deepcopy(events[0])
    if change == "quantity":
        events[0]["qty"] = 2
    if change == "price":
        events[0]["price_usd"] = "101"
    stamps = dict(future="2026-09-12T00:00:00Z", early="2026-09-10T13:59:00Z",
                  naive="2026-09-10T14:02:00")
    if change in stamps:
        events[0]["broker_response_received_at_utc"] = stamps[change]
    audits = [dict(order, payload_json=json.dumps(event)) for event in events]
    if change == "other_order":
        audits[0]["correlation_id"] = "other"
    ledger = dict(fills=fills, fill_audits=audits)
    before = copy.deepcopy(ledger)
    current = "2026-09-11T14:00:00+00:00"
    result = _recorded_upper_bound(ledger, order,
                                  datetime.fromisoformat("2026-09-10T14:00:00+00:00"), current)
    assert result == ("2026-09-10T14:03:00+00:00" if change is None else current)
    assert ledger == before
