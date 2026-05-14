"""T031 — synthetic shock date resolver + TOML loader tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from auto_invest.backtest.synthetic_shocks import (
    DEFAULT_CONFIG_PATH,
    SyntheticShockConfigError,
    _third_friday,
    most_recent_quarterly_opex,
    resolve_synthetic_shock_dates,
    shock_window,
)

# ---------- third Friday arithmetic -------------------------------------


@pytest.mark.parametrize(
    "year,month,expected",
    [
        # Hand-checked OPEX dates.
        (2024, 1, date(2024, 1, 19)),
        (2024, 3, date(2024, 3, 15)),
        (2024, 6, date(2024, 6, 21)),
        (2024, 9, date(2024, 9, 20)),
        (2024, 12, date(2024, 12, 20)),
        (2026, 3, date(2026, 3, 20)),
    ],
)
def test_third_friday_hand_checked(year: int, month: int, expected: date) -> None:
    assert _third_friday(year, month) == expected


# ---------- most_recent_quarterly_opex ---------------------------------


def test_opex_today_mid_year_returns_prior_quarter() -> None:
    """today=2026-05-13 → most recent completed quarterly OPEX is 2026-03-20."""
    assert most_recent_quarterly_opex(today=date(2026, 5, 13)) == date(2026, 3, 20)


def test_opex_just_before_june_opex_still_returns_march() -> None:
    """today=2026-06-18 (Thursday before June OPEX 2026-06-19) → March OPEX."""
    assert most_recent_quarterly_opex(today=date(2026, 6, 18)) == date(2026, 3, 20)


def test_opex_on_third_friday_returns_prior_quarter() -> None:
    """today == OPEX day → "most recently COMPLETED" excludes today itself."""
    # March 2026 OPEX = 2026-03-20 (Friday). today=that day → prior quarter = 2025-12-19.
    result = most_recent_quarterly_opex(today=date(2026, 3, 20))
    assert result < date(2026, 3, 20)
    assert result == date(2025, 12, 19)


def test_opex_after_dec_opex_returns_dec() -> None:
    """today=2026-12-30 (after Dec OPEX 2026-12-18) → Dec 2026 OPEX."""
    assert most_recent_quarterly_opex(today=date(2026, 12, 30)) == date(2026, 12, 18)


# ---------- resolve_synthetic_shock_dates -----------------------------


_FIXTURE_TOML = """\
[[shocks]]
name = "covid_circuit_breakers_2020_03_12"
session_date = "2020-03-12"
expected_gate_trip = "exchange_halt_or_volatility"

[[shocks]]
name = "negative_oil_futures_2020_04_20"
session_date = "2020-04-20"

[[shocks]]
name = "yen_carry_unwind_2024_08_05"
session_date = "2024-08-05"
expected_gate_trip = "global_exposure"

[[shocks]]
name = "most_recent_quarterly_opex"
session_date = "DYNAMIC"
"""


def test_resolve_replaces_dynamic_entry(tmp_path: Path) -> None:
    cfg = tmp_path / "shocks.toml"
    cfg.write_text(_FIXTURE_TOML)
    resolved = resolve_synthetic_shock_dates(today=date(2026, 5, 13), path=cfg)
    assert len(resolved) == 4
    names = [s.name for s in resolved]
    assert "most_recent_quarterly_opex" in names
    dyn = next(s for s in resolved if s.name == "most_recent_quarterly_opex")
    assert dyn.session_date == date(2026, 3, 20)


def test_resolve_preserves_declaration_order(tmp_path: Path) -> None:
    cfg = tmp_path / "shocks.toml"
    cfg.write_text(_FIXTURE_TOML)
    resolved = resolve_synthetic_shock_dates(today=date(2026, 5, 13), path=cfg)
    assert [s.name for s in resolved] == [
        "covid_circuit_breakers_2020_03_12",
        "negative_oil_futures_2020_04_20",
        "yen_carry_unwind_2024_08_05",
        "most_recent_quarterly_opex",
    ]


def test_resolve_static_entries_pass_through(tmp_path: Path) -> None:
    cfg = tmp_path / "shocks.toml"
    cfg.write_text(_FIXTURE_TOML)
    resolved = resolve_synthetic_shock_dates(today=date(2026, 5, 13), path=cfg)
    covid = next(s for s in resolved if s.name.startswith("covid_"))
    assert covid.session_date == date(2020, 3, 12)
    assert covid.expected_gate_trip == "exchange_halt_or_volatility"


def test_resolve_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SyntheticShockConfigError, match="not found"):
        resolve_synthetic_shock_dates(today=date(2026, 5, 13), path=tmp_path / "nope.toml")


def test_resolve_empty_shocks_section_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "shocks.toml"
    cfg.write_text("# no shocks here\n")
    with pytest.raises(SyntheticShockConfigError, match="no \\[\\[shocks\\]\\] entries"):
        resolve_synthetic_shock_dates(today=date(2026, 5, 13), path=cfg)


def test_resolve_bad_date_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "shocks.toml"
    cfg.write_text(
        '[[shocks]]\nname="bad"\nsession_date="not-a-date"\n'
    )
    with pytest.raises(SyntheticShockConfigError, match="not ISO-8601"):
        resolve_synthetic_shock_dates(today=date(2026, 5, 13), path=cfg)


# ---------- shock_window ------------------------------------------------


def test_shock_window_returns_30_trading_day_lookback() -> None:
    from auto_invest.backtest.data_model import SyntheticShockDay

    s = SyntheticShockDay(name="x", session_date=date(2024, 8, 5))
    start, end = shock_window(s, lookback_bars=30)
    assert end == date(2024, 8, 5)
    # 30 trading days back from Aug 5 lands in late June.
    assert start < date(2024, 7, 1)
    assert start > date(2024, 6, 15)


# ---------- project's own synthetic_shocks.toml validates -------------


def test_project_synthetic_shocks_toml_resolves_cleanly() -> None:
    """The checked-in config/synthetic_shocks.toml resolves under today's date.

    Skipped if not running from project root (path is relative to cwd).
    """
    if not DEFAULT_CONFIG_PATH.exists():
        pytest.skip("config/synthetic_shocks.toml not present in test CWD")
    resolved = resolve_synthetic_shock_dates(today=date(2026, 5, 13))
    assert len(resolved) == 4
    # All resolved dates must be real ISO dates (DYNAMIC replaced).
    for s in resolved:
        assert isinstance(s.session_date, date)
