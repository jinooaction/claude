#!/usr/bin/env python3
"""스펙 070 — 후보 구현 공장 probe."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.candidate_factory import (
    build_candidate_factory_run,
    write_candidate_factory_artifacts,
)


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _parse_now(text: str | None) -> datetime:
    if not text:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-backlog", type=Path, required=True)
    parser.add_argument("--promotion-summary", type=Path, default=None)
    parser.add_argument("--result-evidence", type=Path, default=None)
    parser.add_argument("--summary-out", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--enriched-backlog-out", type=Path, default=None)
    parser.add_argument("--package-plan-out", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="summary JSON을 stdout에 출력")
    parser.add_argument("--now", default=None, help="기준 시각 ISO-8601 UTC")
    parser.add_argument("--commit", default=None, help="보고서에 기록할 커밋")
    parser.add_argument("--run-id", default="local", help="보고서 run_id")
    args = parser.parse_args(argv)

    run = build_candidate_factory_run(
        candidate_backlog=_read_json(args.candidate_backlog),
        promotion_summary=_read_json(args.promotion_summary),
        result_evidence=_read_json(args.result_evidence),
        now=_parse_now(args.now),
        commit=args.commit or _git_commit(),
        run_id=args.run_id,
    )
    write_candidate_factory_artifacts(
        run,
        summary_out=args.summary_out,
        json_out=args.json_out,
        enriched_backlog_out=args.enriched_backlog_out,
        package_plan_out=args.package_plan_out,
    )
    if args.json:
        print(json.dumps(run.as_dict(), ensure_ascii=False))
    else:
        print(run.as_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
