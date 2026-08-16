"""스펙 077 — 자율 작업 실행 probe/workflow 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from auto_invest.analytics.pipeline_liveness import default_specs

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "autonomous_work_execution_probe.py"
_spec = importlib.util.spec_from_file_location("autonomous_work_execution_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_manifest_matches_contract(capsys):
    rc = probe_main(["--manifest"])

    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == [
        (
            "capital-path-readiness\tautomation/capital-path-readiness-last-run\t"
            "capital_path_readiness.json"
        ),
        "evolution-backlog\tautomation/autonomous-evolution-last-run\tcandidate_backlog.json",
        "evolution-ledger\tautomation/autonomous-evolution-last-run\tlearning_ledger.json",
        "autonomous-promotion\tautomation/autonomous-promotion-last-run\tpromotion_summary.json",
        (
            "candidate-implementation-factory\t"
            "automation/candidate-implementation-factory-last-run\tcandidate_factory.json"
        ),
        (
            "candidate-packages\tautomation/candidate-implementation-factory-last-run\t"
            "candidate_packages.json"
        ),
        (
            "candidate-result-executor\tautomation/candidate-implementation-results\t"
            "candidate_results.json"
        ),
        (
            "profit-evidence-engine\tautomation/profit-evidence-engine-last-run\t"
            "profit_evidence.json"
        ),
        "ml-edge-ensemble\tautomation/ml-edge-ensemble-last-run\treport.json",
        (
            "daily-cross-asset-ml\tautomation/daily-cross-asset-ml-last-run\t"
            "report.json"
        ),
        (
            "rebalance-paper-forward\tautomation/rebalance-paper-forward-last-run\t"
            "LAST_RUN.md"
        ),
        "edge-autoarm\tautomation/edge-autoarm-last-run\tLAST_RUN.md",
        "money-path\tautomation/money-path-last-run\tLAST_RUN.md",
        "execution-quality\tautomation/execution-quality-last-run\tLAST_RUN.md",
        "kis-smoke\tautomation/kis-smoke-last-run\tLAST_RUN.md",
        "rebalance-micro-gtaa\tautomation/rebalance-micro-gtaa-last-run\tLAST_RUN.md",
        "public-data\tautomation/public-data\tLAST_RUN.md",
        "regime-stratify\tautomation/regime-stratify-last-run\tLAST_RUN.md",
        "released-work\tautomation/released-work-last-run\treleased_work.json",
        "pipeline-liveness\tautomation/pipeline-liveness-last-run\tLAST_RUN.md",
    ]


def test_probe_writes_json_and_markdown(tmp_path, capsys):
    (tmp_path / "capital-path-readiness.md").write_text(
        json.dumps(
            {
                "readiness_state": "ACCUMULATING_EDGE",
                "live_money_status": "PREVIEW_ONLY",
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "pipeline-liveness.md").write_text(
        "## 결정 JSON\n\n```json\n{\"overall\":\"OK\",\"checks\":[]}\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "public-data.md").write_text(
        (
            "# 공개 데이터 수집 채널\n\n"
            "## summary.json\n\n"
            "```json\n"
            "{\"overall_ok\":true,\"published\":11,\"total_items\":11}\n"
            "```\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "regime-stratify.md").write_text(
        (
            "# 레짐 층화\n\n"
            "```\n"
            "regime stratify: 수익률 751일\n"
            "--- stratified json ---\n"
            "{\"schema_version\":\"1.0\",\"total_return_days\":751}\n"
            "```\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "execution-quality.md").write_text(
        (
            "# 실행 품질 패키지\n\n"
            "## 결정 JSON\n\n"
            "```json\n"
            "{\"overall_status\":\"OBSERVE\",\"broker_rejections\":{\"rejected_orders\":2}}\n"
            "```\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "kis-smoke.md").write_text(
        "# KIS smoke\n\n| smoke_state | success |\n",
        encoding="utf-8",
    )
    (tmp_path / "rebalance-micro-gtaa.md").write_text(
        "## 라이브 전 전략 의도 게이트\n```json\n{\"latest_signal\":\"INTENT_LOSS\"}\n```\n",
        encoding="utf-8",
    )

    json_out = tmp_path / "autonomous_work_execution.json"
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
            "2026-07-01T09:10:00Z",
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
    assert written["selected_work"]["candidate_id"] == "candidate-fd04772a23c5"
    assert written["selected_work"]["status"] == "EXECUTION_READY"
    assert written["objective_calibration"]["selected_candidate_id"] == (
        "candidate-fd04772a23c5"
    )
    assert (
        written["objective_calibration"]["exploration_budget"]["max_parallel_candidates"]
        == 1
    )
    assert written["macro_candidate_map"][0]["domain_key"] == "investment_edge"
    assert (
        written["macro_candidate_map"][0]["recommended_candidate_id"]
        == "candidate-investment-edge-frontier-map"
    )
    assert (
        written["investment_edge_frontier_map"][0]["recommended_candidate_id"]
        == "candidate-forward-regime-edge-experiment"
    )
    assert (
        written["data_evidence_frontier_map"][0]["recommended_candidate_id"]
        == "candidate-public-data-input-quality-contract"
    )
    assert (
        written["execution_quality_frontier_map"][0]["recommended_candidate_id"]
        == "candidate-broker-rejection-taxonomy-contract"
    )
    assert written["run_id"] == "123"
    assert written["commit"] == "abc123"
    surfaces = {surface["key"]: surface for surface in written["evidence_surfaces"]}
    assert surfaces["public-data"]["parse_status"] == "ok"
    assert surfaces["regime-stratify"]["parse_status"] == "ok"
    assert surfaces["execution-quality"]["parse_status"] == "ok"
    assert surfaces["kis-smoke"]["parse_status"] == "ok"
    assert surfaces["rebalance-micro-gtaa"]["parse_status"] == "ok"
    summary = summary_out.read_text(encoding="utf-8")
    assert "자율 작업 실행 루프" in summary
    assert "## 목적 함수 보정" in summary
    assert "## 거시 후보 지도" in summary
    assert "## 투자 엣지 frontier 지도" in summary
    assert "## 데이터 증거 frontier 지도" in summary
    assert "## 체결 품질 frontier 지도" in summary


def test_probe_repo_root_released_work_overrides_sidecar_lag(tmp_path, capsys):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    repo_root = tmp_path / "repo"
    contracts_dir = (
        repo_root
        / "specs"
        / "078-money-gate-alignment-loop"
        / "contracts"
    )
    contracts_dir.mkdir(parents=True)
    (contracts_dir.parent / "tasks.md").write_text("- [x] 구현 완료\n", encoding="utf-8")
    (contracts_dir / "money-gate-alignment.md").write_text(
        '{ "selected_work_candidate": "candidate-fd04772a23c5" }\n',
        encoding="utf-8",
    )
    (evidence_dir / "capital-path-readiness.md").write_text(
        json.dumps(
            {
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    },
                    {
                        "candidate_id": "candidate-e481b0309206",
                        "domain_key": "analysis",
                        "status": "new",
                        "score": 531,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (evidence_dir / "pipeline-liveness.md").write_text(
        "## 결정 JSON\n\n```json\n{\"overall\":\"OK\",\"checks\":[]}\n```\n",
        encoding="utf-8",
    )

    rc = probe_main(
        [
            "--evidence-dir",
            str(evidence_dir),
            "--repo-root",
            str(repo_root),
            "--json",
            "--now",
            "2026-07-02T09:10:00Z",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["selected_work"]["candidate_id"] == "candidate-e481b0309206"
    suppressed = {item["candidate_id"]: item for item in payload["suppressed_work"]}
    assert suppressed["candidate-fd04772a23c5"]["status"] == "RELEASED"


def test_probe_closed_queue_emits_macro_growth_candidate(tmp_path, capsys):
    (tmp_path / "capital-path-readiness.md").write_text(
        json.dumps(
            {
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "released-work.md").write_text(
        json.dumps(
            {
                "released_work": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "status": "released",
                        "reason_ko": "이미 완료",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "pipeline-liveness.md").write_text(
        "## 결정 JSON\n\n```json\n{\"overall\":\"OK\",\"checks\":[]}\n```\n",
        encoding="utf-8",
    )

    rc = probe_main(
        [
            "--evidence-dir",
            str(tmp_path),
            "--json",
            "--now",
            "2026-07-03T00:00:00Z",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["selected_work"]["candidate_id"] == "candidate-macro-growth-discovery"
    assert payload["selected_work"]["status"] == "EXECUTION_READY"


def test_pipeline_liveness_registers_autonomous_work_execution():
    specs = {spec.key: spec for spec in default_specs()}

    assert "autonomous-work-execution" in specs
    assert specs["autonomous-work-execution"].branch == (
        "automation/autonomous-work-execution-last-run"
    )
    assert specs["autonomous-work-execution"].critical is False


def test_pipeline_liveness_registers_released_work():
    specs = {spec.key: spec for spec in default_specs()}

    assert "released-work" in specs
    assert specs["released-work"].branch == "automation/released-work-last-run"
    assert specs["released-work"].critical is False


def test_workflow_stays_read_only_safety_contract():
    workflow = (_ROOT / ".github" / "workflows" / "autonomous-work-execution.yml").read_text(
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
    assert "automation/autonomous-work-execution-last-run" in workflow
    assert "--repo-root \"$GITHUB_WORKSPACE\"" in workflow
    assert "scripts/released_work_probe.py" in workflow
