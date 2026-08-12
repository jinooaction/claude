"""스펙 132 — 레짐·비용 견고성 no-live probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_HELPERS_PATH = _ROOT / "tests" / "unit" / "test_broad_no_edge_regime_cost_robustness.py"
_helpers_spec = importlib.util.spec_from_file_location(
    "test_broad_no_edge_regime_cost_robustness_helpers",
    _HELPERS_PATH,
)
assert _helpers_spec and _helpers_spec.loader
_helpers = importlib.util.module_from_spec(_helpers_spec)
_helpers_spec.loader.exec_module(_helpers)

_PROBE_PATH = _ROOT / "scripts" / "broad_no_edge_regime_cost_robustness_probe.py"
_spec = importlib.util.spec_from_file_location(
    "broad_no_edge_regime_cost_robustness_probe",
    _PROBE_PATH,
)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
main = _probe.main


def _write_sidecars(path: Path) -> None:
    values = {
        "regime-stratify": _helpers._regime_stratify(),
        "execution-quality": _helpers._execution_quality(),
        "money-path": _helpers._money_path(),
        "edge-autoarm": _helpers._edge_autoarm(),
        "rebalance-paper-forward": _helpers._forward_sidecar(),
        "released-work": _helpers._released(),
        "evolution-ledger": _helpers._ledger(),
        "pipeline-liveness": _helpers._pipeline(),
    }
    for key, text in values.items():
        (path / f"{key}.md").write_text(text, encoding="utf-8")


def test_probe_manifest(capsys):
    assert main(["--manifest"]) == 0

    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == [
        "regime-stratify\tautomation/regime-stratify-last-run\tLAST_RUN.md",
        "execution-quality\tautomation/execution-quality-last-run\tLAST_RUN.md",
        "money-path\tautomation/money-path-last-run\tLAST_RUN.md",
        "edge-autoarm\tautomation/edge-autoarm-last-run\tLAST_RUN.md",
        "rebalance-paper-forward\tautomation/rebalance-paper-forward-last-run\tLAST_RUN.md",
        "released-work\tautomation/released-work-last-run\treleased_work.json",
        "evolution-ledger\tautomation/autonomous-evolution-last-run\tlearning_ledger.json",
        "pipeline-liveness\tautomation/pipeline-liveness-last-run\tLAST_RUN.md",
    ]


def test_probe_writes_json_and_markdown(tmp_path, capsys):
    _write_sidecars(tmp_path)
    json_out = tmp_path / "report.json"
    summary_out = tmp_path / "report.md"

    assert (
        main(
            [
                "--sidecar-dir",
                str(tmp_path),
                "--json",
                "--json-out",
                str(json_out),
                "--summary-out",
                str(summary_out),
                "--now",
                "2026-08-12T12:00:00Z",
                "--run-id",
                "test-run",
                "--commit",
                "abc123",
            ]
        )
        == 0
    )

    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert file_payload["run_id"] == "test-run"
    assert file_payload["commit"] == "abc123"
    assert file_payload["overall_status"] == "CONTRACT_READY"
    assert (
        file_payload["completed_candidate_id"]
        == "candidate-broad-no-edge-regime-cost-robustness-experiment"
    )
    assert "레짐·비용 견고성 no-live 실험 계약" in summary_out.read_text(
        encoding="utf-8"
    )
