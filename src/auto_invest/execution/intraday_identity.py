"""Reviewed local execution sources; no accounts or authorization issuance."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
# Reviewed static local dependencies of the original Spec 184 source set.
# A regression check detects new local imports omitted from this list.
SOURCE_PATHS = (
    "src/auto_invest/__init__.py",
    "src/auto_invest/analytics/__init__.py",
    "src/auto_invest/analytics/backtest_overfitting.py",
    "src/auto_invest/analytics/intraday_archive.py",
    "src/auto_invest/analytics/intraday_capital_review.py",
    "src/auto_invest/analytics/intraday_operator.py",
    "src/auto_invest/analytics/intraday_paper_challenger.py",
    "src/auto_invest/analytics/intraday_runtime.py",
    "src/auto_invest/backtest/__init__.py",
    "src/auto_invest/backtest/broker_mock.py",
    "src/auto_invest/backtest/clock.py",
    "src/auto_invest/backtest/costs.py",
    "src/auto_invest/backtest/data_model.py",
    "src/auto_invest/backtest/data_source.py",
    "src/auto_invest/backtest/ingest.py",
    "src/auto_invest/backtest/judgment_stub.py",
    "src/auto_invest/backtest/kernel_pre_flight.py",
    "src/auto_invest/backtest/metrics.py",
    "src/auto_invest/backtest/replay.py",
    "src/auto_invest/backtest/report.py",
    "src/auto_invest/backtest/run.py",
    "src/auto_invest/backtest/synthetic_shocks.py",
    "src/auto_invest/broker/__init__.py",
    "src/auto_invest/broker/account_asset_evidence.py",
    "src/auto_invest/broker/account_source_profile.py",
    "src/auto_invest/broker/auth.py",
    "src/auto_invest/broker/balance_report_audit.py",
    "src/auto_invest/broker/client.py",
    "src/auto_invest/broker/diagnostics.py",
    "src/auto_invest/broker/domestic_account.py",
    "src/auto_invest/broker/intraday_account.py",
    "src/auto_invest/broker/intraday_account_frame.py",
    "src/auto_invest/broker/intraday_asset_scope.py",
    "src/auto_invest/broker/intraday_balance_evidence.py",
    "src/auto_invest/broker/intraday_cash_baseline.py",
    "src/auto_invest/broker/intraday_holdings_coverage.py",
    "src/auto_invest/broker/intraday_inputs.py",
    "src/auto_invest/broker/intraday_reported_cash.py",
    "src/auto_invest/broker/intraday_transactions.py",
    "src/auto_invest/broker/models.py",
    "src/auto_invest/broker/overseas.py",
    "src/auto_invest/broker/realtime.py",
    "src/auto_invest/config/__init__.py",
    "src/auto_invest/config/caps.py",
    "src/auto_invest/config/enums.py",
    "src/auto_invest/config/loader.py",
    "src/auto_invest/config/rules.py",
    "src/auto_invest/config/whitelist.py",
    "src/auto_invest/deploy/__init__.py",
    "src/auto_invest/deploy/kernel_guard.py",
    "src/auto_invest/execution/__init__.py",
    "src/auto_invest/execution/authority.py",
    "src/auto_invest/execution/cancellation.py",
    "src/auto_invest/execution/execution_state.py",
    "src/auto_invest/execution/exposure_reservation.py",
    "src/auto_invest/execution/fill_sync.py",
    "src/auto_invest/execution/intraday.py",
    "src/auto_invest/execution/intraday_budget.py",
    "src/auto_invest/execution/intraday_budget_observation.py",
    "src/auto_invest/execution/intraday_budget_settlements.py",
    "src/auto_invest/execution/intraday_cash_ledger.py",
    "src/auto_invest/execution/intraday_cost_reconciliation.py",
    "src/auto_invest/execution/intraday_execution_evidence.py",
    "src/auto_invest/execution/intraday_forward.py",
    "src/auto_invest/execution/intraday_identity.py",
    "src/auto_invest/execution/intraday_launch.py",
    "src/auto_invest/execution/intraday_observation.py",
    "src/auto_invest/execution/intraday_observation_models.py",
    "src/auto_invest/execution/intraday_program.py",
    "src/auto_invest/execution/intraday_qualification.py",
    "src/auto_invest/execution/intraday_registration.py",
    "src/auto_invest/execution/intraday_rehearsal.py",
    "src/auto_invest/execution/intraday_runtime.py",
    "src/auto_invest/execution/intraday_selection.py",
    "src/auto_invest/execution/intraday_signals.py",
    "src/auto_invest/execution/lifecycle.py",
    "src/auto_invest/execution/order_router.py",
    "src/auto_invest/execution/preparation.py",
    "src/auto_invest/judgment/__init__.py",
    "src/auto_invest/judgment/client.py",
    "src/auto_invest/judgment/points/__init__.py",
    "src/auto_invest/judgment/points/news_screen.py",
    "src/auto_invest/judgment/points/volatility.py",
    "src/auto_invest/judgment/registry.py",
    "src/auto_invest/judgment/schemas.py",
    "src/auto_invest/logging_config.py",
    "src/auto_invest/market_data/__init__.py",
    "src/auto_invest/market_data/intraday.py",
    "src/auto_invest/market_data/intraday_attestation.py",
    "src/auto_invest/market_data/intraday_pricing.py",
    "src/auto_invest/market_data/store.py",
    "src/auto_invest/persistence/__init__.py",
    "src/auto_invest/persistence/audit.py",
    "src/auto_invest/persistence/db.py",
    "src/auto_invest/persistence/fill_amounts.py",
    "src/auto_invest/persistence/migrations/0005_fill_notionals.sql",
    "src/auto_invest/persistence/positions.py",
    "src/auto_invest/reconciliation/__init__.py",
    "src/auto_invest/reconciliation/external_holdings.py",
    "src/auto_invest/risk/__init__.py",
    "src/auto_invest/risk/gates.py",
    "src/auto_invest/strategy/__init__.py",
    "src/auto_invest/strategy/factors.py",
    "src/auto_invest/strategy/indicators.py",
    "src/auto_invest/strategy/quality.py",
    "src/auto_invest/strategy/ranking.py",
    "src/auto_invest/strategy/regime.py",
    "src/auto_invest/strategy/sizing.py",
    "src/auto_invest/strategy/triggers.py",
    "src/auto_invest/telemetry/__init__.py",
    "src/auto_invest/telemetry/kpi.py",
    "src/auto_invest/telemetry/meter.py",
    "src/auto_invest/telemetry/prices.py",
    "src/auto_invest/telemetry/store.py",
    "src/auto_invest/telemetry/thresholds.py",
    "src/auto_invest/worker/__init__.py",
    "src/auto_invest/worker/halt.py",
)


def _state(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("EXECUTION_SOURCE_UNAVAILABLE")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def source_identity():
    """Bind relative names and fresh bytes; reject missing or changing sources."""
    if (tuple(sorted(set(SOURCE_PATHS))) != SOURCE_PATHS
            or any(not name.startswith("src/auto_invest/") or ".." in Path(name).parts
                   for name in SOURCE_PATHS)):
        raise ValueError("EXECUTION_SOURCE_LIST_INVALID")
    snapshots = []
    records = []
    try:
        for name in SOURCE_PATHS:
            path = ROOT / name
            # Never substitute a symlink target for a reviewed source path.
            if any(parent.is_symlink() for parent in (path, *path.parents)
                   if parent != ROOT and ROOT in parent.parents):
                raise ValueError("EXECUTION_SOURCE_UNAVAILABLE")
            before = _state(path)
            raw = path.read_bytes()
            if _state(path) != before:
                raise ValueError("EXECUTION_SOURCE_CHANGED")
            snapshots.append((path, before))
            records.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest()})
        # Detect an earlier file changed while later sources were being read.
        if any(_state(path) != before for path, before in snapshots):
            raise ValueError("EXECUTION_SOURCE_CHANGED")
    except OSError:
        raise ValueError("EXECUTION_SOURCE_UNAVAILABLE") from None
    return records
