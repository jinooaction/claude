from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

_PROBE_PATH = Path("scripts/usda_crop_supply_demand_factory_probe.py")
_SPEC = importlib.util.spec_from_file_location("usda_crop_supply_demand_factory_probe", _PROBE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


def test_probe_exposes_offline_inputs_and_no_money_boundary() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/usda_crop_supply_demand_factory_probe.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--wasde-index-dir" in result.stdout
    assert "--wasde-data-dir" in result.stdout
    assert "--prior-factory-json" in result.stdout
    assert "--controls-json" in result.stdout

    probe = Path("scripts/usda_crop_supply_demand_factory_probe.py").read_text(
        encoding="utf-8"
    )
    assert "run_usda_crop_supply_demand_factory" in probe
    assert "KIS_" not in probe
    assert "auto_invest.brokers" not in probe


def test_strategy_factory_workflow_preserves_usda_as_the_720_trial_predecessor() -> None:
    workflow = Path(".github/workflows/autonomous-strategy-factory.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/usda_crop_supply_demand_factory_probe.py" in workflow
    assert "usda_crop_supply_demand_factory.json" in workflow
    assert (
        'global_audit_trial_count\' /tmp/usda_crop_supply_demand_factory.json)" = "720'
        in workflow
    )
    assert (
        'multiplicity_trial_count\' /tmp/usda_crop_supply_demand_factory.json)" = "16'
        in workflow
    )
    assert "--prior-factory-json /tmp/usda_crop_supply_demand_factory.json" in workflow


def test_transient_usda_5xx_is_retried_without_hiding_final_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    def flaky_urlopen(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise urllib.error.HTTPError(request.full_url, 500, "temporary", {}, None)
        return io.BytesIO(b"ok")

    monkeypatch.setattr(probe.urllib.request, "urlopen", flaky_urlopen)
    monkeypatch.setattr(probe.time, "sleep", delays.append)

    assert probe._read_bytes(None, "https://example.test/wasde") == b"ok"
    assert attempts == 3
    assert delays == [1.0, 2.0]


def test_non_retryable_usda_4xx_fails_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def rejected_urlopen(request, timeout):
        nonlocal attempts
        attempts += 1
        raise urllib.error.HTTPError(request.full_url, 404, "missing", {}, None)

    monkeypatch.setattr(probe.urllib.request, "urlopen", rejected_urlopen)

    with pytest.raises(urllib.error.HTTPError):
        probe._read_bytes(None, "https://example.test/missing")
    assert attempts == 1
