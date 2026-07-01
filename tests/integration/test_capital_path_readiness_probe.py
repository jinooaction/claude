"""스펙 076 — 자본 경로 준비도 probe/workflow 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from auto_invest.analytics.pipeline_liveness import default_specs

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "capital_path_readiness_probe.py"
_spec = importlib.util.spec_from_file_location("capital_path_readiness_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _write_money_path(sidecar_dir: Path) -> None:
    payload = {
        "stage": "ACCUMULATING_EDGE",
        "blocking_gate": "전진 관측 부족: 13/20",
        "live_money_state": {"status": "PREVIEW_ONLY", "can_submit_real_orders": False},
    }
    (sidecar_dir / "money-path.md").write_text(
        "## 결정 JSON\n\n```json\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n```\n",
        encoding="utf-8",
    )


def test_manifest_matches_contract(capsys):
    rc = probe_main(["--manifest"])

    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == [
        "money-path\tautomation/money-path-last-run\tLAST_RUN.md",
        "edge-autoarm\tautomation/edge-autoarm-last-run\tLAST_RUN.md",
        "reassign\tautomation/reassign-last-run\tLAST_RUN.md",
        "rebalance-paper-forward\tautomation/rebalance-paper-forward-last-run\tLAST_RUN.md",
        "kis-smoke\tautomation/kis-smoke-last-run\tLAST_RUN.md",
        "autonomous-promotion\tautomation/autonomous-promotion-last-run\tpromotion_summary.json",
        "evolution-backlog\tautomation/autonomous-evolution-last-run\tcandidate_backlog.json",
        "evolution-ledger\tautomation/autonomous-evolution-last-run\tlearning_ledger.json",
    ]


def test_probe_writes_json_and_markdown(tmp_path, capsys):
    _write_money_path(tmp_path)
    (tmp_path / "evolution-backlog.md").write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "evolution-ledger.md").write_text(
        json.dumps({"entries": []}),
        encoding="utf-8",
    )

    json_out = tmp_path / "capital_path_readiness.json"
    summary_out = tmp_path / "LAST_RUN.md"
    rc = probe_main(
        [
            "--evidence-dir",
            str(tmp_path),
            "--json",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            "--now",
            "2026-07-01T08:10:00Z",
            "--run-id",
            "123",
            "--commit",
            "abc123",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    written = json.loads(json_out.read_text(encoding="utf-8"))
    assert printed == written
    assert written["readiness_state"] == "ACCUMULATING_EDGE"
    assert written["live_money_status"] == "PREVIEW_ONLY"
    assert written["run_id"] == "123"
    assert written["commit"] == "abc123"
    assert "자본 경로 준비도 루프" in summary_out.read_text(encoding="utf-8")


def test_pipeline_liveness_registers_capital_path_readiness():
    specs = {spec.key: spec for spec in default_specs()}

    assert "capital-path-readiness" in specs
    assert specs["capital-path-readiness"].branch == (
        "automation/capital-path-readiness-last-run"
    )
    assert specs["capital-path-readiness"].critical is False


def test_workflow_stays_read_only_safety_contract():
    workflow = (_ROOT / ".github" / "workflows" / "capital-path-readiness.yml").read_text(
        encoding="utf-8"
    )

    forbidden = [
        "KIS_",
        "ssh ",
        "ssh -",
        "rebalance-live --mode live",
        "--confirm-live",
        "place-order",
        "submit-order",
    ]
    for token in forbidden:
        assert token not in workflow
    assert "automation/capital-path-readiness-last-run" in workflow
