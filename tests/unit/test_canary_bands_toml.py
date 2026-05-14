"""Spec 007 T009 — `config/canary_bands.toml` loader contract.

Covers `contracts/canary-bands-toml.md` line-by-line: defaults round-trip,
hard-pin enforcement on the two count metrics, FR-C02 minimum
`trading_days`, negative-band rejection, unknown-tier rejection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_invest.canary.bands import (
    DEFAULT_PATH,
    CanaryBandsConfigError,
    load_bands,
)


@pytest.fixture
def write_bands(tmp_path: Path):
    def _w(body: str) -> Path:
        p = tmp_path / "canary_bands.toml"
        p.write_text(body, encoding="utf-8")
        return p

    return _w


# ---------------------------------------------------------- shipped defaults


def test_shipped_defaults_load_clean() -> None:
    bands = load_bands(DEFAULT_PATH)
    assert set(bands.keys()) == {"L2", "L3"}

    l2 = bands["L2"]
    assert l2.trading_days == 30
    assert l2.pnl_drawdown_pct == pytest.approx(3.0)
    assert l2.risk_gate_violations == 0
    assert l2.audit_integrity_failures == 0
    assert l2.latency_p95_regression_pct == pytest.approx(20.0)
    assert l2.llm_cost_regression_pct == pytest.approx(10.0)

    l3 = bands["L3"]
    assert l3.trading_days == 45
    assert l3.pnl_drawdown_pct == pytest.approx(2.0)
    assert l3.latency_p95_regression_pct == pytest.approx(15.0)
    assert l3.llm_cost_regression_pct == pytest.approx(7.5)


# ---------------------------------------------------------- pinned-at-0 enforcement


def test_risk_gate_violations_must_equal_zero(write_bands) -> None:
    p = write_bands(
        """
[L2]
trading_days = 30
pnl_drawdown_pct = 3.0
risk_gate_violations = 1
audit_integrity_failures = 0
latency_p95_regression_pct = 20.0
llm_cost_regression_pct = 10.0
"""
    )
    with pytest.raises(CanaryBandsConfigError, match="risk_gate_violations"):
        load_bands(p)


def test_audit_integrity_failures_must_equal_zero(write_bands) -> None:
    p = write_bands(
        """
[L2]
trading_days = 30
pnl_drawdown_pct = 3.0
risk_gate_violations = 0
audit_integrity_failures = 2
latency_p95_regression_pct = 20.0
llm_cost_regression_pct = 10.0
"""
    )
    with pytest.raises(CanaryBandsConfigError, match="audit_integrity_failures"):
        load_bands(p)


# ---------------------------------------------------------- FR-C02 minimum window


def test_l2_below_30_trading_days_rejected(write_bands) -> None:
    p = write_bands(
        """
[L2]
trading_days = 29
pnl_drawdown_pct = 3.0
risk_gate_violations = 0
audit_integrity_failures = 0
latency_p95_regression_pct = 20.0
llm_cost_regression_pct = 10.0
"""
    )
    with pytest.raises(CanaryBandsConfigError, match="below FR-C02 minimum"):
        load_bands(p)


def test_l3_below_45_trading_days_rejected(write_bands) -> None:
    p = write_bands(
        """
[L3]
trading_days = 44
pnl_drawdown_pct = 2.0
risk_gate_violations = 0
audit_integrity_failures = 0
latency_p95_regression_pct = 15.0
llm_cost_regression_pct = 7.5
"""
    )
    with pytest.raises(CanaryBandsConfigError, match="below FR-C02 minimum"):
        load_bands(p)


# ---------------------------------------------------------- negative-band rejection


def test_negative_drawdown_band_rejected(write_bands) -> None:
    p = write_bands(
        """
[L2]
trading_days = 30
pnl_drawdown_pct = -1.0
risk_gate_violations = 0
audit_integrity_failures = 0
latency_p95_regression_pct = 20.0
llm_cost_regression_pct = 10.0
"""
    )
    with pytest.raises(CanaryBandsConfigError, match="must be >= 0"):
        load_bands(p)


# ---------------------------------------------------------- unknown-tier rejection


def test_unknown_tier_rejected(write_bands) -> None:
    p = write_bands(
        """
[L9]
trading_days = 30
pnl_drawdown_pct = 3.0
risk_gate_violations = 0
audit_integrity_failures = 0
latency_p95_regression_pct = 20.0
llm_cost_regression_pct = 10.0
"""
    )
    with pytest.raises(CanaryBandsConfigError, match="unknown tier 'L9'"):
        load_bands(p)


def test_l4_accepted_forward_compatible(write_bands) -> None:
    """R-C10 — L4 is reserved for spec 005 / IX.A future use; loader should accept."""
    p = write_bands(
        """
[L4]
trading_days = 60
pnl_drawdown_pct = 1.0
risk_gate_violations = 0
audit_integrity_failures = 0
latency_p95_regression_pct = 10.0
llm_cost_regression_pct = 5.0
"""
    )
    bands = load_bands(p)
    assert "L4" in bands
    assert bands["L4"].trading_days == 60


# ---------------------------------------------------------- structural failures


def test_empty_file_rejected(write_bands) -> None:
    p = write_bands("")
    with pytest.raises(CanaryBandsConfigError, match="empty bands file"):
        load_bands(p)


def test_missing_key_rejected(write_bands) -> None:
    p = write_bands(
        """
[L2]
trading_days = 30
pnl_drawdown_pct = 3.0
# risk_gate_violations missing
audit_integrity_failures = 0
latency_p95_regression_pct = 20.0
llm_cost_regression_pct = 10.0
"""
    )
    with pytest.raises(CanaryBandsConfigError, match="L2"):
        load_bands(p)


def test_malformed_toml_rejected(write_bands) -> None:
    p = write_bands("not = valid = toml")
    with pytest.raises(CanaryBandsConfigError, match="invalid TOML"):
        load_bands(p)


def test_missing_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(CanaryBandsConfigError, match="not found"):
        load_bands(tmp_path / "nope.toml")
