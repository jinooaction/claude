"""T036 — summary.md renderer (US3): structure + content coverage.

Verifies that a canned BacktestSummary renders to a Markdown string that:
  - has each section header in the contract order
  - lists every rule with its headline metrics in the table
  - surfaces every DataQualityWarning
  - groups gate rejections by gate name
  - includes the slippage-assumption disclaimer line
  - is byte-stable for the same inputs (FR-B15 spillover)
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from auto_invest.backtest.data_model import (
    BacktestRun,
    BacktestSummary,
    DataQualityWarning,
    RuleBacktestResult,
)
from auto_invest.backtest.report import KernelGuardReport, render_summary_md


def _summary(
    *,
    with_warnings: bool = False,
    with_rejections: bool = False,
) -> BacktestSummary:
    per_rule = [
        RuleBacktestResult(
            rule_id="alpha",
            symbol="AAPL",
            total_return_pct=Decimal("3.500000"),
            max_drawdown_pct=Decimal("1.250000"),
            sharpe_ratio=Decimal("0.812000"),
            order_count=8,
            fill_count=7,
            gate_rejection_count_by_gate={"per_trade_cap_gate": 1} if with_rejections else {},
            notional_traded_usd=Decimal("12345.000000"),
        ),
        RuleBacktestResult(
            rule_id="beta",
            symbol="MSFT",
            total_return_pct=Decimal("-1.200000"),
            max_drawdown_pct=Decimal("4.000000"),
            sharpe_ratio=Decimal("-0.250000"),
            order_count=4,
            fill_count=3,
            gate_rejection_count_by_gate={"per_symbol_cap_gate": 2} if with_rejections else {},
            notional_traded_usd=Decimal("5000.000000"),
        ),
    ]
    warnings = (
        [
            DataQualityWarning(
                symbol="AAPL",
                session_date=date(2024, 4, 15),
                kind="zero_volume_regular",
                note="ad-hoc gap",
            ),
            DataQualityWarning(
                symbol="MSFT",
                session_date=None,
                kind="gap_over_7_days",
                note="multi-day gap",
            ),
        ]
        if with_warnings
        else []
    )
    return BacktestSummary(
        aggregate_return_pct=Decimal("1.150000"),
        aggregate_max_drawdown_pct=Decimal("4.000000"),
        aggregate_sharpe=Decimal("0.281000"),
        per_rule=per_rule,
        total_orders=12,
        total_fills=10,
        total_gate_rejections=3 if with_rejections else 0,
        data_quality_warnings=warnings,
    )


def _run() -> BacktestRun:
    return BacktestRun(
        run_id="bt-test-run-123",
        invoker="cli",
        ruleset_path=Path("/tmp/rules.toml"),
        ruleset_sha256="3" * 64,
        dataset_version="7" * 64,
        date_start=date(2024, 1, 2),
        date_end=date(2024, 1, 31),
        replay_seed=0,
        synthetic_shock=False,
        start_ts=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
        end_ts=datetime(2026, 5, 14, 10, 0, 5, tzinfo=UTC),
        status="completed",
    )


def _guard() -> KernelGuardReport:
    return KernelGuardReport(touched=False, checked_paths=[], manifest_sha256="a" * 64)


# ---------- structural sections ----------------------------------------


def test_summary_contains_all_sections() -> None:
    md = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    assert "# Backtest summary — bt-test-run-123" in md
    assert "## Aggregate metrics" in md
    assert "## Per-rule headline metrics" in md
    assert "## Data-quality warnings" in md
    assert "## Gate-rejection breakdown" in md


def test_summary_section_order_matches_contract() -> None:
    md = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    sections_in_order = [
        "# Backtest summary",
        "## Aggregate metrics",
        "## Per-rule headline metrics",
        "## Data-quality warnings",
        "## Gate-rejection breakdown",
    ]
    last = -1
    for s in sections_in_order:
        idx = md.find(s)
        assert idx > last, f"section out of order: {s}"
        last = idx


def test_summary_header_includes_required_fields() -> None:
    md = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    assert "date range:" in md
    assert "ruleset sha256:" in md
    assert "dataset_version:" in md
    assert "fill model:" in md
    assert "judgment mode:" in md
    assert "slippage assumption:" in md
    assert "synthetic_shock:" in md


def test_summary_includes_slippage_disclaimer() -> None:
    md = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    # Disclaimer references R-B3 + the locked "zero" assumption.
    assert "slippage assumption:" in md
    assert "zero" in md.lower()
    assert "R-B3" in md


def test_summary_lists_every_rule_in_table() -> None:
    md = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    assert "| alpha | AAPL " in md
    assert "| beta | MSFT " in md
    assert "3.500000" in md  # alpha return
    assert "-1.200000" in md  # beta return
    assert "12345.000000" in md  # alpha notional


def test_summary_table_header_present() -> None:
    md = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    # Markdown table header keywords (order in the actual rendered header).
    for col in (
        "rule_id",
        "symbol",
        "return_pct",
        "max_dd_pct",
        "sharpe",
        "orders",
        "fills",
        "gate_rejections",
        "notional_usd",
    ):
        assert col in md


def test_summary_surfaces_all_data_quality_warnings() -> None:
    md = render_summary_md(
        run=_run(),
        summary=_summary(with_warnings=True),
        kernel_guard_report=_guard(),
    )
    assert "AAPL 2024-04-15: zero_volume_regular" in md
    assert "MSFT —: gap_over_7_days" in md or "MSFT — : gap_over_7_days" in md
    assert "ad-hoc gap" in md
    assert "multi-day gap" in md


def test_summary_empty_warnings_section_shows_none() -> None:
    md = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    # Locate the warnings section and confirm it says _none_.
    warnings_block = md.split("## Data-quality warnings", 1)[1].split("## ", 1)[0]
    assert "_none_" in warnings_block


def test_summary_groups_gate_rejections_by_gate() -> None:
    md = render_summary_md(
        run=_run(),
        summary=_summary(with_rejections=True),
        kernel_guard_report=_guard(),
    )
    block = md.split("## Gate-rejection breakdown", 1)[1]
    assert "per_trade_cap_gate: 1" in block
    assert "per_symbol_cap_gate: 2" in block


def test_summary_no_rejections_shows_placeholder() -> None:
    md = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    block = md.split("## Gate-rejection breakdown", 1)[1]
    assert "_no rejections_" in block


# ---------- byte-stability spillover ---------------------------------


def test_summary_byte_stable_for_same_inputs() -> None:
    md1 = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    md2 = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    assert md1 == md2


def test_summary_ends_with_newline() -> None:
    md = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    assert md.endswith("\n")


def test_summary_aggregate_metrics_canonical_6dp() -> None:
    md = render_summary_md(run=_run(), summary=_summary(), kernel_guard_report=_guard())
    block = md.split("## Aggregate metrics", 1)[1].split("##", 1)[0]
    for v in ("1.150000", "4.000000", "0.281000"):
        assert v in block
