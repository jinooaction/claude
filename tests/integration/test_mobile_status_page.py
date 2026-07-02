from __future__ import annotations

import json
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
    output = tmp_path / "status.html"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_mobile_status.py",
            "--sidecar-dir",
            str(sidecars),
            "--output",
            str(output),
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
