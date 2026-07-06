"""스펙 101 — 데이터 증거 생존성 계약 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "data_evidence_liveness_probe.py"
_spec = importlib.util.spec_from_file_location("data_evidence_liveness_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main

PUBLIC_DATA_TS = "2026-07-04T05:05:20Z"
REGIME_STRATIFY_TS = "2026-07-04T01:09:16Z"


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _last_run(timestamp: str) -> str:
    return (
        "# sidecar\n\n"
        "| 항목 | 값 |\n"
        "|------|-----|\n"
        f"| timestamp_utc | {timestamp} |\n"
    )


def _liveness() -> str:
    return (
        "## 결정 JSON\n\n```json\n"
        + _json(
            {
                "schema_version": "1.0",
                "overall": "OK",
                "checks": [
                    {
                        "key": "collect-public-data",
                        "status": "OK",
                        "critical": False,
                        "age_hours": 55.9,
                        "max_age_hours": 80.0,
                        "timestamp_utc": PUBLIC_DATA_TS,
                    },
                    {
                        "key": "regime-stratify",
                        "status": "OK",
                        "critical": False,
                        "age_hours": 59.9,
                        "max_age_hours": 80.0,
                        "timestamp_utc": REGIME_STRATIFY_TS,
                    },
                ],
            }
        )
        + "\n```\n"
    )


def _write_sidecars(root: Path) -> None:
    public_data = root / "automation" / "public-data"
    public_data.mkdir(parents=True)
    (public_data / "LAST_RUN.md").write_text(_last_run(PUBLIC_DATA_TS), encoding="utf-8")
    (public_data / "summary.json").write_text(
        _json(
            {
                "schema_version": "2.0",
                "overall_ok": True,
                "published": 11,
                "total_items": 11,
                "items": {"SPY": {"ok": True}},
                "cross_checks": [{"name": "spy_vs_ief", "status": "PASS"}],
            }
        ),
        encoding="utf-8",
    )
    (public_data / "regime.json").write_text(
        _json(
            {
                "schema_version": "1.0",
                "overall_label": "CAUTION",
                "available_indicators": 4,
                "total_indicators": 4,
            }
        ),
        encoding="utf-8",
    )
    (public_data / "regime_timeline.csv").write_text(
        "date,label\n2026-01-01,CAUTION\n",
        encoding="utf-8",
    )

    regime_stratify = root / "automation" / "regime-stratify-last-run"
    regime_stratify.mkdir(parents=True)
    (regime_stratify / "LAST_RUN.md").write_text(
        _last_run(REGIME_STRATIFY_TS),
        encoding="utf-8",
    )

    liveness = root / "automation" / "pipeline-liveness-last-run"
    liveness.mkdir(parents=True)
    (liveness / "LAST_RUN.md").write_text(_liveness(), encoding="utf-8")

    released_work = root / "automation" / "released-work-last-run"
    released_work.mkdir(parents=True)
    (released_work / "released_work.json").write_text(
        _json(
            {
                "released_work": [
                    {
                        "candidate_id": "candidate-data-evidence-liveness-contract",
                        "status": "released",
                        "reason_ko": "스펙 101 완료",
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
                "public-data-last-run\tautomation/public-data\tLAST_RUN.md",
                "public-data-summary\tautomation/public-data\tsummary.json",
                "public-data-regime\tautomation/public-data\tregime.json",
                "public-data-regime-timeline\tautomation/public-data\tregime_timeline.csv",
                "regime-stratify\tautomation/regime-stratify-last-run\tLAST_RUN.md",
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
    json_out = tmp_path / "data_evidence_liveness.json"
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
            "2026-07-06T13:05:00Z",
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
        == "candidate-data-evidence-liveness-contract"
    )
    assert written["next_candidate_id"] == "candidate-execution-quality-frontier-map"
    assert "데이터 증거 생존성 계약" in summary_out.read_text(encoding="utf-8")


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
            "2026-07-06T13:05:00Z",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall_status"] == "CONTRACT_READY"
    assert {surface["key"] for surface in payload["evidence_surfaces"]} == {
        "public-data-last-run",
        "public-data-summary",
        "public-data-regime",
        "public-data-regime-timeline",
        "regime-stratify",
        "pipeline-liveness",
        "released-work",
        "capital-path-readiness",
    }
