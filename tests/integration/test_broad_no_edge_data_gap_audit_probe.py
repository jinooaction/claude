"""스펙 133 — 데이터 결측 감사 no-live probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_HELPERS_PATH = _ROOT / "tests" / "unit" / "test_broad_no_edge_data_gap_audit.py"
_helpers_spec = importlib.util.spec_from_file_location(
    "test_broad_no_edge_data_gap_audit_helpers",
    _HELPERS_PATH,
)
assert _helpers_spec and _helpers_spec.loader
_helpers = importlib.util.module_from_spec(_helpers_spec)
_helpers_spec.loader.exec_module(_helpers)

_PROBE_PATH = _ROOT / "scripts" / "broad_no_edge_data_gap_audit_probe.py"
_spec = importlib.util.spec_from_file_location(
    "broad_no_edge_data_gap_audit_probe",
    _PROBE_PATH,
)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
main = _probe.main


def _write_sidecars(path: Path) -> None:
    values = _helpers._evidence()
    for key, text in values.items():
        (path / f"{key}.md").write_text(text, encoding="utf-8")


def test_probe_manifest(capsys):
    assert main(["--manifest"]) == 0

    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == [
        "public-data-last-run\tautomation/public-data\tLAST_RUN.md",
        "public-data-summary\tautomation/public-data\tsummary.json",
        "public-data-regime\tautomation/public-data\tregime.json",
        "public-data-regime-timeline\tautomation/public-data\tregime_timeline.csv",
        "regime-stratify\tautomation/regime-stratify-last-run\tLAST_RUN.md",
        "rebalance-paper-forward\tautomation/rebalance-paper-forward-last-run\tLAST_RUN.md",
        "money-path\tautomation/money-path-last-run\tLAST_RUN.md",
        "edge-autoarm\tautomation/edge-autoarm-last-run\tLAST_RUN.md",
        "released-work\tautomation/released-work-last-run\treleased_work.json",
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
                "2026-08-12T13:00:00Z",
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
        == "candidate-broad-no-edge-data-gap-audit"
    )
    assert "데이터 결측 원인 감사" in summary_out.read_text(encoding="utf-8")
