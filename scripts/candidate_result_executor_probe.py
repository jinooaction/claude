#!/usr/bin/env python3
"""스펙 071 — 후보 결과 실행기 probe."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.candidate_result_executor import (
    build_candidate_result_executor_run,
    write_candidate_result_artifacts,
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
    parser.add_argument("--package-plan", type=Path, required=True)
    parser.add_argument("--released-work", type=Path, default=None)
    parser.add_argument("--summary-out", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--results-out", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="summary JSON을 stdout에 출력")
    parser.add_argument("--now", default=None, help="기준 시각 ISO-8601 UTC")
    parser.add_argument("--commit", default=None, help="보고서에 기록할 커밋")
    parser.add_argument("--run-id", default="local", help="보고서 run_id")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="패키지 명령별 최대 실행 시간",
    )
    args = parser.parse_args(argv)

    run = build_candidate_result_executor_run(
        package_plan=_read_json(args.package_plan),
        released_work=_read_json(args.released_work),
        now=_parse_now(args.now),
        commit=args.commit or _git_commit(),
        run_id=args.run_id,
        timeout_seconds=args.timeout_seconds,
    )
    write_candidate_result_artifacts(
        run,
        summary_out=args.summary_out,
        json_out=args.json_out,
        results_out=args.results_out,
    )
    if args.json:
        print(json.dumps(run.as_dict(), ensure_ascii=False))
    else:
        print(run.as_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
