"""스펙 099 — 공개 데이터 입력 품질 계약 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "public_data_input_quality_probe.py"
_spec = importlib.util.spec_from_file_location("public_data_input_quality_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _summary() -> str:
    return _json(
        {
            "schema_version": "2.0",
            "as_of": "2026-07-04",
            "overall_ok": True,
            "published": 3,
            "total_items": 3,
            "items": {
                "SPY": {"ok": True, "rows": 751},
                "IEF": {"ok": True, "rows": 751},
                "VIX": {"ok": True, "rows": 751},
            },
            "cross_checks": [
                {"name": "spy_vs_ief", "status": "PASS", "overlap_days": 751},
                {"name": "spy_vs_vix", "status": "PASS", "overlap_days": 751},
            ],
        }
    )


def _regime() -> str:
    return _json(
        {
            "schema_version": "1.0",
            "overall_label": "CAUTION",
            "available_indicators": 4,
            "total_indicators": 4,
            "indicators": {
                "yield_curve": {"status": "OK"},
                "vix": {"status": "OK"},
                "inflation": {"status": "OK"},
                "sahm": {"status": "OK"},
            },
        }
    )


def _timeline(rows: int = 25) -> str:
    body = ["date,label", *[f"2026-01-{day:02d},CAUTION" for day in range(1, rows + 1)]]
    return "\n".join(body) + "\n"


def _stratify() -> str:
    payload = {
        "schema_version": "1.0",
        "total_return_days": 751,
        "labels": {"CAUTION": 431, "RISK_OFF": 7, "RISK_ON": 313},
    }
    return (
        "# 레짐 층화\n\n"
        "```\n"
        "regime stratify: 수익률 751일\n"
        "--- stratified json ---\n"
        + _json(payload)
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
                    "candidate_id": "candidate-public-data-input-quality-contract",
                    "status": "released",
                    "reason_ko": "스펙 099 완료",
                }
            ]
        }
    )


def _capital() -> str:
    return _json(
        {
            "readiness_state": "ACCUMULATING_EDGE",
            "live_money_status": "PREVIEW_ONLY",
            "capital_ladder_status": "BLOCKED",
        }
    )


def _write_sidecars(root: Path) -> None:
    public_data = root / "automation" / "public-data"
    public_data.mkdir(parents=True)
    (public_data / "LAST_RUN.md").write_text(
        "## 결정 JSON\n\n```json\n{\"overall_ok\":true}\n```\n",
        encoding="utf-8",
    )
    (public_data / "summary.json").write_text(_summary(), encoding="utf-8")
    (public_data / "regime.json").write_text(_regime(), encoding="utf-8")
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

    capital = root / "automation" / "capital-path-readiness-last-run"
    capital.mkdir(parents=True)
    (capital / "capital_path_readiness.json").write_text(_capital(), encoding="utf-8")


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


def test_probe_manifest_replay_writes_json_and_markdown(tmp_path, capsys):
    _write_sidecars(tmp_path)
    manifest = _write_manifest(tmp_path)
    json_out = tmp_path / "public_data_input_quality.json"
    summary_out = tmp_path / "LAST_RUN.md"

    rc = probe_main(
        [
            "--repo-root",
            str(tmp_path),
            "--manifest",
            str(manifest),
            "--format",
            "json",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            "--now",
            "2026-07-06T12:20:00Z",
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
    assert written["completed_candidate_id"] == "candidate-public-data-input-quality-contract"
    assert "공개 데이터 입력 품질 계약" in summary_out.read_text(encoding="utf-8")


def test_probe_repo_root_mode_reads_standard_sidecar_layout(tmp_path, capsys):
    _write_sidecars(tmp_path)

    rc = probe_main(
        [
            "--repo-root",
            str(tmp_path),
            "--format",
            "json",
            "--now",
            "2026-07-06T12:20:00Z",
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
