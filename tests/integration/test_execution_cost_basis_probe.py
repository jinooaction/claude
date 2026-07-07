"""스펙 104 - 체결 비용 기준 계약 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "execution_cost_basis_probe.py"
_spec = importlib.util.spec_from_file_location("execution_cost_basis_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _markdown_json(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _write_sidecars(root: Path, *, with_ready_basis: bool = False) -> None:
    basis = (
        {
            "basis_complete": True,
            "accepted_or_filled_orders": 2,
            "measurable_fills": 2,
            "turnover_observed": True,
            "avg_slippage_bps": 5.0,
        }
        if with_ready_basis
        else None
    )
    execution_payload = {
        "overall_status": "OBSERVE",
        "broker_rejections": {"rejected_orders": 2},
        "live_gate": {"latest_signal": "INTENT_LOSS"},
    }
    if basis is not None:
        execution_payload["execution_cost_basis"] = basis

    execution_quality = root / "automation" / "execution-quality-last-run"
    execution_quality.mkdir(parents=True)
    (execution_quality / "LAST_RUN.md").write_text(
        _markdown_json(execution_payload),
        encoding="utf-8",
    )

    kis_smoke = root / "automation" / "kis-smoke-last-run"
    kis_smoke.mkdir(parents=True)
    (kis_smoke / "LAST_RUN.md").write_text(
        "# KIS smoke\n\n| smoke_state | success |\n| smoke_exit | 0 |\n",
        encoding="utf-8",
    )

    micro = root / "automation" / "rebalance-micro-gtaa-last-run"
    micro.mkdir(parents=True)
    (micro / "LAST_RUN.md").write_text(
        "## 라이브 전 전략 의도 게이트\n```json\n"
        + _json({"ok": False, "latest_signal": "INTENT_LOSS"})
        + "\n```\n",
        encoding="utf-8",
    )

    money_path = root / "automation" / "money-path-last-run"
    money_path.mkdir(parents=True)
    (money_path / "LAST_RUN.md").write_text(
        _markdown_json(
            {
                "overall_status": "OK",
                "live_money_state": {
                    "status": "PREVIEW_ONLY",
                    "can_submit_real_orders": False,
                    "armed": False,
                },
                "last_run": {
                    "accepted_or_filled_count": 2 if with_ready_basis else 0,
                    "broker_rejected_count": 0,
                },
            }
        ),
        encoding="utf-8",
    )

    liveness = root / "automation" / "pipeline-liveness-last-run"
    liveness.mkdir(parents=True)
    (liveness / "LAST_RUN.md").write_text(
        _markdown_json({"schema_version": "1.0", "overall": "OK", "checks": []}),
        encoding="utf-8",
    )

    released_work = root / "automation" / "released-work-last-run"
    released_work.mkdir(parents=True)
    (released_work / "released_work.json").write_text(
        _json(
            {
                "released_work": [
                    {
                        "candidate_id": "candidate-execution-cost-basis-contract",
                        "status": "released",
                        "reason_ko": "스펙 104 완료",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    capital = root / "automation" / "capital-path-readiness-last-run"
    capital.mkdir(parents=True)
    (capital / "capital_path_readiness.json").write_text(
        _json(
            {
                "readiness_state": "ACCUMULATING_EDGE",
                "live_money_status": "PREVIEW_ONLY",
                "capital_ladder_status": "BLOCKED",
            }
        ),
        encoding="utf-8",
    )


def _write_manifest(root: Path) -> Path:
    manifest = root / "manifest.tsv"
    manifest.write_text(
        "\n".join(
            [
                "execution-quality\tautomation/execution-quality-last-run\tLAST_RUN.md",
                "kis-smoke\tautomation/kis-smoke-last-run\tLAST_RUN.md",
                "rebalance-micro-gtaa\tautomation/rebalance-micro-gtaa-last-run\tLAST_RUN.md",
                "money-path\tautomation/money-path-last-run\tLAST_RUN.md",
                "pipeline-liveness\tautomation/pipeline-liveness-last-run\tLAST_RUN.md",
                "released-work\tautomation/released-work-last-run\treleased_work.json",
                (
                    "capital-path-readiness\tautomation/capital-path-readiness-last-run\t"
                    "capital_path_readiness.json"
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def test_probe_repo_root_mode_writes_wait_json_and_markdown(tmp_path, capsys):
    _write_sidecars(tmp_path)
    json_out = tmp_path / "execution_cost_basis.json"
    summary_out = tmp_path / "LAST_RUN.md"

    rc = probe_main(
        [
            "--repo-root",
            str(tmp_path),
            "--format",
            "json",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            "--now",
            "2026-07-07T01:30:00Z",
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
    assert written["overall_status"] == "OBSERVATION_WAIT"
    assert written["run_id"] == "123"
    assert written["commit"] == "abc123"
    assert written["completed_candidate_id"] == "candidate-execution-cost-basis-contract"
    assert written["next_candidate_id"] == "candidate-broker-diagnostic-liveness-contract"
    assert written["cost_basis_summary"]["execution_quality_has_cost_basis"] is False
    assert "체결 비용 기준" in summary_out.read_text(encoding="utf-8")


def test_probe_manifest_replay_can_report_ready_basis(tmp_path, capsys):
    _write_sidecars(tmp_path, with_ready_basis=True)
    manifest = _write_manifest(tmp_path)

    rc = probe_main(
        [
            "--repo-root",
            str(tmp_path),
            "--manifest",
            str(manifest),
            "--format",
            "json",
            "--now",
            "2026-07-07T01:30:00Z",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall_status"] == "CONTRACT_READY"
    assert payload["cost_basis_summary"]["basis_complete"] is True
    assert {surface["key"] for surface in payload["evidence_surfaces"]} == {
        "execution-quality",
        "kis-smoke",
        "rebalance-micro-gtaa",
        "money-path",
        "pipeline-liveness",
        "released-work",
        "capital-path-readiness",
    }
