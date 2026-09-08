from __future__ import annotations

import html as html_module
import json
import re
import subprocess
import sys
from pathlib import Path


def test_mobile_status_generator_renders_html(tmp_path: Path) -> None:
    sidecars = tmp_path / "sidecars"
    sidecars.mkdir()
    (sidecars / "kis-smoke.md").write_text(
        "| 항목 | 값 |\n|------|-----|\n| timestamp_utc | 2026-06-18T07:00:00Z |\n",
        encoding="utf-8",
    )
    (sidecars / "operator-status.md").write_text(
        "## 결정 JSON\n\n```json\n"
        + json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "123",
                "commit": "abcdef123456",
                "timestamp_utc": "2026-06-18T08:00:00Z",
                "overall_status": "ACTION_REQUIRED",
                "headline_ko": "돈 경로 정렬 확인이 필요합니다.",
                "next_action_ko": "money-gate-alignment sidecar를 확인한다.",
                "dashboard_url": "https://example.test/status.html",
                "alert_decision": {
                    "alert_level": "ACTION_REQUIRED",
                    "should_send": True,
                    "reason_ko": "개입 필요 표면 1개",
                    "message_ko": "확인 필요",
                    "send_status": "SKIPPED_MISSING_SECRETS",
                },
                "surfaces": [],
                "dashboard_sections": [
                    {
                        "key": "money",
                        "title_ko": "실제 돈 경로",
                        "status": "PREVIEW_ONLY",
                        "body_ko": "실제 돈 경로는 PREVIEW_ONLY입니다.",
                    }
                ],
                "safety_invariants": ["no orders"],
            },
            ensure_ascii=False,
        )
        + "\n```\n",
        encoding="utf-8",
    )
    (sidecars / "money-path.md").write_text(
        "## 결정 JSON\n\n```json\n"
        + json.dumps(
            {
                "as_of_utc": "2026-06-18T07:55:00Z",
                "stage": "DEPLOYED",
                "blocking_gate": "20% 승격 증거 필요",
                "current_rung": 1,
                "entry_route": "operational_canary",
                "capital_pct": "10",
                "account_nav_usd": "1434.91",
                "deployed_capital_usd": 143,
                "live_money_state": {
                    "status": "REAL_ORDER_PATH_ARMED",
                    "can_submit_real_orders": True,
                    "next_scheduled_live_utc": "2026-06-18T14:17:00Z",
                    "last_run": {
                        "timestamp_utc": "2026-06-17T19:09:50Z",
                        "event": "schedule",
                        "live_step": "failure",
                        "preflight_ok": True,
                        "preflight_reason": "ENTRY_READY",
                        "accepted_or_filled_count": 0,
                        "broker_rejected_count": 0,
                    },
                },
                "live_profit_evidence": {
                    "status": "NO_FILLS_YET",
                    "fills_count": 0,
                    "gross_invested_usd": "0",
                    "realized_pnl_usd": "0",
                    "unrealized_pnl_usd": "0",
                    "total_pnl_usd": "0",
                    "return_pct": None,
                    "measurement_scope": "strategy",
                    "observed_at_utc": "2026-06-18T07:50:00Z",
                },
                "safety_budget": {
                    "reference_rung": 1,
                    "current_dd_pct": "0",
                    "demote_dd_pct": "10",
                    "halt_dd_pct": "20",
                    "loss_at_demote_usd": 15,
                    "loss_at_halt_usd": 29,
                },
            }
        )
        + "\n```\n",
        encoding="utf-8",
    )
    (sidecars / "rebalance-live-canary.md").write_text(
        "| timestamp_utc | 2026-06-18T07:45:00Z |\n```json\n"
        + json.dumps(
            {
                "allowed": True,
                "evidence": {
                    "forward_n_obs": 9,
                    "min_forward_obs": 40,
                    "forward_psr": None,
                    "min_forward_psr": 0.8,
                    "operational_assessment": {
                        "candidate_id": "globalfixed-ensemble-3-6-9-12",
                        "alpha_confirmed": False,
                    },
                    "fundability": {"target_weights": {"IAUM": "0.16", "SCHX": "0.33"}},
                },
            }
        )
        + "\n```\n",
        encoding="utf-8",
    )
    (sidecars / "autonomous-strategy-factory.md").write_text(
        "- 역사 판정: `PUBLISHED_EDGE`\n"
        "- 개발 선택 후보: `pead-candidate`\n"
        "| timestamp_utc | 2026-06-18T07:40:00Z |\n",
        encoding="utf-8",
    )
    output = tmp_path / "status.html"
    json_output = tmp_path / "status.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_mobile_status.py",
            "--sidecar-dir",
            str(sidecars),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
            "--repository",
            "jinooaction/claude",
            "--commit",
            "abcdef123456",
            "--now",
            "2026-06-18T08:00:00Z",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    html = output.read_text(encoding="utf-8")
    assert "Wrote" in result.stdout
    assert "<html lang=\"ko\">" in html
    assert "auto-invest 상태판" in html
    assert "KIS 연결" in html
    assert "abcdef1" in html
    assert "status-data" in html
    assert "operator-status-data" in html
    assert "운영자 요약" in html
    assert "돈 경로 정렬 확인이 필요합니다." in html
    assert "실제 돈 경로는 PREVIEW_ONLY입니다." in html
    assert "자금 현황" in html
    assert "전략 현황" in html
    assert "현재 운용 한도 · 합산 자산 아님" in html
    assert "$143.00" in html
    assert "$600.00" in html
    assert "globalfixed-ensemble-3-6-9-12" in html

    mobile_status = json.loads(json_output.read_text(encoding="utf-8"))
    assert mobile_status["schema_version"] == "1.0"
    assert mobile_status["generated_at_utc"] == "2026-06-18T08:00:00Z"
    assert mobile_status["repository"] == "jinooaction/claude"
    assert mobile_status["commit"] == "abcdef123456"
    assert mobile_status["source"] == "automation sidecars"
    assert mobile_status["read_only"] is True
    assert mobile_status["liveness"]["overall"] == "CRITICAL"
    assert mobile_status["operator_status"]["overall_status"] == "ACTION_REQUIRED"
    assert mobile_status["operator_status"]["dashboard_sections"][0]["key"] == "money"
    assert mobile_status["capital_summary"]["account"]["status"] == "UNVERIFIED"
    assert mobile_status["capital_summary"]["account"]["total_assets_usd"] is None
    assert mobile_status["capital_summary"]["live_allocation"]["allocated_capital_usd"] == "143"
    assert mobile_status["capital_summary"]["intraday_budget"]["capital_limit_usd"] == "600.00"
    assert mobile_status["capital_summary"]["performance"]["gross_invested_usd"] == "0"
    assert mobile_status["strategy_summary"]["active"]["role"] == "OPERATIONAL_CANARY"
    assert mobile_status["strategy_summary"]["intraday"]["orders_submitted"] == 0

    embedded_liveness = _embedded_json(html, "status-data")
    embedded_operator = _embedded_json(html, "operator-status-data")
    embedded_capital = _embedded_json(html, "capital-summary-data")
    embedded_strategy = _embedded_json(html, "strategy-summary-data")
    assert mobile_status["liveness"] == embedded_liveness
    assert mobile_status["operator_status"] == embedded_operator
    assert mobile_status["capital_summary"] == embedded_capital
    assert mobile_status["strategy_summary"] == embedded_strategy

    assert "1434.91" not in json.dumps(mobile_status)

    serialized = json.dumps(mobile_status, ensure_ascii=False).lower()
    for forbidden in ("kis_app_key", "kis_app_secret", "account_number", "access_token", "ssh_key"):
        assert forbidden not in serialized


def test_mobile_status_json_marks_missing_operator_status_as_null(tmp_path: Path) -> None:
    sidecars = tmp_path / "sidecars"
    sidecars.mkdir()
    output = tmp_path / "status.html"
    json_output = tmp_path / "status.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/generate_mobile_status.py",
            "--sidecar-dir",
            str(sidecars),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
            "--commit",
            "abcdef123456",
            "--now",
            "2026-06-18T08:00:00Z",
        ],
        check=True,
    )

    mobile_status = json.loads(json_output.read_text(encoding="utf-8"))
    assert mobile_status["read_only"] is True
    assert mobile_status["operator_status"] is None
    assert mobile_status["liveness"]["overall"] == "CRITICAL"


def test_mobile_status_manifest_lists_sidecars() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_mobile_status.py",
            "--sidecar-dir",
            "/tmp/unused",
            "--manifest",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "kis-smoke\tautomation/kis-smoke-last-run\tLAST_RUN.md" in result.stdout
    assert "operator-status\tautomation/operator-status-last-run\tLAST_RUN.md" in result.stdout
    assert (
        "live-profit-evidence\tautomation/live-profit-evidence-last-run\t"
        "profit_evidence.json"
    ) in result.stdout
    assert (
        "autonomous-strategy-factory\tautomation/autonomous-strategy-factory-last-run\t"
        "LAST_RUN.md"
    ) in result.stdout
    assert result.stdout.count("autonomous-strategy-factory\t") == 1


def test_mobile_status_workflow_republishes_after_key_money_and_strategy_sources() -> None:
    workflow = Path(".github/workflows/mobile-status-pages.yml").read_text(encoding="utf-8")

    assert "workflow_run:" in workflow
    assert '"Money-path readiness (첫-자본까지의 길 종합)"' in workflow
    assert '"Live canary portfolio rebalance (guarded, real money)"' in workflow
    assert '"Live profit evidence (실계좌 체결과 첫 수익 증거)"' in workflow
    assert '"Autonomous strategy factory (PEAD published-edge diagnostic)"' in workflow
    assert "branches: [main]" in workflow
    assert "ref: main" in workflow
    assert "rebalance-once" not in workflow
    assert "--mode live" not in workflow


def _embedded_json(document: str, element_id: str) -> dict:
    match = re.search(
        rf'<script type="application/json" id="{element_id}">(.*?)</script>',
        document,
    )
    assert match is not None
    return json.loads(html_module.unescape(match.group(1)))
