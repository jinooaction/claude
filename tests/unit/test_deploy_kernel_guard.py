"""Tests for `auto_invest.deploy.kernel_guard` (spec 006 FR-D13, constitution IX)."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_invest.deploy.kernel_guard import (
    KernelManifestError,
    kernel_diff_check,
    load_kernel_manifest,
)


def test_load_default_manifest_succeeds():
    manifest = load_kernel_manifest(Path(".specify/memory/kernel.toml"))
    # Must have all 7 groups including K_meta.
    expected = {
        "K1_position_sizing",
        "K2_whitelist",
        "K3_judgment_points",
        "K4_append_only_audit",
        "K5_secret_isolation",
        "K6_market_hours_guard",
        "K_meta",
    }
    assert expected.issubset(set(manifest.groups))


def test_clean_diff_passes(tmp_path: Path):
    manifest = load_kernel_manifest(Path(".specify/memory/kernel.toml"))
    report = kernel_diff_check(
        ["src/auto_invest/reports/daily.py", "tests/unit/test_audit.py"],
        manifest=manifest,
    )
    assert report.is_clean is True
    assert report.touches == ()
    assert "no kernel files" in report.reason()


def test_position_sizing_touch_detected():
    manifest = load_kernel_manifest(Path(".specify/memory/kernel.toml"))
    report = kernel_diff_check(
        ["src/auto_invest/risk/gates.py"],
        manifest=manifest,
    )
    assert report.is_clean is False
    assert "K1_position_sizing" in report.touched_groups
    assert "src/auto_invest/risk/gates.py" in report.reason()


def test_whitelist_touch_detected():
    manifest = load_kernel_manifest(Path(".specify/memory/kernel.toml"))
    report = kernel_diff_check(
        ["src/auto_invest/config/whitelist.py"],
        manifest=manifest,
    )
    assert "K2_whitelist" in report.touched_groups


def test_audit_touch_detected():
    manifest = load_kernel_manifest(Path(".specify/memory/kernel.toml"))
    report = kernel_diff_check(
        ["src/auto_invest/persistence/audit.py"],
        manifest=manifest,
    )
    assert "K4_append_only_audit" in report.touched_groups


def test_kernel_meta_self_protection():
    """K-meta protects the kernel manifest itself + the constitution."""
    manifest = load_kernel_manifest(Path(".specify/memory/kernel.toml"))
    report_constitution = kernel_diff_check(
        [".specify/memory/constitution.md"],
        manifest=manifest,
    )
    report_manifest = kernel_diff_check(
        [".specify/memory/kernel.toml"],
        manifest=manifest,
    )
    assert "K_meta" in report_constitution.touched_groups
    assert "K_meta" in report_manifest.touched_groups


def test_multiple_kernel_groups_in_one_diff():
    manifest = load_kernel_manifest(Path(".specify/memory/kernel.toml"))
    report = kernel_diff_check(
        [
            "src/auto_invest/risk/gates.py",  # K1
            "src/auto_invest/config/whitelist.py",  # K2
            "src/auto_invest/reports/daily.py",  # not kernel
        ],
        manifest=manifest,
    )
    assert report.is_clean is False
    assert "K1_position_sizing" in report.touched_groups
    assert "K2_whitelist" in report.touched_groups
    # Non-kernel file is not reported as a touch.
    assert all(t.path != "src/auto_invest/reports/daily.py" for t in report.touches)


def test_kernel_paths_normalize_leading_dot_slash():
    manifest = load_kernel_manifest(Path(".specify/memory/kernel.toml"))
    report = kernel_diff_check(
        ["./src/auto_invest/persistence/audit.py"],
        manifest=manifest,
    )
    assert report.is_clean is False
    assert "K4_append_only_audit" in report.touched_groups


def test_missing_manifest_raises(tmp_path: Path):
    with pytest.raises(KernelManifestError):
        load_kernel_manifest(tmp_path / "nope.toml")


def test_empty_manifest_rejected(tmp_path: Path):
    p = tmp_path / "empty.toml"
    p.write_text("", encoding="utf-8")
    with pytest.raises(KernelManifestError):
        load_kernel_manifest(p)


def test_missing_k_meta_rejected(tmp_path: Path):
    """A manifest without K_meta cannot enforce its own fixed-point."""
    p = tmp_path / "bad.toml"
    p.write_text(
        """
[K1_position_sizing]
description = "test"
files = ["src/auto_invest/risk/gates.py"]
""",
        encoding="utf-8",
    )
    with pytest.raises(KernelManifestError, match="K_meta"):
        load_kernel_manifest(p)


def test_directory_prefix_protects_recursively(tmp_path: Path):
    """Directory entries (ending with /) cover everything underneath."""
    p = tmp_path / "dir.toml"
    p.write_text(
        """
[K1_position_sizing]
description = "test"
files = ["src/auto_invest/risk/"]

[K_meta]
description = "self"
files = [".specify/memory/kernel.toml"]
""",
        encoding="utf-8",
    )
    manifest = load_kernel_manifest(p)
    report = kernel_diff_check(
        [
            "src/auto_invest/risk/gates.py",
            "src/auto_invest/risk/__init__.py",
            "src/auto_invest/risk/anything_new.py",
        ],
        manifest=manifest,
    )
    assert all("K1_position_sizing" in t.groups for t in report.touches)
    assert len(report.touches) == 3


def test_invalid_toml_raises(tmp_path: Path):
    p = tmp_path / "bad.toml"
    p.write_text("this is { not valid", encoding="utf-8")
    with pytest.raises(KernelManifestError, match="not valid TOML"):
        load_kernel_manifest(p)
