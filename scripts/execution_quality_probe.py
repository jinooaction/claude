"""스펙 083 — 실행 품질 패키지 probe.

워크플로가 automation sidecar 브랜치들을 읽어 `<key>.md` 파일로 모아두면, 이 probe가
순수 코어(`analytics.execution_quality`)로 JSON/Markdown을 발행한다.

읽기 전용 — 주문 0건, 돈 0 이동, 브로커 호출 0건.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.execution_quality import build_execution_quality

CONSUMED_SIDECARS: list[tuple[str, str, str]] = [
    (
        "opportunity-monitor",
        "automation/rebalance-micro-gtaa-last-run",
        "opportunity_monitor.json",
    ),
    (
        "opportunity-history",
        "automation/rebalance-micro-gtaa-last-run",
        "opportunity_history.json",
    ),
    ("rebalance-micro-gtaa", "automation/rebalance-micro-gtaa-last-run", "LAST_RUN.md"),
    ("kis-smoke", "automation/kis-smoke-last-run", "LAST_RUN.md"),
]


def _parse_now(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _read_evidence(evidence_dir: Path) -> dict[str, str | None]:
    evidence: dict[str, str | None] = {}
    for key, _, _ in CONSUMED_SIDECARS:
        path = evidence_dir / f"{key}.md"
        try:
            evidence[key] = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            evidence[key] = None
    return evidence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execution quality sidecar probe")
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Print consumed sidecars as key<TAB>branch<TAB>filename and exit.",
    )
    parser.add_argument(
        "--evidence-dir",
        "--sidecar-dir",
        dest="evidence_dir",
        type=Path,
        default=Path("."),
        help="Directory containing <key>.md sidecar snapshots.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--json-out", type=Path, help="Write JSON report to this path.")
    parser.add_argument("--summary-out", type=Path, help="Write Markdown report to this path.")
    parser.add_argument("--now", help="Override current UTC time for deterministic tests.")
    parser.add_argument("--run-id", default="local", help="Workflow run id.")
    parser.add_argument("--commit", default="unknown", help="Source commit hash.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.manifest:
        for key, branch, filename in CONSUMED_SIDECARS:
            print(f"{key}\t{branch}\t{filename}")
        return 0

    report = build_execution_quality(
        _read_evidence(args.evidence_dir),
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

    print(json_text if args.json else markdown_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
