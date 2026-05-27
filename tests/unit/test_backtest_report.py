"""T024 — report writer: artefact tree shape + byte-stability invariants.

Verifies:
  - backtest-run.json schema matches contracts/backtest-run-json.md
  - metrics.csv columns + aggregate row
  - per-rule/<rid>/{orders,fills,gate-rejections}.json sorting + Decimal canonicalisation
  - _meta/kernel-guard-report.json snapshot
  - chmod-readonly applied at completion (POSIX)
  - byte-identical determinism contract holds for metrics.csv and per-rule/*.json
    across two writes of the same ReplayResult (FR-B15 / R-B5 stability for
    the byte-identical-covered subset).
"""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.backtest.data_model import BacktestRun
from auto_invest.backtest.replay import (
    FillRecord,
    GateRejectionRecord,
    OrderRecord,
    ReplayResult,
)
from auto_invest.backtest.report import (
    KernelGuardReport,
    build_per_rule_results,
    build_summary,
    write_report,
)

# ---------- helpers ------------------------------------------------------


def _make_result(*, with_fills: bool = True) -> ReplayResult:
    """Build a small ReplayResult for two rules — one with fills, one all rejected."""
    orders_r1 = [
        OrderRecord(
            correlation_id="c-1",
            rule_id="r1",
            symbol="AAPL",
            side="BUY",
            order_type="LIMIT",
            qty=20,
            limit_price_usd="190.000000",
            state="SUBMITTED",
            ts_utc="2024-01-03T21:00:00.000Z",
            kis_order_id="BT-ORD-aaa",
        ),
    ]
    fills_r1 = (
        [
            FillRecord(
                correlation_id="c-1",
                rule_id="r1",
                symbol="AAPL",
                side="BUY",
                qty=20,
                fill_price_usd="190.000000",
                executed_at_utc="2024-01-03T21:00:00.000Z",
                kis_fill_id="BT-FILL-aaa",
            ),
        ]
        if with_fills
        else []
    )

    orders_r2 = [
        OrderRecord(
            correlation_id="c-2",
            rule_id="r2",
            symbol="MSFT",
            side="BUY",
            order_type="LIMIT",
            qty=100,
            limit_price_usd="400.000000",
            state="REJECTED_BY_GATE",
            ts_utc="2024-01-03T21:00:00.000Z",
            kis_order_id=None,
            gate="per_trade_cap_gate",
            reason="too big",
        ),
    ]
    rejections_r2 = [
        GateRejectionRecord(
            correlation_id="c-2",
            rule_id="r2",
            symbol="MSFT",
            gate="per_trade_cap_gate",
            reason="too big",
            ts_utc="2024-01-03T21:00:00.000Z",
        ),
    ]

    # Monotonically increasing equity for r1 (with fill → small positive return).
    # Flat equity for r2 (no fill).
    eq_r1: list[tuple[date, Decimal]] = [
        (date(2024, 1, 3), Decimal("50000")),
        (date(2024, 1, 4), Decimal("50500")),
        (date(2024, 1, 5), Decimal("51000")),
    ]
    eq_r2: list[tuple[date, Decimal]] = [
        (date(2024, 1, 3), Decimal("50000")),
        (date(2024, 1, 4), Decimal("50000")),
        (date(2024, 1, 5), Decimal("50000")),
    ]

    notional_r1 = Decimal("3800") if with_fills else Decimal("0")

    return ReplayResult(
        per_rule_orders={"r1": orders_r1, "r2": orders_r2},
        per_rule_fills={"r1": fills_r1, "r2": []},
        per_rule_gate_rejections={"r1": [], "r2": rejections_r2},
        per_rule_equity_curve={"r1": eq_r1, "r2": eq_r2},
        per_rule_symbol={"r1": "AAPL", "r2": "MSFT"},
        per_rule_notional_traded_usd={"r1": notional_r1, "r2": Decimal("0")},
        data_quality_warnings=[],
        total_orders=2,
        total_fills=1 if with_fills else 0,
        total_gate_rejections=1,
    )


def _make_run(run_id: str = "bt-test-run") -> BacktestRun:
    return BacktestRun(
        run_id=run_id,
        invoker="cli",
        ruleset_path=Path("/tmp/rules.toml"),
        ruleset_sha256="3" * 64,
        dataset_version="7" * 64,
        date_start=date(2024, 1, 3),
        date_end=date(2024, 1, 5),
        replay_seed=0,
        synthetic_shock=False,
        start_ts=datetime(2026, 5, 13, 14, 32, 1, tzinfo=UTC),
        end_ts=datetime(2026, 5, 13, 14, 34, 17, tzinfo=UTC),
        status="completed",
    )


def _guard_report(touched: bool = False) -> KernelGuardReport:
    return KernelGuardReport(
        touched=touched,
        checked_paths=[".specify/memory/kernel.toml", "src/auto_invest/risk/gates.py"],
        manifest_sha256="a" * 64,
    )


# ---------- backtest-run.json schema -------------------------------------


def test_backtest_run_json_top_level_fields(tmp_path: Path) -> None:
    run_dir = write_report(
        run=_make_run(),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=tmp_path,
        chmod_readonly=False,
    )
    payload = json.loads((run_dir / "backtest-run.json").read_text())

    for field in (
        "run_id",
        "invoker",
        "ruleset_path",
        "ruleset_sha256",
        "dataset_version",
        "date_start",
        "date_end",
        "replay_seed",
        "fill_model",
        "cost_model",
        "judgment_mode",
        "synthetic_shock",
        "start_ts",
        "end_ts",
        "status",
        "summary",
        "kernel_guard_report",
    ):
        assert field in payload, f"missing top-level field {field!r}"

    assert payload["fill_model"] == "pessimistic_zero_slip"
    assert payload["judgment_mode"] == "stub"
    assert "total_commission_usd" in payload["summary"]
    assert "total_slippage_cost_usd" in payload["summary"]
    assert payload["summary"]["total_orders"] == 2
    assert payload["summary"]["total_fills"] == 1
    assert payload["summary"]["total_gate_rejections"] == 1
    assert len(payload["summary"]["per_rule"]) == 2


def test_summary_decimals_are_canonical_6dp(tmp_path: Path) -> None:
    run_dir = write_report(
        run=_make_run(),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=tmp_path,
        chmod_readonly=False,
    )
    payload = json.loads((run_dir / "backtest-run.json").read_text())
    summary = payload["summary"]

    for key in ("aggregate_return_pct", "aggregate_max_drawdown_pct", "aggregate_sharpe"):
        v = summary[key]
        assert isinstance(v, str)
        assert "." in v
        assert len(v.split(".")[1]) == 6, f"{key}={v!r} not canonical 6dp"

    for r in summary["per_rule"]:
        for key in (
            "total_return_pct",
            "max_drawdown_pct",
            "sharpe_ratio",
            "notional_traded_usd",
        ):
            v = r[key]
            assert len(v.split(".")[1]) == 6


# ---------- metrics.csv ---------------------------------------------------


def test_metrics_csv_columns_and_aggregate_row(tmp_path: Path) -> None:
    run_dir = write_report(
        run=_make_run(),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=tmp_path,
        chmod_readonly=False,
    )
    text = (run_dir / "metrics.csv").read_text()
    rows = [r.split(",") for r in text.strip().split("\n")]
    header, *data = rows

    assert header == [
        "rule_id",
        "symbol",
        "total_return_pct",
        "max_drawdown_pct",
        "sharpe",
        "sortino",
        "order_count",
        "fill_count",
        "closed_trades",
        "win_rate",
        "profit_factor",
        "total_gate_rejections",
        "notional_usd",
        "commission_usd",
        "slippage_cost_usd",
    ]
    # 2 rules + 1 aggregate row
    assert len(data) == 3
    assert data[-1][0] == "_aggregate"
    assert data[-1][1] == ""


def test_metrics_csv_rule_rows_sorted_by_rule_id(tmp_path: Path) -> None:
    run_dir = write_report(
        run=_make_run(),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=tmp_path,
        chmod_readonly=False,
    )
    rows = (run_dir / "metrics.csv").read_text().strip().split("\n")[1:-1]
    rule_ids = [r.split(",")[0] for r in rows]
    assert rule_ids == sorted(rule_ids)


# ---------- per-rule artefacts -------------------------------------------


def test_per_rule_directories_and_files(tmp_path: Path) -> None:
    run_dir = write_report(
        run=_make_run(),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=tmp_path,
        chmod_readonly=False,
    )
    assert (run_dir / "per-rule" / "r1" / "orders.json").exists()
    assert (run_dir / "per-rule" / "r1" / "fills.json").exists()
    assert (run_dir / "per-rule" / "r1" / "gate-rejections.json").exists()
    assert (run_dir / "per-rule" / "r2" / "orders.json").exists()
    assert (run_dir / "per-rule" / "r2" / "fills.json").exists()
    assert (run_dir / "per-rule" / "r2" / "gate-rejections.json").exists()


def test_per_rule_orders_contain_expected_fields(tmp_path: Path) -> None:
    run_dir = write_report(
        run=_make_run(),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=tmp_path,
        chmod_readonly=False,
    )
    orders = json.loads((run_dir / "per-rule" / "r1" / "orders.json").read_text())
    assert len(orders) == 1
    o = orders[0]
    for field in ("correlation_id", "rule_id", "symbol", "side", "qty", "state", "ts_utc"):
        assert field in o

    rejections = json.loads(
        (run_dir / "per-rule" / "r2" / "gate-rejections.json").read_text()
    )
    assert len(rejections) == 1
    assert rejections[0]["gate"] == "per_trade_cap_gate"


# ---------- _meta/kernel-guard-report.json -------------------------------


def test_kernel_guard_report_meta_written(tmp_path: Path) -> None:
    run_dir = write_report(
        run=_make_run(),
        result=_make_result(),
        kernel_guard_report=_guard_report(touched=False),
        out_root=tmp_path,
        chmod_readonly=False,
    )
    meta = json.loads((run_dir / "_meta" / "kernel-guard-report.json").read_text())
    assert meta["touched"] is False
    assert ".specify/memory/kernel.toml" in meta["checked_paths"]
    assert len(meta["manifest_sha256"]) == 64


# ---------- byte-stability (FR-B15) --------------------------------------


def test_metrics_csv_byte_identical_across_runs(tmp_path: Path) -> None:
    """The byte-identical-covered subset must reproduce exactly given the same inputs."""
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    write_report(
        run=_make_run("run-A"),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=out_a,
        chmod_readonly=False,
    )
    write_report(
        run=_make_run("run-B"),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=out_b,
        chmod_readonly=False,
    )
    a = (out_a / "run-A" / "metrics.csv").read_bytes()
    b = (out_b / "run-B" / "metrics.csv").read_bytes()
    assert a == b


def test_per_rule_orders_byte_identical_across_runs(tmp_path: Path) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    write_report(
        run=_make_run("run-A"),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=out_a,
        chmod_readonly=False,
    )
    write_report(
        run=_make_run("run-B"),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=out_b,
        chmod_readonly=False,
    )
    a = (out_a / "run-A" / "per-rule" / "r1" / "orders.json").read_bytes()
    b = (out_b / "run-B" / "per-rule" / "r1" / "orders.json").read_bytes()
    assert a == b


# ---------- POSIX chmod-readonly -----------------------------------------


@pytest.mark.skipif(os.name != "posix", reason="chmod semantics are POSIX-only")
def test_chmod_readonly_strips_write_bits(tmp_path: Path) -> None:
    run_dir = write_report(
        run=_make_run(),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=tmp_path,
        chmod_readonly=True,
    )
    f = run_dir / "backtest-run.json"
    mode = f.stat().st_mode
    # No write bit set on user/group/other.
    assert not (mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


# ---------- aggregate-row arithmetic -------------------------------------


def test_metrics_csv_aggregate_notional_is_sum_of_rules(tmp_path: Path) -> None:
    run_dir = write_report(
        run=_make_run(),
        result=_make_result(),
        kernel_guard_report=_guard_report(),
        out_root=tmp_path,
        chmod_readonly=False,
    )
    rows = (run_dir / "metrics.csv").read_text().strip().split("\n")
    *rule_rows, agg = rows[1:]
    rule_notionals = sum(Decimal(r.split(",")[-1]) for r in rule_rows)
    assert Decimal(agg.split(",")[-1]) == rule_notionals


# ---------- spec 016 슬라이스 2 — 거래 단위 잣대 (헌법 X.2) ---------------


def _round_trip_result() -> ReplayResult:
    """r1: BUY 2@100, SELL 2@130 → +60 한 청산. r2: 체결 없음."""
    fills_r1 = [
        FillRecord(
            correlation_id="c-b",
            rule_id="r1",
            symbol="AAPL",
            side="BUY",
            qty=2,
            fill_price_usd="100.000000",
            executed_at_utc="2024-01-03T21:00:00.000Z",
            kis_fill_id="BT-b",
        ),
        FillRecord(
            correlation_id="c-s",
            rule_id="r1",
            symbol="AAPL",
            side="SELL",
            qty=2,
            fill_price_usd="130.000000",
            executed_at_utc="2024-01-04T21:00:00.000Z",
            kis_fill_id="BT-s",
        ),
    ]
    orders_r1 = [
        OrderRecord(
            correlation_id=cid,
            rule_id="r1",
            symbol="AAPL",
            side=side,
            order_type="LIMIT",
            qty=2,
            limit_price_usd="100.000000",
            state="SUBMITTED",
            ts_utc=ts,
            kis_order_id=oid,
        )
        for cid, side, ts, oid in (
            ("c-b", "BUY", "2024-01-03T21:00:00.000Z", "BT-ob"),
            ("c-s", "SELL", "2024-01-04T21:00:00.000Z", "BT-os"),
        )
    ]
    eq = [
        (date(2024, 1, 3), Decimal("50000")),
        (date(2024, 1, 4), Decimal("50060")),
    ]
    return ReplayResult(
        per_rule_orders={"r1": orders_r1, "r2": []},
        per_rule_fills={"r1": fills_r1, "r2": []},
        per_rule_gate_rejections={"r1": [], "r2": []},
        per_rule_equity_curve={"r1": eq, "r2": [(date(2024, 1, 3), Decimal("50000"))]},
        per_rule_symbol={"r1": "AAPL", "r2": "MSFT"},
        per_rule_notional_traded_usd={"r1": Decimal("460"), "r2": Decimal("0")},
        data_quality_warnings=[],
        total_orders=2,
        total_fills=2,
        total_gate_rejections=0,
    )


def test_per_rule_result_carries_trade_metrics() -> None:
    per_rule = {r.rule_id: r for r in build_per_rule_results(_round_trip_result())}
    r1 = per_rule["r1"]
    assert r1.closed_trades == 1
    assert r1.win_rate == Decimal("1.000000")  # 1 of 1 winning
    assert r1.profit_factor is None  # no losing trade → no denominator
    # r2 had no closed trades → N/A.
    r2 = per_rule["r2"]
    assert r2.closed_trades == 0
    assert r2.win_rate is None
    assert r2.profit_factor is None


def test_summary_pools_trade_metrics_across_rules() -> None:
    result = _round_trip_result()
    summary = build_summary(result, build_per_rule_results(result))
    assert summary.total_closed_trades == 1
    assert summary.aggregate_win_rate == Decimal("1.000000")
    assert summary.aggregate_profit_factor is None


def test_metrics_csv_has_trade_metric_columns(tmp_path: Path) -> None:
    run_dir = write_report(
        run=_make_run(),
        result=_round_trip_result(),
        kernel_guard_report=_guard_report(),
        out_root=tmp_path,
        chmod_readonly=False,
    )
    rows = [r.split(",") for r in (run_dir / "metrics.csv").read_text().strip().split("\n")]
    header = rows[0]
    r1_row = dict(zip(header, rows[1], strict=True))
    assert r1_row["rule_id"] == "r1"
    assert r1_row["closed_trades"] == "1"
    assert r1_row["win_rate"] == "1.000000"
    assert r1_row["profit_factor"] == ""  # N/A → empty cell
    assert "sortino" in header
