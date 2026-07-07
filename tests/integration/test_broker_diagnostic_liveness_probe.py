"""스펙 105 - 브로커 진단 생존성 계약 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "broker_diagnostic_liveness_probe.py"
_spec = importlib.util.spec_from_file_location("broker_diagnostic_liveness_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _markdown_json(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _write_sidecars(root: Path, *, embedded_smoke: bool = True) -> None:
    kis_smoke = root / "automation" / "kis-smoke-last-run"
    kis_smoke.mkdir(parents=True)
    (kis_smoke / "LAST_RUN.md").write_text(
        "\n".join(
            [
                "# KIS smoke",
                "",
                "| 변수 | 값 |",
                "|------|-----|",
                "| secrets_present | true |",
                "| key_valid | true |",
                "| smoke_state | success |",
                "| smoke_exit | 0 |",
                "| tests_total | 4 |",
                "| tests_failed | 0 |",
                "| timestamp_utc | 2026-07-07T06:48:04Z |",
                "",
            ]
        ),
        encoding="utf-8",
    )

    execution_payload = {"overall_status": "OBSERVE"}
    if embedded_smoke:
        execution_payload["broker_smoke"] = {
            "key_valid": True,
            "smoke_state": "success",
            "smoke_exit": 0,
            "tests_total": 4,
            "tests_failed": 0,
            "timestamp_utc": "2026-07-07T06:48:04Z",
        }
    execution_quality = root / "automation" / "execution-quality-last-run"
    execution_quality.mkdir(parents=True)
    (execution_quality / "LAST_RUN.md").write_text(
        _markdown_json(execution_payload),
        encoding="utf-8",
    )

    liveness = root / "automation" / "pipeline-liveness-last-run"
    liveness.mkdir(parents=True)
    (liveness / "LAST_RUN.md").write_text(
        _markdown_json(
            {
                "schema_version": "1.0",
                "overall": "OK",
                "checks": [
                    {"key": "kis-smoke", "status": "OK", "critical": True},
                    {"key": "execution-quality", "status": "OK", "critical": False},
                ],
            }
        ),
        encoding="utf-8",
    )

    released_work = root / "automation" / "released-work-last-run"
    released_work.mkdir(parents=True)
    (released_work / "released_work.json").write_text(
        _json(
            {
                "released_work": [
                    {
                        "candidate_id": "candidate-broker-diagnostic-liveness-contract",
                        "status": "released",
                        "reason_ko": "스펙 105 완료",
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
                "kis-smoke\tautomation/kis-smoke-last-run\tLAST_RUN.md",
                "execution-quality\tautomation/execution-quality-last-run\tLAST_RUN.md",
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


def test_probe_repo_root_mode_writes_ready_json_and_markdown(tmp_path, capsys):
    _write_sidecars(tmp_path)
    json_out = tmp_path / "broker_diagnostic_liveness.json"
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
            "2026-07-08T01:30:00Z",
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
    assert written["completed_candidate_id"] == "candidate-broker-diagnostic-liveness-contract"
    assert written["next_candidate_id"] == "candidate-agent-ops-frontier-map"
    assert written["diagnostic_summary"]["diagnostic_state"] == "BROKER_DIAGNOSTIC_LIVE"
    assert "브로커 진단 생존성" in summary_out.read_text(encoding="utf-8")


def test_probe_manifest_replay_can_report_observation_wait(tmp_path, capsys):
    _write_sidecars(tmp_path, embedded_smoke=False)
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
            "2026-07-08T01:30:00Z",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall_status"] == "OBSERVATION_WAIT"
    assert payload["diagnostic_summary"]["execution_quality_has_broker_smoke"] is False
    assert {surface["key"] for surface in payload["evidence_surfaces"]} == {
        "kis-smoke",
        "execution-quality",
        "pipeline-liveness",
        "released-work",
        "capital-path-readiness",
    }
