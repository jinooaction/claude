"""스펙 083 — 실행 품질 probe/workflow 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "execution_quality_probe.py"
_FIXTURES = _ROOT / "tests" / "fixtures" / "execution_quality"
_WORKFLOW = _ROOT / ".github" / "workflows" / "execution-quality.yml"

_spec = importlib.util.spec_from_file_location("execution_quality_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_manifest_matches_contract(capsys) -> None:
    rc = probe_main(["--manifest"])

    assert rc == 0
    assert capsys.readouterr().out.strip().splitlines() == [
        (
            "opportunity-monitor\tautomation/rebalance-micro-gtaa-last-run\t"
            "opportunity_monitor.json"
        ),
        (
            "opportunity-history\tautomation/rebalance-micro-gtaa-last-run\t"
            "opportunity_history.json"
        ),
        "rebalance-micro-gtaa\tautomation/rebalance-micro-gtaa-last-run\tLAST_RUN.md",
        "kis-smoke\tautomation/kis-smoke-last-run\tLAST_RUN.md",
    ]


def test_probe_writes_json_and_markdown(tmp_path, capsys) -> None:
    for fixture in _FIXTURES.glob("*.md"):
        (tmp_path / fixture.name).write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    json_out = tmp_path / "execution_quality.json"
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
            "2026-07-02T07:30:00Z",
            "--run-id",
            "083",
            "--commit",
            "abc1234",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    written = json.loads(json_out.read_text(encoding="utf-8"))
    assert printed == written
    assert written["overall_status"] == "OBSERVE"
    assert written["broker_rejections"]["kis_msg_codes"] == {"APBK1672": 2}
    assert "실행 품질 패키지" in summary_out.read_text(encoding="utf-8")


def test_workflow_stays_read_only_and_publishes_sidecar() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")

    forbidden = [
        "KIS_",
        "ssh ",
        "ssh -",
        "rebalance-live --mode live",
        "--confirm-live",
        "place-order",
        "submit-order",
        "gh pr create",
        "git push origin main",
    ]
    for token in forbidden:
        assert token not in text
    assert "scripts/execution_quality_probe.py --manifest" in text
    assert "automation/execution-quality-last-run" in text
    assert "execution_quality.json" in text
