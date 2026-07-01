"""스펙 078 — 돈 경로 게이트 정렬 probe/workflow 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from auto_invest.analytics.pipeline_liveness import default_specs

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "money_gate_alignment_probe.py"
_spec = importlib.util.spec_from_file_location("money_gate_alignment_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _write_inputs(sidecar_dir: Path) -> None:
    blocker = "전진 관측 부족: 14/20 (통계적 유의까지 더 쌓여야 함)."
    (sidecar_dir / "money-path.md").write_text(
        "## 결정 JSON\n\n```json\n"
        + json.dumps(
            {
                "stage": "ACCUMULATING_EDGE",
                "blocking_gate": blocker,
                "live_money_state": {
                    "status": "PREVIEW_ONLY",
                    "can_submit_real_orders": False,
                },
                "forward_n_obs": 14,
            },
            ensure_ascii=False,
        )
        + "\n```\n",
        encoding="utf-8",
    )
    (sidecar_dir / "capital-path-readiness.md").write_text(
        json.dumps(
            {
                "readiness_state": "ACCUMULATING_EDGE",
                "live_money_status": "PREVIEW_ONLY",
                "capital_ladder_stage": "ACCUMULATING_EDGE",
                "blocking_gate": blocker,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sidecar_dir / "edge-autoarm.md").write_text(
        "## 결정 JSON\n\n```json\n"
        + json.dumps({"action": "WAIT_EDGE"}, ensure_ascii=False)
        + "\n```\n\n## forward 판정 JSON\n\n```json\n"
        + json.dumps(
            {"verdict": "INSUFFICIENT_DATA", "n_obs": 14, "min_obs_required": 20},
            ensure_ascii=False,
        )
        + "\n```\n",
        encoding="utf-8",
    )
    (sidecar_dir / "reassign.md").write_text(
        "## 5중 게이트 결정 JSON\n\n```json\n"
        + json.dumps({"action": "HOLD", "challenger_key": None}, ensure_ascii=False)
        + "\n```\n",
        encoding="utf-8",
    )
    (sidecar_dir / "rebalance-paper-forward.md").write_text(
        "## 리더보드 결정 JSON\n\n```json\n"
        + json.dumps({"observation_health": "OK", "known_count": 7, "max_n_obs": 14})
        + "\n```\n",
        encoding="utf-8",
    )
    (sidecar_dir / "pipeline-liveness.md").write_text(
        "## 결정 JSON\n\n```json\n{\"overall\":\"OK\",\"checks\":[]}\n```\n",
        encoding="utf-8",
    )
    (sidecar_dir / "autonomous-work-execution.md").write_text(
        json.dumps({"selected_work": {"candidate_id": "candidate-fd04772a23c5"}}),
        encoding="utf-8",
    )
    (sidecar_dir / "kis-smoke.md").write_text(
        "| timestamp_utc | 2026-07-01T14:13:22Z |\n"
        "| smoke_state | success |\n"
        "| key_valid | true |\n",
        encoding="utf-8",
    )


def test_manifest_matches_contract(capsys):
    rc = probe_main(["--manifest"])

    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == [
        "money-path\tautomation/money-path-last-run\tLAST_RUN.md",
        (
            "capital-path-readiness\tautomation/capital-path-readiness-last-run\t"
            "capital_path_readiness.json"
        ),
        "edge-autoarm\tautomation/edge-autoarm-last-run\tLAST_RUN.md",
        "reassign\tautomation/reassign-last-run\tLAST_RUN.md",
        "rebalance-paper-forward\tautomation/rebalance-paper-forward-last-run\tLAST_RUN.md",
        "pipeline-liveness\tautomation/pipeline-liveness-last-run\tLAST_RUN.md",
        (
            "autonomous-work-execution\tautomation/autonomous-work-execution-last-run\t"
            "autonomous_work_execution.json"
        ),
        "kis-smoke\tautomation/kis-smoke-last-run\tLAST_RUN.md",
    ]


def test_probe_writes_json_and_markdown(tmp_path, capsys):
    _write_inputs(tmp_path)
    json_out = tmp_path / "money_gate_alignment.json"
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
            "2026-07-01T09:20:00Z",
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
    assert written["overall_status"] == "ALIGNED_WAITING"
    assert written["selected_work_candidate"] == "candidate-fd04772a23c5"
    assert written["run_id"] == "123"
    assert written["commit"] == "abc123"
    assert "돈 경로 게이트 정렬 루프" in summary_out.read_text(encoding="utf-8")


def test_pipeline_liveness_registers_money_gate_alignment():
    specs = {spec.key: spec for spec in default_specs()}

    assert "money-gate-alignment" in specs
    assert specs["money-gate-alignment"].branch == "automation/money-gate-alignment-last-run"
    assert specs["money-gate-alignment"].critical is False


def test_workflow_stays_read_only_safety_contract():
    workflow = (_ROOT / ".github" / "workflows" / "money-gate-alignment.yml").read_text(
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
    assert "automation/money-gate-alignment-last-run" in workflow
