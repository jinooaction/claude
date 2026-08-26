from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.backtest.data_source import trading_days_between
from auto_invest.portfolio.execution_proxy_parity import (
    PREREGISTERED_EXECUTION_SYMBOL_MAP,
    assess_execution_proxy_parity,
    validate_execution_proxy_parity_evidence,
)


@dataclass
class _DataSource:
    bars: dict[str, list[OHLCVBar]]

    @property
    def dataset_version(self) -> str:
        return "proxy-test"

    def list_symbols(self) -> list[str]:
        return sorted(self.bars)

    def session_dates(self, symbol: str) -> list[date]:
        return [bar.session_date for bar in self.bars.get(symbol, [])]

    def coverage_holes(self, symbols, date_start, date_end):  # noqa: ANN001
        expected = set(trading_days_between(date_start, date_end))
        return [
            (symbol, session)
            for symbol in symbols
            for session in sorted(expected - set(self.session_dates(symbol)))
        ]

    def read_bars(self, symbol: str, date_start: date, date_end: date) -> list[OHLCVBar]:
        return [
            bar
            for bar in self.bars.get(symbol, [])
            if date_start <= bar.session_date <= date_end
        ]


def _source(*, break_pair: str | None = None, stale_days: int = 0) -> tuple[_DataSource, datetime]:
    observed_at = datetime(2026, 8, 27, 12, tzinfo=UTC)
    sessions = trading_days_between(date(2025, 8, 1), date(2026, 8, 27))[-260:]
    if stale_days:
        sessions = [session - timedelta(days=stale_days) for session in sessions]
    bars: dict[str, list[OHLCVBar]] = {}
    for pair_index, (signal, execution) in enumerate(
        PREREGISTERED_EXECUTION_SYMBOL_MAP.items()
    ):
        signal_price = Decimal(str(80 + pair_index * 20))
        execution_price = Decimal(str(25 + pair_index * 10))
        signal_rows: list[OHLCVBar] = []
        execution_rows: list[OHLCVBar] = []
        for index, session in enumerate(sessions):
            base_return = Decimal(str(0.0004 + 0.006 * ((index % 11) - 5) / 5))
            signal_price *= Decimal("1") + base_return
            if break_pair == signal:
                proxy_return = Decimal("0.02") if index % 2 else Decimal("-0.02")
            else:
                proxy_return = base_return + Decimal(str(((index % 3) - 1) * 0.00005))
            execution_price *= Decimal("1") + proxy_return
            signal_rows.append(_bar(signal, session, signal_price, 2_000_000))
            execution_rows.append(_bar(execution, session, execution_price, 3_000_000))
        bars[signal] = signal_rows
        bars[execution] = execution_rows
    return _DataSource(bars), observed_at


def _bar(symbol: str, session: date, close: Decimal, volume: int) -> OHLCVBar:
    return OHLCVBar(
        symbol=symbol,
        session_date=session,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
        session_schedule_tag="regular",
    )


def test_preregistered_pairs_pass_and_self_validate() -> None:
    source, observed_at = _source()
    evidence = assess_execution_proxy_parity(
        source,
        symbol_map=PREREGISTERED_EXECUTION_SYMBOL_MAP,
        observed_at=observed_at,
    )

    assert evidence.passed is True
    assert len(evidence.pairs) == 3
    assert validate_execution_proxy_parity_evidence(
        evidence.as_dict(),
        expected_symbol_map=PREREGISTERED_EXECUTION_SYMBOL_MAP,
        now=observed_at,
    )


def test_low_correlation_pair_fails_closed() -> None:
    source, observed_at = _source(break_pair="IEF")
    evidence = assess_execution_proxy_parity(
        source,
        symbol_map=PREREGISTERED_EXECUTION_SYMBOL_MAP,
        observed_at=observed_at,
    )

    assert evidence.passed is False
    pair = next(row for row in evidence.pairs if row.signal_symbol == "IEF")
    assert pair.checks["return_correlation"] is False


def test_wrong_mapping_stale_data_and_mutation_are_rejected() -> None:
    source, observed_at = _source()
    evidence = assess_execution_proxy_parity(
        source,
        symbol_map=PREREGISTERED_EXECUTION_SYMBOL_MAP,
        observed_at=observed_at,
    ).as_dict()

    wrong_mapping = dict(PREREGISTERED_EXECUTION_SYMBOL_MAP)
    wrong_mapping["SPY"] = "SPYM"
    assert not validate_execution_proxy_parity_evidence(
        evidence, expected_symbol_map=wrong_mapping, now=observed_at
    )

    assert not validate_execution_proxy_parity_evidence(
        evidence,
        expected_symbol_map=PREREGISTERED_EXECUTION_SYMBOL_MAP,
        now=observed_at + timedelta(hours=37),
    )

    evidence["pairs"][0]["return_correlation"] = 0.1
    assert not validate_execution_proxy_parity_evidence(
        evidence,
        expected_symbol_map=PREREGISTERED_EXECUTION_SYMBOL_MAP,
        now=observed_at,
    )


def test_old_market_data_fails_even_when_metrics_are_close() -> None:
    source, observed_at = _source(stale_days=10)
    evidence = assess_execution_proxy_parity(
        source,
        symbol_map=PREREGISTERED_EXECUTION_SYMBOL_MAP,
        observed_at=observed_at,
    )

    assert evidence.passed is False
    assert all(pair.checks["freshness"] is False for pair in evidence.pairs)

