#!/usr/bin/env python3
"""스펙 107 — HANDOFF 사실성 생존성 계약 probe.

저장소와 HANDOFF 파일을 읽어 JSON/Markdown 보고서를 출력한다. 읽기 전용이며
PR 생성, 머지, 배포, 브로커 호출, 주문, 자본 배분, live 설정 변경을 수행하지 않는다.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.handoff_truth_liveness import (
    build_handoff_truth_liveness_report,
)


def _parse_now(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HANDOFF truth liveness contract probe")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root to inspect.",
    )
    parser.add_argument(
        "--handoff",
        type=Path,
        help="HANDOFF path; defaults to <repo-root>/HANDOFF.md.",
    )
    parser.add_argument("--expect-pytest", help="Expected substring for main 테스트 row.")
    parser.add_argument("--expect-ruff", help="Expected substring for main 린트 row.")
    parser.add_argument("--expect-open-pr", help="Expected substring for 열린 PR row.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument("--json-out", type=Path, help="Write JSON report to this path.")
    parser.add_argument("--summary-out", type=Path, help="Write Markdown report to this path.")
    parser.add_argument("--now", help="Override current UTC time for deterministic tests.")
    parser.add_argument("--run-id", default="local", help="Workflow run id.")
    parser.add_argument("--commit", default="unknown", help="Source commit hash.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    report = build_handoff_truth_liveness_report(
        repo_root,
        handoff_path=args.handoff,
        expect_pytest=args.expect_pytest,
        expect_ruff=args.expect_ruff,
        expect_open_pr=args.expect_open_pr,
        now=_parse_now(args.now),
        run_id=args.run_id,
        commit=args.commit,
    )
    json_text = json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
    markdown_text = report.as_markdown()

    if args.json_out:
        args.json_out.write_text(json_text + "\n", encoding="utf-8")
    if args.summary_out:
        args.summary_out.write_text(markdown_text + "\n", encoding="utf-8")

    print(json_text if args.format == "json" else markdown_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
