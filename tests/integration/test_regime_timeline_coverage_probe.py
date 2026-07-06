"""스펙 100 — 레짐 타임라인 커버리지 계약 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "regime_timeline_coverage_probe.py"
_spec = importlib.util.spec_from_file_location("regime_timeline_coverage_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _timeline() -> str:
    rows = ["date,label,flags,available"]
    current = date(2026, 1, 1)
    for offset, label in enumerate(["RISK_ON"] * 25 + ["CAUTION"] * 25 + ["RISK_OFF"] * 7):
        rows.append(f"{(current + timedelta(days=offset)).isoformat()},{label},,4")
    return "\n".join(rows) + "\n"


def _stratify() -> str:
    payload = {
        "schema_version": "1.0",
        "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
        "total_return_days": 57,
        "by_label": {
            "CAUTION": {"n_days": 25},
            "RISK_OFF": {"n_days": 7},
            "RISK_ON": {"n_days": 25},
        },
        "all": {"n_days": 57},
    }
    return (
        "## GLOBAL-TREND\n\n"
        "```\n"
        "regime stratify: 수익률 57일\n"
        "--- stratified json ---\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```\n"
    )


def _liveness() -> str:
    return (
        "## 결정 JSON\n\n```json\n"
        + _json(
            {
                "overall": "OK",
                "checks": [
                    {"key": "collect-public-data", "status": "OK", "age_hours": 55.0},
                    {"key": "regime-stratify", "status": "OK", "age_hours": 59.0},
                ],
            }
        )
        + "\n```\n"
    )


def _released() -> str:
    return _json(
        {
            "released_work": [
                {
                    "candidate_id": "candidate-regime-timeline-coverage-contract",
                    "status": "released",
                    "reason_ko": "스펙 100 완료",
                }
            ]
        }
    )


def _write_sidecars(root: Path) -> None:
    public_data = root / "automation" / "public-data"
    public_data.mkdir(parents=True)
    (public_data / "regime_timeline.csv").write_text(_timeline(), encoding="utf-8")

    regime_stratify = root / "automation" / "regime-stratify-last-run"
    regime_stratify.mkdir(parents=True)
    (regime_stratify / "LAST_RUN.md").write_text(_stratify(), encoding="utf-8")

    liveness = root / "automation" / "pipeline-liveness-last-run"
    liveness.mkdir(parents=True)
    (liveness / "LAST_RUN.md").write_text(_liveness(), encoding="utf-8")

    released_work = root / "automation" / "released-work-last-run"
    released_work.mkdir(parents=True)
    (released_work / "released_work.json").write_text(_released(), encoding="utf-8")


def _write_manifest(root: Path) -> Path:
    manifest = root / "manifest.tsv"
    manifest.write_text(
        "\n".join(
            [
                "public-data-regime-timeline\tautomation/public-data\tregime_timeline.csv",
                "regime-stratify\tautomation/regime-stratify-last-run\tLAST_RUN.md",
                "pipeline-liveness\tautomation/pipeline-liveness-last-run\tLAST_RUN.md",
                "released-work\tautomation/released-work-last-run\treleased_work.json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def test_probe_repo_root_mode_writes_json_and_markdown(tmp_path, capsys):
    _write_sidecars(tmp_path)
    json_out = tmp_path / "regime_timeline_coverage.json"
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
            "2026-07-06T13:30:00Z",
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
    assert (
        written["completed_candidate_id"]
        == "candidate-regime-timeline-coverage-contract"
    )
    assert written["next_candidate_id"] == "candidate-data-evidence-liveness-contract"
    assert "레짐 타임라인 커버리지 계약" in summary_out.read_text(encoding="utf-8")


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
            "2026-07-06T13:30:00Z",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall_status"] == "OBSERVATION_WAIT"
    assert {surface["key"] for surface in payload["evidence_surfaces"]} == {
        "public-data-regime-timeline",
        "regime-stratify",
        "pipeline-liveness",
        "released-work",
    }
