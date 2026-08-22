#!/usr/bin/env python3
"""Validate production recovery output and build a fail-closed sidecar."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_report(raw: str, *, remote_exit: int, run_id: str, commit: str) -> dict[str, object]:
    try:
        report = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        report = {}
    required = {
        "status",
        "halt_present_after",
        "reconciliation_state",
        "evidence_quality",
        "halt_cleared",
        "orders_submitted",
    }
    valid = (
        isinstance(report, dict)
        and required.issubset(report)
        and report.get("orders_submitted") == 0
        and report.get("status") in {"RECOVERED", "CLEAR", "BLOCKED", "INCONCLUSIVE"}
    )
    if not valid:
        report = {
            "schema_version": "1.0",
            "status": "INCONCLUSIVE",
            "observed_at_utc": _now(),
            "halt_present_before": None,
            "halt_present_after": True,
            "halt_reason_before": None,
            "reconciliation_state": "INCONCLUSIVE",
            "measurement_contract_id": None,
            "evidence_quality": "BLOCKED",
            "halt_cleared": False,
            "orders_submitted": 0,
            "reasons": ["remote_recovery_output_invalid"],
        }
    if remote_exit != 0 and report["status"] in {"RECOVERED", "CLEAR"}:
        report.update(
            status="INCONCLUSIVE",
            halt_present_after=True,
            evidence_quality="BLOCKED",
            halt_cleared=False,
            reasons=["remote_recovery_exit_nonzero"],
        )
    report["workflow_run_id"] = run_id
    report["workflow_commit"] = commit
    report["remote_exit"] = remote_exit
    return report


def render_summary(report: dict[str, object]) -> str:
    reasons = ", ".join(str(item) for item in report.get("reasons", [])) or "없음"
    return "\n".join(
        [
            "# 정합성 halt 자동 복구 - 최신 실행",
            "",
            f"- 상태: `{report['status']}`",
            f"- 정합성: `{report['reconciliation_state']}`",
            f"- 실행 뒤 halt: `{report['halt_present_after']}`",
            f"- halt 해제: `{report['halt_cleared']}`",
            f"- 주문 제출: `{report['orders_submitted']}`",
            f"- 측정 품질: `{report['evidence_quality']}`",
            f"- 이유: `{reasons}`",
            f"- workflow run: `{report['workflow_run_id']}`",
            f"- commit: `{report['workflow_commit']}`",
            "",
            "이 작업은 새 정합성 검사와 조건부 halt 해제만 수행하며 주문은 제출하지 않습니다.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--remote-exit", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args()
    raw = args.raw.read_text(encoding="utf-8") if args.raw.exists() else ""
    report = build_report(
        raw,
        remote_exit=args.remote_exit,
        run_id=args.run_id,
        commit=args.commit,
    )
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    args.summary_out.write_text(render_summary(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
