"""스펙 103 — 브로커 거부 분류 계약 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "broker_rejection_taxonomy_probe.py"
_spec = importlib.util.spec_from_file_location("broker_rejection_taxonomy_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _markdown_json(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _write_sidecars(root: Path) -> None:
    execution_quality = root / "automation" / "execution-quality-last-run"
    execution_quality.mkdir(parents=True)
    (execution_quality / "LAST_RUN.md").write_text(
        _markdown_json(
            {
                "overall_status": "OBSERVE",
                "broker_rejections": {
                    "rejected_orders": 2,
                    "parsed_broker_errors": 2,
                    "unparsed_reasons": 0,
                    "broker_error_observation_rate": "1.0000",
                    "kis_msg_codes": {"APBK1672": 2},
                    "exception_types": {"KisOrderResponseError": 2},
                    "http_statuses": {"200": 2},
                },
                "broker_smoke": {
                    "present": True,
                    "smoke_state": "success",
                    "smoke_exit": 0,
                    "tests_total": 4,
                    "tests_failed": 0,
                    "smoke_error_rate": "0.0000",
                    "key_valid": True,
                },
                "live_gate": {
                    "ok": False,
                    "reason": "latest_intent_loss",
                    "verdict": "INSUFFICIENT_DATA",
                    "latest_signal": "INTENT_LOSS",
                },
            }
        ),
        encoding="utf-8",
    )

    kis_smoke = root / "automation" / "kis-smoke-last-run"
    kis_smoke.mkdir(parents=True)
    (kis_smoke / "LAST_RUN.md").write_text(
        "# KIS smoke\n\n| smoke_state | success |\n| smoke_exit | 0 |\n| key_valid | true |\n",
        encoding="utf-8",
    )

    micro = root / "automation" / "rebalance-micro-gtaa-last-run"
    micro.mkdir(parents=True)
    (micro / "LAST_RUN.md").write_text(
        "## 라이브 전 전략 의도 게이트\n```json\n"
        + _json(
            {
                "ok": False,
                "reason": "latest_intent_loss",
                "verdict": "INSUFFICIENT_DATA",
                "latest_signal": "INTENT_LOSS",
            }
        )
        + "\n```\n",
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
                        "candidate_id": "candidate-broker-rejection-taxonomy-contract",
                        "status": "released",
                        "reason_ko": "스펙 103 완료",
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


def test_probe_repo_root_mode_writes_json_and_markdown(tmp_path, capsys):
    _write_sidecars(tmp_path)
    json_out = tmp_path / "broker_rejection_taxonomy.json"
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
            "2026-07-07T00:20:00Z",
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
    assert written["overall_status"] == "CONTRACT_READY"
    assert written["run_id"] == "123"
    assert written["commit"] == "abc123"
    assert (
        written["completed_candidate_id"]
        == "candidate-broker-rejection-taxonomy-contract"
    )
    assert written["next_candidate_id"] == "candidate-execution-cost-basis-contract"
    assert written["taxonomy"][0]["signature"] == "APBK1672"
    assert "브로커 거부 분류" in summary_out.read_text(encoding="utf-8")


def test_probe_manifest_replay_reads_expected_inputs(tmp_path, capsys):
    _write_sidecars(tmp_path)
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
            "2026-07-07T00:20:00Z",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall_status"] == "CONTRACT_READY"
    assert {surface["key"] for surface in payload["evidence_surfaces"]} == {
        "execution-quality",
        "kis-smoke",
        "rebalance-micro-gtaa",
        "pipeline-liveness",
        "released-work",
        "capital-path-readiness",
    }
