"""T017 — engine pre-flight kernel-touch check tests (Phase 3 / US1).

Drives ``auto_invest.backtest.engine.kernel_touch_check`` — the engine's
defense-in-depth check that mirrors spec 006 FR-D13 / spec 007 FR-C08.

The engine reads ``.specify/memory/kernel.toml`` and rejects any change
set whose diff intersects a Kernel-protected path. This protects the
canary harness even when invoked outside the deploy guard.

T017 spec (tasks.md)::

    Test tests/backtest/test_kernel_safety.py: invoke the engine's
    pre-flight kernel_touch_check against a synthetic diff that
    includes kernel.toml and assert it raises
    BacktestKernelTouchError; against an empty diff assert it returns
    cleanly. Also: parametrise over each Kernel group (K1..K7 +
    K_meta) — synthesize a diff that touches one file per group and
    assert the check rejects each; specifically include
    data/ohlcv/datasets/synthetic_shock_v1.json (K7) so FR-B20's
    runtime enforcement is regression-tested.

This file is written BEFORE T021 (engine.py) lands. Import-time failure
is the desired red signal.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from auto_invest.backtest.engine import kernel_touch_check

from auto_invest.backtest.errors import BacktestKernelTouchError

REPO_ROOT = Path(__file__).resolve().parents[2]
KERNEL_TOML = REPO_ROOT / ".specify" / "memory" / "kernel.toml"


def _kernel_groups() -> dict[str, list[str]]:
    """Read the live ``kernel.toml`` and return {group_name: [files...]}."""
    manifest = tomllib.loads(KERNEL_TOML.read_text())
    return {name: section["files"] for name, section in manifest.items()}


# ---------------------------------------------------------------- baselines


def test_empty_diff_passes_cleanly():
    """An empty diff is the no-op case; engine must NOT raise."""
    # Returns None on success per the contract.
    assert kernel_touch_check(diff_paths=[]) is None


def test_purely_non_kernel_diff_passes_cleanly():
    """A diff that touches only non-Kernel paths must succeed."""
    safe_paths = [
        "src/auto_invest/backtest/engine.py",
        "tests/backtest/test_named_dataset.py",
        "specs/008-backtest-engine/spec.md",
        "README.md",
    ]
    assert kernel_touch_check(diff_paths=safe_paths) is None


def test_diff_containing_kernel_toml_is_rejected():
    """The headline kernel.toml file is itself K-meta."""
    with pytest.raises(BacktestKernelTouchError):
        kernel_touch_check(diff_paths=[".specify/memory/kernel.toml"])


def test_diff_containing_constitution_is_rejected():
    """constitution.md is K-meta."""
    with pytest.raises(BacktestKernelTouchError):
        kernel_touch_check(diff_paths=[".specify/memory/constitution.md"])


# ---------------------------------------------------------------- parametrised


# One representative file per Kernel group — matches kernel.toml as of
# constitution v2.0.0 + spec 008 Increment 1 (K7 added).
KERNEL_GROUP_REPRESENTATIVES = [
    ("K1_position_sizing", "src/auto_invest/risk/gates.py"),
    ("K2_whitelist", "src/auto_invest/config/whitelist.py"),
    ("K3_judgment_points", "src/auto_invest/telemetry/meter.py"),
    ("K4_append_only_audit", "src/auto_invest/persistence/audit.py"),
    (
        "K4_append_only_audit_migration_0003",
        "src/auto_invest/persistence/migrations/0003_backtest_events.sql",
    ),
    ("K5_secret_isolation", "src/auto_invest/logging_config.py"),
    ("K6_market_hours_guard", "src/auto_invest/worker/schedule.py"),
    ("K7_named_datasets", "data/ohlcv/datasets/synthetic_shock_v1.json"),
    ("K_meta_constitution", ".specify/memory/constitution.md"),
    ("K_meta_kernel_toml", ".specify/memory/kernel.toml"),
]


@pytest.mark.parametrize("label,path", KERNEL_GROUP_REPRESENTATIVES)
def test_each_kernel_group_member_is_rejected(label: str, path: str):
    """Every group in kernel.toml must be enforced by the engine.

    Regressions here mean either the manifest changed silently or the
    engine's enforcement is no longer reading the live manifest.
    """
    with pytest.raises(BacktestKernelTouchError):
        kernel_touch_check(diff_paths=[path])


# ---------------------------------------------------------------- K7 emphasis


def test_k7_synthetic_shock_dataset_is_rejected():
    """FR-B20: the synthetic-shock dataset is a Kernel file (K7).

    This is the specific reason K7 exists separately from the spec-005
    L4 classification — runtime enforcement does not depend on the
    tuner shipping. The engine itself refuses to run a change set that
    rewrites the safety surface.
    """
    with pytest.raises(BacktestKernelTouchError):
        kernel_touch_check(diff_paths=["data/ohlcv/datasets/synthetic_shock_v1.json"])


# ---------------------------------------------------------------- coverage


def test_check_uses_live_kernel_manifest():
    """Every path listed in kernel.toml must trigger the rejection.

    Drives directly off the manifest so adding a path to kernel.toml
    immediately becomes a regression-tested file without a test edit.
    """
    groups = _kernel_groups()
    all_kernel_files = [f for files in groups.values() for f in files]
    # Sanity: the manifest exposes at least the 8 groups we expect at v2.0.0
    # + spec 008 Increment 1 (K1..K7 + K_meta).
    expected_groups = {
        "K1_position_sizing",
        "K2_whitelist",
        "K3_judgment_points",
        "K4_append_only_audit",
        "K5_secret_isolation",
        "K6_market_hours_guard",
        "K7_named_datasets",
        "K_meta",
    }
    assert expected_groups.issubset(groups.keys())

    for kernel_file in all_kernel_files:
        with pytest.raises(BacktestKernelTouchError):
            kernel_touch_check(diff_paths=[kernel_file])


def test_mixed_diff_with_one_kernel_file_is_rejected():
    """A diff that contains many safe paths plus ONE Kernel path is rejected.

    The check is any-intersect, not all-intersect: a single Kernel
    file in an otherwise non-Kernel change set still triggers refusal.
    """
    mixed = [
        "src/auto_invest/backtest/engine.py",
        "tests/backtest/test_kernel_safety.py",
        "src/auto_invest/risk/gates.py",  # <- K1
        "README.md",
    ]
    with pytest.raises(BacktestKernelTouchError):
        kernel_touch_check(diff_paths=mixed)


def test_custom_kernel_toml_path(tmp_path: Path):
    """The engine accepts an explicit kernel-toml path for testability.

    Used by spec 007's harness so it can pin the check against a
    specific git revision of the manifest rather than the working tree.
    """
    fake_manifest = tmp_path / "kernel.toml"
    fake_manifest.write_text(
        '[K_fake]\ndescription = "test-only group"\nfiles = ["just/one/file.py"]\n'
    )
    # File listed in the custom manifest is rejected.
    with pytest.raises(BacktestKernelTouchError):
        kernel_touch_check(
            diff_paths=["just/one/file.py"],
            kernel_toml=fake_manifest,
        )
    # File NOT listed is accepted (even though it is in the real
    # manifest's K1 group), proving the custom path is being honoured.
    assert (
        kernel_touch_check(
            diff_paths=["src/auto_invest/risk/gates.py"],
            kernel_toml=fake_manifest,
        )
        is None
    )
