import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.analytics.intraday_paper_challenger import load_preregistration
from auto_invest.analytics.intraday_runtime import PaperRuntime
from auto_invest.execution.intraday_signals import compile_decision, execution_fingerprint
from auto_invest.market_data.intraday import CALENDAR, SYMBOLS, DataError, iso
from auto_invest.market_data.intraday_pricing import limit_price

PREREG = Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")
PROVIDER = "kis-nasdaq-partial-unadjusted"


@pytest.mark.parametrize("mark,buy,sell", [
    ("50", "50.03", "49.97"), ("100", "100.06", "99.94"),
    ("200", "200.12", "199.88"), ("250", "250.15", "249.85"),
    ("25", "25.01", "24.99"),
])
def test_exact_cent_boundaries(mark, buy, sell):
    assert limit_price(Decimal(mark), buy=True) == Decimal(buy)
    assert limit_price(Decimal(mark), buy=False) == Decimal(sell)


def test_paper_and_execution_produce_same_limit_and_boundary_fill(tmp_path):
    opening = CALENDAR.session_open("2026-09-09").to_pydatetime()
    runtime = PaperRuntime(tmp_path / "paper.db", load_preregistration(PREREG),
                           PROVIDER, False, "forward")
    history = []
    candidate = runtime.candidates[0]
    found = False
    try:
        for n in range(15):
            stamp = opening + timedelta(minutes=5 * n)
            bars = [dict(symbol=s, timestamp_utc=iso(stamp), open=100, high=101,
                         low=99, close=100, volume=100000) for s in SYMBOLS]
            history.extend(bars)
            runtime.process(bars, stamp + timedelta(minutes=5))
            payload = json.loads(runtime.conn.execute(
                "SELECT payload FROM intraday_events ORDER BY id DESC LIMIT 1"
            ).fetchone()[0])
            account = payload["state"]["accounts"][candidate.candidate_id]
            if not account["pending"]:
                continue
            order = account["pending"]["SPY"]
            assert order["side"] == "BUY" and order["limit"] == 100.06
            decision = compile_decision(
                candidate, provider=PROVIDER, bars=history, now=stamp + timedelta(minutes=5),
                owned={}, entry_times={}, entered_symbols=set(),
                capital=Decimal("100000"), cash=Decimal("100000"),
            )
            assert decision.limits["SPY"] == Decimal(str(order["limit"]))
            assert decision.targets["SPY"] == order["qty"]
            # The previous erroneous 100.05 limit would not touch this bar.
            next_stamp = stamp + timedelta(minutes=5)
            next_bars = [dict(symbol=s, timestamp_utc=iso(next_stamp), open=100.1,
                              high=100.2, low=100.055, close=100.1, volume=100000)
                         for s in SYMBOLS]
            runtime.process(next_bars, next_stamp + timedelta(minutes=5))
            after = json.loads(runtime.conn.execute(
                "SELECT payload FROM intraday_events ORDER BY id DESC LIMIT 1"
            ).fetchone()[0])
            assert after["state"]["accounts"][candidate.candidate_id]["positions"]["SPY"] > 0
            found = True
            break
        assert found
    finally:
        runtime.close()


def test_pricing_source_change_invalidates_both_models(tmp_path, monkeypatch):
    config = load_preregistration(PREREG)
    path = tmp_path / "paper.db"
    runtime = PaperRuntime(path, config, PROVIDER, False, "forward")
    candidate = runtime.candidates[0]
    before = execution_fingerprint(candidate, PROVIDER)
    runtime.close()
    original = Path.read_bytes

    def changed(path):
        return original(path) + (b"\n# changed" if path.name == "intraday_pricing.py" else b"")

    monkeypatch.setattr(Path, "read_bytes", changed)
    assert execution_fingerprint(candidate, PROVIDER) != before
    with pytest.raises(DataError, match="RUNTIME_IDENTITY_MISMATCH"):
        PaperRuntime(path, config, PROVIDER, False, "forward")
