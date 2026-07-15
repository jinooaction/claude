#!/usr/bin/env python3
"""운영자 이해 가능 보고 생존성 계약 probe."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.operator_report_liveness import (
    build_operator_report_liveness_report,
    collect_repo_evidence,
)


def _parse_now(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Operator-readable final report liveness probe"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root to inspect.",
    )
    parser.add_argument("--final-report", type=Path, help="Final report text file.")
    parser.add_argument("--released-work", type=Path, help="released_work.json file.")
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        help="Directory containing final-report.md and released-work.json.",
    )
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

    evidence = collect_repo_evidence(
        args.repo_root,
        final_report_path=args.final_report,
        released_work_path=args.released_work,
        evidence_dir=args.evidence_dir,
    )
    report = build_operator_report_liveness_report(
        evidence,
        repo_root=args.repo_root,
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
