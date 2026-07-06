"""스펙 097 — 비용 차감 엣지 실험 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "cost_adjusted_edge_experiment_probe.py"
_spec = importlib.util.spec_from_file_location(
    "cost_adjusted_edge_experiment_probe",
    _PROBE_PATH,
)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _fenced(obj: dict) -> str:
    return "```json\n" + json.dumps(obj, ensure_ascii=False) + "\n```"


def _write_sidecars(sidecar_dir: Path) -> None:
    board = {
        "schema_version": "1.0",
        "as_of_utc": "2026-07-03T23:40:22Z",
        "champion_key": None,
        "incumbent_key": "global",
        "challenger_key": None,
        "comparable_count": 0,
        "track_count": 2,
        "known_count": 2,
        "unknown_count": 0,
        "max_n_obs": 16,
        "min_n_obs": 16,
        "lagging_keys": [],
        "observation_health": "OK",
        "observation_note": "관측 누적 중",
        "headline": "아직 비교 불가",
        "rows": [
            {
                "key": "global",
                "label": "글로벌 분산 추세",
                "is_incumbent": True,
                "verdict": "INSUFFICIENT_DATA",
                "n_obs": 16,
                "min_obs": 20,
                "comparability": "PREMATURE",
                "rank": 1,
                "total_return_pct": "-0.58",
                "max_drawdown_pct": "4.2",
                "universe": ["SPY", "IEF", "GLD"],
            },
            {
                "key": "multiasset",
                "label": "멀티에셋 분산 추세",
                "is_incumbent": False,
                "verdict": "INSUFFICIENT_DATA",
                "n_obs": 16,
                "min_obs": 20,
                "comparability": "PREMATURE",
                "rank": 2,
                "total_return_pct": "1.84",
                "max_drawdown_pct": "10.6",
                "universe": ["SPY", "IEF"],
            },
        ],
    }
    (sidecar_dir / "rebalance-paper-forward.md").write_text(
        "# forward\n\n## 리더보드 결정 JSON\n\n" + _fenced(board),
        encoding="utf-8",
    )
    (sidecar_dir / "execution-quality.md").write_text(
        "# 실행 품질 패키지\n\n## 결정 JSON\n\n"
        + _fenced(
            {
                "overall_status": "OBSERVE",
                "opportunity_monitor": {
                    "verdict": "INSUFFICIENT_DATA",
                    "latest_signal": "INTENT_LOSS",
                    "cumulative_pnl_usd": "-1.14",
                },
                "broker_rejections": {
                    "rejected_orders": 2,
                    "parsed_broker_errors": 2,
                    "broker_error_observation_rate": 1.0,
                    "kis_msg_codes": {"APBK1672": 2},
                },
                "broker_smoke": {
                    "present": True,
                    "smoke_state": "success",
                    "tests_total": 4,
                    "tests_failed": 0,
                    "smoke_error_rate": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )
    (sidecar_dir / "money-path.md").write_text(
        "## 결정 JSON\n\n"
        + _fenced(
            {
                "stage": "BLOCKED",
                "live_money_state": {
                    "status": "PREVIEW_ONLY",
                    "can_submit_real_orders": False,
                    "detail": "armed:false",
                },
            }
        ),
        encoding="utf-8",
    )
    (sidecar_dir / "released-work.md").write_text(
        json.dumps({"released_work": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (sidecar_dir / "evolution-ledger.md").write_text(
        json.dumps({"entries": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (sidecar_dir / "pipeline-liveness.md").write_text(
        "## 결정 JSON\n\n" + _fenced({"overall": "OK", "checks": []}),
        encoding="utf-8",
    )


def test_manifest_lists_required_sidecars(capsys):
    rc = probe_main(["--manifest"])

    assert rc == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out == [
        "rebalance-paper-forward\tautomation/rebalance-paper-forward-last-run\tLAST_RUN.md",
        "execution-quality\tautomation/execution-quality-last-run\tLAST_RUN.md",
        "money-path\tautomation/money-path-last-run\tLAST_RUN.md",
        "released-work\tautomation/released-work-last-run\treleased_work.json",
        "evolution-ledger\tautomation/autonomous-evolution-last-run\tlearning_ledger.json",
        "pipeline-liveness\tautomation/pipeline-liveness-last-run\tLAST_RUN.md",
    ]


def test_probe_writes_json_and_markdown(tmp_path, capsys):
    sidecar_dir = tmp_path / "sidecars"
    sidecar_dir.mkdir()
    _write_sidecars(sidecar_dir)
    json_out = tmp_path / "cost_adjusted_edge_experiment.json"
    summary_out = tmp_path / "LAST_RUN.md"

    rc = probe_main(
        [
            "--sidecar-dir",
            str(sidecar_dir),
            "--json",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            "--now",
            "2026-07-06T12:00:00Z",
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
    assert written["run_id"] == "123"
    assert written["commit"] == "abc123"
    assert written["completed_candidate_id"] == "candidate-cost-adjusted-edge-experiment"
    assert "cost_adjusted_candidates" in written
    assert "비용 차감 no-live 엣지 실험 계약" in summary_out.read_text(
        encoding="utf-8"
    )


def test_probe_repo_root_released_work_overrides_sidecar_lag(tmp_path, capsys):
    sidecar_dir = tmp_path / "sidecars"
    sidecar_dir.mkdir()
    _write_sidecars(sidecar_dir)
    repo_root = tmp_path / "repo"
    spec_dir = repo_root / "specs" / "097-cost-adjusted-edge-experiment"
    contracts_dir = spec_dir / "contracts"
    contracts_dir.mkdir(parents=True)
    (spec_dir / "tasks.md").write_text("- [x] 구현 완료\n", encoding="utf-8")
    (contracts_dir / "cost-adjusted-edge-experiment.md").write_text(
        "completed_candidate_id: candidate-cost-adjusted-edge-experiment\n",
        encoding="utf-8",
    )

    rc = probe_main(
        [
            "--sidecar-dir",
            str(sidecar_dir),
            "--repo-root",
            str(repo_root),
            "--json",
            "--now",
            "2026-07-06T12:00:00Z",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    gate = next(
        gate
        for gate in printed["validation_gates"]
        if gate["gate_id"] == "released-work-closure"
    )
    assert gate["status"] == "PASS"

