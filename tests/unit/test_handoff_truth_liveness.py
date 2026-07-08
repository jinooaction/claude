"""스펙 107 — HANDOFF 사실성 생존성 계약 단위 테스트."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.handoff_truth_liveness import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    GATE_FAIL,
    GATE_PASS,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
    build_handoff_truth_liveness_report,
)

NOW = datetime(2026, 7, 8, 3, 0, 0, tzinfo=UTC)
REPO = Path(__file__).resolve().parents[2]


def _handoff(tmp_path: Path, main_row: str, *, pytest_row: str | None = None) -> Path:
    path = tmp_path / "HANDOFF.md"
    path.write_text(
        "\n".join(
            [
                "# Handoff",
                "",
                "| 항목 | 상태 |",
                "|------|------|",
                f"| 마지막 main 커밋 | {main_row} |",
                f"| main 테스트 | {pytest_row or '`uv run pytest -q` -> 2510 passed, 4 skipped'} |",
                "| main 린트 | `uv run ruff check src tests` -> All checks passed |",
                "| 열린 PR | 없음 |",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _patch_git(monkeypatch, fake_git) -> None:
    import auto_invest.analytics.handoff_truth_liveness as module

    monkeypatch.setattr(module.check_handoff_facts, "_git", fake_git)


def _origin_main_git(_repo, *args):
    if args == ("log", "-1", "--pretty=%h %s", "origin/main"):
        return "fe2af54 Merge pull request #369 from branch"
    return ""


def test_origin_main_match_returns_ready_report(tmp_path, monkeypatch):
    _patch_git(monkeypatch, _origin_main_git)
    report = build_handoff_truth_liveness_report(
        REPO,
        handoff_path=_handoff(tmp_path, "`fe2af54` - Merge pull request #369"),
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    assert report.overall_status == CONTRACT_READY
    assert report.run_id == "123"
    assert report.commit == "abc123"
    assert report.completed_candidate_id == COMPLETED_CANDIDATE_ID
    assert report.next_candidate_id == NEXT_AUTONOMOUS_CANDIDATE_ID
    assert report.handoff_summary["matched_baseline_kind"] == "origin_main"
    assert {gate.status for gate in report.quality_gates} == {GATE_PASS}
    assert "no orders" in report.safety_invariants
    assert "HANDOFF 사실성 생존성 계약" in report.as_markdown()
    assert report.to_dict()["allowed_baselines"][0]["short_commit"] == "fe2af54"


def test_handoff_only_first_parent_match_is_not_stale(tmp_path, monkeypatch):
    def fake_git(_repo, *args):
        if args == ("log", "-1", "--pretty=%h %s", "origin/main"):
            return "eb32b8d Merge pull request #371 from handoff"
        if args == ("rev-list", "--parents", "-n", "1", "origin/main"):
            return "eb32b8d75986295 ecc93f2112bea88 ceb5749f00d"
        if args == ("diff", "--name-only", "ecc93f2112bea88", "eb32b8d75986295"):
            return "\n".join(
                [
                    "HANDOFF.md",
                    "HANDOFF-052-AGENT-QUALITY-REDTEAM.md",
                    "specs/057-agent-quality-redteam/tasks.md",
                ]
            )
        if args == ("log", "-1", "--pretty=%h %s", "ecc93f2112bea88"):
            return "ecc93f2 Merge pull request #370 from feature"
        return ""

    _patch_git(monkeypatch, fake_git)
    report = build_handoff_truth_liveness_report(
        REPO,
        handoff_path=_handoff(tmp_path, "`ecc93f2` - Merge pull request #370"),
        now=NOW,
    )

    assert report.overall_status == CONTRACT_READY
    assert report.handoff_summary["matched_baseline_kind"] == (
        "handoff_only_first_parent"
    )
    assert report.allowed_baselines[1].kind == "handoff_only_first_parent"


def test_stale_handoff_main_row_blocks_contract(tmp_path, monkeypatch):
    _patch_git(monkeypatch, _origin_main_git)
    report = build_handoff_truth_liveness_report(
        REPO,
        handoff_path=_handoff(tmp_path, "`cbc2cd4` - Merge pull request #368"),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["handoff_fact_main_commit"].status == GATE_FAIL
    assert "stale" in gates["handoff_fact_main_commit"].summary_ko


def test_missing_handoff_blocks_contract(tmp_path, monkeypatch):
    _patch_git(monkeypatch, _origin_main_git)
    report = build_handoff_truth_liveness_report(
        REPO,
        handoff_path=tmp_path / "missing.md",
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["handoff_fact_handoff_readable"].status == GATE_FAIL


def test_expected_row_mismatch_blocks_contract(tmp_path, monkeypatch):
    _patch_git(monkeypatch, _origin_main_git)
    report = build_handoff_truth_liveness_report(
        REPO,
        handoff_path=_handoff(tmp_path, "`fe2af54` - Merge pull request #369"),
        expect_pytest="9999 passed",
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["handoff_fact_main_pytest"].status == GATE_FAIL


def test_probe_writes_json_and_markdown(tmp_path, monkeypatch, capsys):
    _patch_git(monkeypatch, _origin_main_git)
    probe_path = REPO / "scripts" / "handoff_truth_liveness_probe.py"
    spec = importlib.util.spec_from_file_location("handoff_truth_liveness_probe", probe_path)
    assert spec and spec.loader
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    json_out = tmp_path / "report.json"
    summary_out = tmp_path / "report.md"
    rc = probe.main(
        [
            "--repo-root",
            str(REPO),
            "--handoff",
            str(_handoff(tmp_path, "`fe2af54` - Merge pull request #369")),
            "--format",
            "json",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            "--now",
            "2026-07-08T03:00:00Z",
            "--run-id",
            "probe-123",
            "--commit",
            "abc123",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    written = json.loads(json_out.read_text(encoding="utf-8"))
    assert printed == written
    assert written["overall_status"] == CONTRACT_READY
    assert written["completed_candidate_id"] == COMPLETED_CANDIDATE_ID
    assert summary_out.read_text(encoding="utf-8").startswith(
        "# HANDOFF 사실성 생존성 계약"
    )
