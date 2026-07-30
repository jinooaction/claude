"""스펙 079 — 완료 후보 소비 장부 probe/workflow 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.released_work import scan_released_work

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "released_work_probe.py"
_spec = importlib.util.spec_from_file_location("released_work_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _write_released_spec(repo_root: Path) -> None:
    contracts_dir = repo_root / "specs" / "078-money-gate-alignment-loop" / "contracts"
    contracts_dir.mkdir(parents=True)
    (contracts_dir.parent / "tasks.md").write_text("- [x] 구현 완료\n", encoding="utf-8")
    (contracts_dir / "money-gate-alignment.md").write_text(
        '{ "selected_work_candidate": "candidate-fd04772a23c5" }\n',
        encoding="utf-8",
    )


def test_probe_writes_released_work_json_and_markdown(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _write_released_spec(repo_root)
    json_out = tmp_path / "released_work.json"
    summary_out = tmp_path / "LAST_RUN.md"

    rc = probe_main(
        [
            "--repo-root",
            str(repo_root),
            "--json",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            "--now",
            "2026-07-02T09:05:00Z",
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
    assert written["overall_status"] == "OK"
    assert written["released_work"][0]["candidate_id"] == "candidate-fd04772a23c5"
    assert "완료 후보 소비 장부" in summary_out.read_text(encoding="utf-8")


def test_workflow_stays_read_only_safety_contract():
    workflow = (_ROOT / ".github" / "workflows" / "released-work-ledger.yml").read_text(
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
        "gh pr create",
        "git push origin main",
    ]
    for token in forbidden:
        assert token not in workflow
    assert "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert "${GH_TOKEN}" in workflow
    assert "${GITHUB_TOKEN}" not in workflow
    assert "automation/released-work-last-run" in workflow
    assert "scripts/released_work_probe.py" in workflow


def test_current_evidence_source_diversification_candidate_is_released():
    report = scan_released_work(
        _ROOT,
        now=datetime(2026, 7, 30, 22, 30, 0, tzinfo=UTC),
        run_id="test",
        commit="test",
    )

    assert any(
        entry.candidate_id == "candidate-evidence-source-diversification-validation-failures"
        and entry.spec_id == "120-evidence-based-candidate-source-diversification"
        and entry.source_field == "completed_candidate_id"
        for entry in report.released_work
    )
