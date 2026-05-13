"""FR-B12 (kernel pre-flight) safety-contract tests."""

from __future__ import annotations

from auto_invest.backtest.kernel_pre_flight import (
    PreFlightResult,
    parse_git_porcelain,
)


def test_parse_porcelain_handles_modified_added_untracked():
    output = (
        " M src/auto_invest/risk/gates.py\n"
        "A  src/auto_invest/backtest/data_model.py\n"
        "?? data/backtest/runid/\n"
    )
    paths = parse_git_porcelain(output)
    assert "src/auto_invest/risk/gates.py" in paths
    assert "src/auto_invest/backtest/data_model.py" in paths
    assert "data/backtest/runid/" in paths


def test_parse_porcelain_handles_rename_arrow():
    output = 'R  "old/file.py" -> "new/file.py"\n'
    paths = parse_git_porcelain(output)
    assert paths == ["new/file.py"]


def test_parse_porcelain_ignores_blank_lines():
    assert parse_git_porcelain("\n   \n") == []


def test_kernel_pre_flight_detects_k1_touch():
    from auto_invest.deploy import kernel_diff_check, load_kernel_manifest

    manifest = load_kernel_manifest()
    report = kernel_diff_check(
        ["src/auto_invest/risk/gates.py"],
        manifest=manifest,
    )
    assert not report.is_clean
    assert "K1_position_sizing" in report.touched_groups


def test_kernel_pre_flight_clean_tree_returns_touched_false():
    from auto_invest.deploy import kernel_diff_check, load_kernel_manifest

    manifest = load_kernel_manifest()
    report = kernel_diff_check(
        ["src/auto_invest/backtest/data_model.py", "tests/unit/test_anything.py"],
        manifest=manifest,
    )
    assert report.is_clean


def test_pre_flight_result_default_is_safe():
    r = PreFlightResult(touched=False)
    assert r.paths == []
    assert r.groups == []
