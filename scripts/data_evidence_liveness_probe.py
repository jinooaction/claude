"""스펙 101 — 데이터 증거 생존성 계약 probe.

기존 sidecar 파일을 읽어 JSON/Markdown 보고서를 출력한다. 읽기 전용이며 신규
데이터 수집, 브로커 호출, 주문, 자본 배분, live 설정 변경을 수행하지 않는다.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.data_evidence_liveness import (
    build_data_evidence_liveness_report,
    read_evidence_manifest,
    read_repo_sidecars,
)


def _parse_now(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Data evidence liveness contract probe")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root or local sidecar fixture root.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Tab-separated key, branch/path root, and file path manifest.",
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

    repo_root = args.repo_root.resolve()
    evidence = (
        read_evidence_manifest(args.manifest, repo_root=repo_root)
        if args.manifest
        else read_repo_sidecars(repo_root)
    )
    report = build_data_evidence_liveness_report(
        evidence,
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
