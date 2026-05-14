"""T025 — run.py orchestration: happy path + every error-branch exit code.

Asserts:
  - Happy path emits BACKTEST_STARTED + BACKTEST_COMPLETED and writes the
    full artefact tree (backtest-run.json with status=completed).
  - Kernel-touched + no --allow-kernel-edits → exit 78, BACKTEST_BLOCKED_KERNEL_TOUCH
    ERROR row, backtest-run.json with status=failed for forensics.
  - --allow-kernel-edits bypasses the gate (still records touched=True in JSON).
  - Live-broker leak inside replay → exit 80 + BACKTEST_LIVE_BROKER_LEAK.
  - BACKTEST_MODE env var is set during replay and restored at end.
  - Failure paths still write backtest-run.json (forensics survive).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.backtest.broker_mock import BacktestLiveBrokerLeakError
from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.backtest.judgment_stub import BACKTEST_MODE_ENV
from auto_invest.backtest.kernel_pre_flight import PreFlightResult
from auto_invest.backtest.run import (
    EXIT_KERNEL_TOUCHED,
    EXIT_LIVE_BROKER_LEAK,
    EXIT_OK,
    RunOptions,
    run_backtest,
)
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, PriceTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import audit, db

# ---------- fakes -------------------------------------------------------


@dataclass
class _FakeDataSource:
    bars: dict[str, list[OHLCVBar]]
    holes: list[tuple[str, date]] = field(default_factory=list)

    @property
    def dataset_version(self) -> str:
        return "f" * 64

    def list_symbols(self) -> list[str]:
        return sorted(self.bars.keys())

    def session_dates(self, symbol: str) -> list[date]:
        return [b.session_date for b in self.bars.get(symbol, [])]

    def coverage_holes(self, symbols, date_start, date_end):  # noqa: ANN001
        return list(self.holes)

    def read_bars(self, symbol, date_start, date_end):  # noqa: ANN001
        return [
            b
            for b in self.bars.get(symbol, [])
            if date_start <= b.session_date <= date_end
        ]


def _bar(d: date) -> OHLCVBar:
    return OHLCVBar(
        symbol="AAPL",
        session_date=d,
        open=Decimal("190.00"),
        high=Decimal("200.00"),
        low=Decimal("185.00"),
        close=Decimal("195.00"),
        volume=1_000_000,
        session_schedule_tag="regular",
    )


def _rule(rid: str = "r1") -> TradingRule:
    return TradingRule(
        id=rid,
        symbol="AAPL",
        stage=StrategyStage.BACKTEST,
        priority=0,
        trigger=PriceTrigger(direction="<=", threshold=Decimal("200"), cooldown_seconds=0),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=20, limit_price="190.00"),
    )


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("10"),
        global_exposure_pct=Decimal("50"),
        canary_capital_pct=Decimal("1"),
        canary_min_duration_days=5,
        canary_acceptance_drawdown_pct=Decimal("5"),
    )


def _whitelist() -> Whitelist:
    return Whitelist(
        symbols=frozenset({"AAPL"}),
        accounts=frozenset({"BACKTEST"}),
        order_types=frozenset({OrderType.LIMIT}),
    )


def _options(
    tmp_path: Path,
    *,
    allow_kernel_edits: bool = False,
    pre_flight: PreFlightResult | None = None,
    rules=(),
    bars=None,
) -> RunOptions:
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text("# fake rules toml")
    if bars is None:
        bars = {"AAPL": [_bar(date(2024, 1, 3))]}
    return RunOptions(
        rules_path=rules_path,
        rules=list(rules) if rules else [_rule()],
        ruleset_sha256="3" * 64,
        data_source=_FakeDataSource(bars),
        date_start=date(2024, 1, 3),
        date_end=date(2024, 1, 3),
        caps=_caps(),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        out_root=tmp_path / "out",
        allow_kernel_edits=allow_kernel_edits,
        pre_flight_result=pre_flight or PreFlightResult(touched=False),
        chmod_readonly=False,  # tests inspect artefact dirs
        repo_root=tmp_path,  # avoids reading the real repo's kernel.toml
    )


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "audit.db")
    db.migrate(c)
    yield c
    c.close()


# ---------- happy path --------------------------------------------------


def test_happy_path_writes_artefacts_and_emits_audit_chain(conn, tmp_path) -> None:
    options = _options(tmp_path)
    outcome = run_backtest(options, conn=conn)

    assert outcome.exit_code == EXIT_OK
    assert outcome.failure_reason is None
    assert (outcome.run_dir / "backtest-run.json").exists()
    assert (outcome.run_dir / "metrics.csv").exists()
    assert (outcome.run_dir / "per-rule" / "r1").exists()
    payload = json.loads((outcome.run_dir / "backtest-run.json").read_text())
    assert payload["status"] == "completed"
    assert payload["summary"]["total_orders"] >= 1

    events = [r["event_type"] for r in audit.read_all(conn)]
    assert "BACKTEST_STARTED" in events
    assert "BACKTEST_COMPLETED" in events
    assert events[-1] == "BACKTEST_COMPLETED"  # terminal row


def test_happy_path_run_dir_includes_meta_kernel_report(conn, tmp_path) -> None:
    outcome = run_backtest(_options(tmp_path), conn=conn)
    meta = json.loads(
        (outcome.run_dir / "_meta" / "kernel-guard-report.json").read_text()
    )
    assert meta["touched"] is False
    assert "checked_paths" in meta
    assert "manifest_sha256" in meta


# ---------- kernel-touched gate (exit 78) -------------------------------


def test_kernel_touched_without_override_exits_78(conn, tmp_path) -> None:
    options = _options(
        tmp_path,
        pre_flight=PreFlightResult(
            touched=True,
            paths=["src/auto_invest/risk/gates.py"],
            groups=["K1"],
        ),
    )
    outcome = run_backtest(options, conn=conn)

    assert outcome.exit_code == EXIT_KERNEL_TOUCHED
    assert "BACKTEST_BLOCKED_KERNEL_TOUCH" in (outcome.failure_reason or "") or (
        "Kernel" in (outcome.failure_reason or "")
    )
    assert outcome.kernel_touched_paths == ["src/auto_invest/risk/gates.py"]

    # Forensic backtest-run.json still written.
    payload = json.loads((outcome.run_dir / "backtest-run.json").read_text())
    assert payload["status"] == "failed"
    assert payload["summary"] is None

    # ERROR + BACKTEST_COMPLETED rows written for forensic chain.
    events = [r["event_type"] for r in audit.read_all(conn)]
    assert "ERROR" in events
    assert "BACKTEST_COMPLETED" in events
    # No replay → no BACKTEST_STARTED + no order chain.
    assert "BACKTEST_STARTED" not in events
    assert "ORDER_INTENT" not in events


def test_allow_kernel_edits_bypasses_gate_and_completes(conn, tmp_path) -> None:
    options = _options(
        tmp_path,
        allow_kernel_edits=True,
        pre_flight=PreFlightResult(
            touched=True,
            paths=["src/auto_invest/risk/gates.py"],
            groups=["K1"],
        ),
    )
    outcome = run_backtest(options, conn=conn)
    assert outcome.exit_code == EXIT_OK

    # The bypass still records touched=True in the artefact for forensics.
    meta = json.loads(
        (outcome.run_dir / "_meta" / "kernel-guard-report.json").read_text()
    )
    assert meta["touched"] is True


# ---------- BACKTEST_MODE env var ---------------------------------------


def test_backtest_mode_env_var_restored_after_run(conn, tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(BACKTEST_MODE_ENV, raising=False)
    run_backtest(_options(tmp_path), conn=conn)
    # After completion the env var must not be set (started unset → restored to unset).
    assert os.environ.get(BACKTEST_MODE_ENV) is None


def test_backtest_mode_env_var_restored_to_prior_value(conn, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(BACKTEST_MODE_ENV, "0")
    run_backtest(_options(tmp_path), conn=conn)
    assert os.environ.get(BACKTEST_MODE_ENV) == "0"


# ---------- live-broker leak (exit 80) ----------------------------------


def test_live_broker_leak_exits_80(conn, tmp_path, monkeypatch) -> None:
    """Patch BacktestBroker to fail the adapter-id check at replay entry."""
    from auto_invest.backtest import run as run_module

    real_broker_cls = run_module.BacktestBroker

    class _Leaky(real_broker_cls):
        def __init__(self) -> None:
            super().__init__()
            self.adapter_id = "kis-prod-v1"  # type: ignore[assignment]

    monkeypatch.setattr(run_module, "BacktestBroker", _Leaky)

    outcome = run_backtest(_options(tmp_path), conn=conn)

    assert outcome.exit_code == EXIT_LIVE_BROKER_LEAK
    assert "BACKTEST_LIVE_BROKER_LEAK" in (outcome.failure_reason or "")
    payload = json.loads((outcome.run_dir / "backtest-run.json").read_text())
    assert payload["status"] == "failed"
    events = [r["event_type"] for r in audit.read_all(conn)]
    assert "BACKTEST_STARTED" in events
    assert "BACKTEST_COMPLETED" in events
    assert any(
        r["event_type"] == "ERROR"
        and "BACKTEST_LIVE_BROKER_LEAK" in json.loads(r["payload_json"]).get("message", "")
        for r in audit.read_all(conn)
    )


def test_live_broker_leak_does_not_raise(conn, tmp_path, monkeypatch) -> None:
    """The orchestrator MUST swallow BacktestLiveBrokerLeakError and exit cleanly."""
    from auto_invest.backtest import run as run_module

    class _Leaky(run_module.BacktestBroker):
        def __init__(self) -> None:
            super().__init__()
            self.adapter_id = "kis-prod-v1"  # type: ignore[assignment]

    monkeypatch.setattr(run_module, "BacktestBroker", _Leaky)
    # Should not raise; exit code communicates the failure.
    outcome = run_backtest(_options(tmp_path), conn=conn)
    assert isinstance(outcome.exit_code, int)


# ---------- run_id uniqueness ------------------------------------------


def test_run_id_unique_per_invocation(conn, tmp_path) -> None:
    a = run_backtest(_options(tmp_path), conn=conn)
    b = run_backtest(_options(tmp_path), conn=conn)
    assert a.run_id != b.run_id


# ---------- BacktestLiveBrokerLeakError sanity ------------------------


def test_assert_backtest_adapter_imported_at_module_load() -> None:
    """If broker_mock module never imported BacktestLiveBrokerLeakError, tests above
    would silently pass — sanity-check the symbol is reachable."""
    assert BacktestLiveBrokerLeakError is not None
