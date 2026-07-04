"""스펙 077 — 자율 작업 실행 루프 probe.

워크플로가 automation sidecar 브랜치들을 읽어 `<key>.md` 파일로 모아두면, 이 probe가
순수 코어(`analytics.autonomous_work_execution`)로 다음 작업 패킷을 발행한다.

읽기 전용 — 주문 0건, 돈 0 이동, 코드/PR 자동 생성 없음. 사용:
  uv run python scripts/autonomous_work_execution_probe.py --manifest
  uv run python scripts/autonomous_work_execution_probe.py --evidence-dir /tmp/sidecars --json
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.autonomous_work_execution import build_autonomous_work_execution
from auto_invest.analytics.released_work import scan_released_work

CONSUMED_SIDECARS: list[tuple[str, str, str]] = [
    (
        "capital-path-readiness",
        "automation/capital-path-readiness-last-run",
        "capital_path_readiness.json",
    ),
    ("evolution-backlog", "automation/autonomous-evolution-last-run", "candidate_backlog.json"),
    ("evolution-ledger", "automation/autonomous-evolution-last-run", "learning_ledger.json"),
    (
        "autonomous-promotion",
        "automation/autonomous-promotion-last-run",
        "promotion_summary.json",
    ),
    (
        "candidate-implementation-factory",
        "automation/candidate-implementation-factory-last-run",
        "candidate_factory.json",
    ),
    (
        "candidate-packages",
        "automation/candidate-implementation-factory-last-run",
        "candidate_packages.json",
    ),
    (
        "candidate-result-executor",
        "automation/candidate-implementation-results",
        "candidate_results.json",
    ),
    ("rebalance-paper-forward", "automation/rebalance-paper-forward-last-run", "LAST_RUN.md"),
    ("edge-autoarm", "automation/edge-autoarm-last-run", "LAST_RUN.md"),
    ("money-path", "automation/money-path-last-run", "LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run", "released_work.json"),
    ("pipeline-liveness", "automation/pipeline-liveness-last-run", "LAST_RUN.md"),
]


def _parse_now(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _read_evidence(
    evidence_dir: Path,
    *,
    repo_root: Path | None,
    now: datetime,
    run_id: str,
    commit: str,
) -> dict[str, str | None]:
    evidence: dict[str, str | None] = {}
    for key, _, _ in CONSUMED_SIDECARS:
        path = evidence_dir / f"{key}.md"
        try:
            evidence[key] = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            evidence[key] = None
    if repo_root is not None:
        report = scan_released_work(repo_root, now=now, run_id=run_id, commit=commit)
        evidence["released-work"] = json.dumps(
            report.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )
    return evidence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Autonomous work execution sidecar probe")
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
    parser.add_argument(
        "--repo-root",
        type=Path,
        help=(
            "Repository root to scan for completed specs. When provided, current checkout "
            "released-work evidence overrides the sidecar snapshot."
        ),
    )
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

    now = _parse_now(args.now)
    report = build_autonomous_work_execution(
        _read_evidence(
            args.evidence_dir,
            repo_root=args.repo_root,
            now=now,
            run_id=args.run_id,
            commit=args.commit,
        ),
        now=now,
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
