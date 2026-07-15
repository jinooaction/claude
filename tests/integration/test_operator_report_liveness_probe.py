"""스펙 118 - 운영자 이해 가능 보고 생존성 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from auto_invest.analytics.operator_report_liveness import (
    COMPLETED_CANDIDATE_ID,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
)

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "operator_report_liveness_probe.py"
_spec = importlib.util.spec_from_file_location("operator_report_liveness_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_probe_writes_json_and_markdown(tmp_path, capsys):
    final_report = tmp_path / "final-report.md"
    final_report.write_text(
        "\n".join(
            [
                "운영자가 바로 이해할 수 있게 완료 보고의 의미 검사가 main에 들어갔다.",
                "무엇을 만들었는가: 최종 보고가 운영 상태 변화와 검증을 담는지 확인한다.",
                "돈 경로와 안전 경계: 주문, 자본, whitelist/caps, 비밀값은 "
                "건드리지 않았다. 다음 세션은 같은 후보를 반복하지 않는다.",
                "검증: focused pytest, 전체 pytest, ruff, handoff 사실 검증, "
                "strict harness로 확인한다.",
                "남은 위험: 실제 서버와 KIS 계좌 상태는 이 보고서의 범위 밖이다.",
            ]
        ),
        encoding="utf-8",
    )
    released_work = tmp_path / "released_work.json"
    released_work.write_text(
        json.dumps(
            {
                "released_work": [
                    {"candidate_id": COMPLETED_CANDIDATE_ID, "status": "released"}
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    json_out = tmp_path / "report.json"
    summary_out = tmp_path / "report.md"

    rc = probe_main(
        [
            "--repo-root",
            str(_ROOT),
            "--final-report",
            str(final_report),
            "--released-work",
            str(released_work),
            "--format",
            "json",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            "--now",
            "2026-07-15T12:00:00Z",
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
    assert written["completed_candidate_id"] == COMPLETED_CANDIDATE_ID
    assert written["next_candidate_id"] == NEXT_AUTONOMOUS_CANDIDATE_ID
    assert written["final_report_summary"]["state"] == "PASS"
    assert "운영자 이해 가능 보고 생존성 계약" in summary_out.read_text(encoding="utf-8")
