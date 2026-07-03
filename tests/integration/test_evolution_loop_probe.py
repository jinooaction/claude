"""스펙 067 — 자율 성장 루프 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _REPO_ROOT / "scripts" / "evolution_loop_probe.py"
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "evolution_loop" / "fresh"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "autonomous-evolution-loop.yml"

_spec = importlib.util.spec_from_file_location("evolution_loop_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_probe_manifest_lists_required_sidecars(capsys) -> None:
    rc = probe_main(["--manifest"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "money-path\tautomation/money-path-last-run\tLAST_RUN.md" in out
    assert "reassign\tautomation/reassign-last-run\tLAST_RUN.md" in out
    assert "pipeline-liveness\tautomation/pipeline-liveness-last-run\tLAST_RUN.md" in out
    assert "promote-readiness\tautomation/promote-readiness-last-run\tLAST_RUN.md" in out
    assert (
        "capital-path-readiness\tautomation/capital-path-readiness-last-run\tcapital_path_readiness.json"
        in out
    )
    assert "released-work\tautomation/released-work-last-run\treleased_work.json" in out
    assert "kis-smoke\tautomation/kis-smoke-last-run\tLAST_RUN.md" in out
    assert (
        "execution-quality\tautomation/execution-quality-last-run\texecution_quality.json"
        in out
    )
    assert (
        "promotion-summary\tautomation/autonomous-promotion-last-run\tpromotion_summary.json"
        in out
    )


def test_probe_json_output_includes_expected_sections(capsys) -> None:
    rc = probe_main(
        [
            "--evidence-dir",
            str(_FIXTURES),
            "--json",
            "--now",
            "2026-06-29T01:00:00Z",
            "--commit",
            "abc1234",
            "--run-id",
            "test-run",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "test-run"
    assert payload["top_breakthrough_candidates"]
    assert payload["safe_high_leverage_work"]
    assert "market_observation" in payload["evidence_dependencies"]
    assert payload["operator_review"] == []
    assert any(surface["key"] == "handoff" for surface in payload["evidence_surfaces"])


def test_probe_writes_sidecar_artifacts(tmp_path, capsys) -> None:
    summary = tmp_path / "LAST_RUN.md"
    summary_json = tmp_path / "evolution_summary.json"
    ledger = tmp_path / "learning_ledger.json"
    backlog = tmp_path / "candidate_backlog.json"
    rc = probe_main(
        [
            "--evidence-dir",
            str(_FIXTURES),
            "--summary-out",
            str(summary),
            "--json-out",
            str(summary_json),
            "--ledger-out",
            str(ledger),
            "--candidate-backlog-out",
            str(backlog),
            "--now",
            "2026-06-29T01:00:00Z",
            "--commit",
            "abc1234",
        ]
    )
    assert rc == 0
    assert "자율 성장 루프" in summary.read_text(encoding="utf-8")
    assert json.loads(summary_json.read_text(encoding="utf-8"))["candidates"]
    assert json.loads(ledger.read_text(encoding="utf-8"))["entries"]
    assert json.loads(backlog.read_text(encoding="utf-8"))["candidates"]
    assert "주문, 자본, whitelist, caps, live 전략은 변경하지 않았습니다" in capsys.readouterr().out


def test_probe_replays_learning_ledger_suppression(tmp_path, capsys) -> None:
    ledger_in = tmp_path / "learning_ledger_in.json"
    summary_json = tmp_path / "evolution_summary.json"
    ledger_out = tmp_path / "learning_ledger_out.json"
    backlog = tmp_path / "candidate_backlog.json"
    candidate_id = "candidate-fa66202bf496"
    ledger_in.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "entries": [
                    {
                        "entry_id": "ledger-fa66202bf496-hold",
                        "candidate_id": candidate_id,
                        "decision": "evidence_dependent",
                        "reason_ko": "결과 실행기 검증만 있고 다음 sidecar 재검토 전이라 보류",
                        "evidence_package_id": "candidate-result-executor:pkg-ae5a47448ec9",
                        "next_recheck_condition": "released-work 최신 실행 뒤 재검토",
                        "created_at_utc": "2026-07-03T00:00:00Z",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = probe_main(
        [
            "--evidence-dir",
            str(_FIXTURES),
            "--ledger-json",
            str(ledger_in),
            "--json-out",
            str(summary_json),
            "--ledger-out",
            str(ledger_out),
            "--candidate-backlog-out",
            str(backlog),
            "--json",
            "--now",
            "2026-06-29T01:00:00Z",
            "--commit",
            "abc1234",
            "--run-id",
            "test-run",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    candidates = {candidate["candidate_id"]: candidate for candidate in payload["candidates"]}
    assert candidates[candidate_id]["status"] == "evidence_dependent"
    assert candidate_id not in payload["safe_high_leverage_work"]
    backlog_candidates = {
        candidate["candidate_id"]: candidate
        for candidate in json.loads(backlog.read_text(encoding="utf-8"))["candidates"]
    }
    assert backlog_candidates[candidate_id]["status"] == "evidence_dependent"
    assert json.loads(ledger_out.read_text(encoding="utf-8"))["entries"][0][
        "evidence_package_id"
    ] == "candidate-result-executor:pkg-ae5a47448ec9"


def test_probe_writes_source_diversification_candidate_when_static_queue_is_closed(
    tmp_path, capsys
) -> None:
    for source in _FIXTURES.glob("*.md"):
        (tmp_path / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    seed_rc = probe_main(
        [
            "--evidence-dir",
            str(tmp_path),
            "--candidate-backlog-out",
            str(tmp_path / "seed_backlog.json"),
            "--json",
            "--now",
            "2026-06-29T01:00:00Z",
            "--commit",
            "abc1234",
            "--run-id",
            "seed",
        ]
    )
    assert seed_rc == 0
    capsys.readouterr()
    seed = json.loads((tmp_path / "seed_backlog.json").read_text(encoding="utf-8"))
    (tmp_path / "released-work.md").write_text(
        json.dumps(
            {
                "released_work": [
                    {"candidate_id": candidate["candidate_id"], "status": "released"}
                    for candidate in seed["candidates"]
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "capital-path-readiness.md").write_text(
        json.dumps(
            {
                "timestamp_utc": "2026-06-29T00:55:00Z",
                "observability_issues": [
                    {
                        "issue_id": "released-candidate-echo:test",
                        "issue_type": "released_candidate_echo",
                        "source_key": "released-work",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = probe_main(
        [
            "--evidence-dir",
            str(tmp_path),
            "--candidate-backlog-out",
            str(tmp_path / "candidate_backlog.json"),
            "--json",
            "--now",
            "2026-06-29T01:00:00Z",
            "--commit",
            "abc1234",
            "--run-id",
            "test-run",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    candidates = {candidate["candidate_id"]: candidate for candidate in payload["candidates"]}
    assert candidates["candidate-source-diversification-sidecar-bottleneck"]["status"] == "new"
    assert (
        "candidate-source-diversification-sidecar-bottleneck"
        in payload["safe_high_leverage_work"]
    )


def test_autonomous_evolution_workflow_is_read_only_and_publishes_sidecar() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" in text and "workflow_dispatch:" in text
    assert "automation/autonomous-evolution-last-run" in text
    assert "evolution_loop_probe.py --manifest" in text
    assert "--candidate-backlog-out" in text
    assert "src/auto_invest/analytics/execution_quality.py" in text
    assert ".github/workflows/execution-quality.yml" in text
    assert "VULTR_SSH" not in text
    assert "KIS_" not in text
    assert "ssh " not in text and "ssh -" not in text
    assert text.count("set -euo pipefail") == 4
    assert "no orders, no capital change, no whitelist/caps change, no live strategy change" in text
