#!/usr/bin/env python3
"""스펙 069 — 자율 승격 실행 루프 probe."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.promotion_actions import (
    build_promotion_actions,
    write_promotion_action_artifacts,
)


def _read_json(path: Path) -> dict[str, Any] | None:
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
    parser.add_argument("--promotion-summary", type=Path, required=True)
    parser.add_argument("--forward-registry", type=Path, required=True)
    parser.add_argument("--canary-submissions", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--forward-registry-out", type=Path, default=None)
    parser.add_argument("--canary-submissions-out", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="summary JSON을 stdout에 출력")
    parser.add_argument("--now", default=None, help="기준 시각 ISO-8601 UTC")
    parser.add_argument("--commit", default=None, help="보고서에 기록할 커밋")
    parser.add_argument("--run-id", default="local", help="보고서 run_id")
    args = parser.parse_args(argv)

    run = build_promotion_actions(
        promotion_summary=_read_json(args.promotion_summary),
        forward_registry=_read_json(args.forward_registry),
        canary_submissions=_read_json(args.canary_submissions),
        now=_parse_now(args.now),
        commit=args.commit or _git_commit(),
        run_id=args.run_id,
    )
    write_promotion_action_artifacts(
        run,
        summary_out=args.summary_out,
        json_out=args.json_out,
        forward_registry_out=args.forward_registry_out,
        canary_submissions_out=args.canary_submissions_out,
    )
    if args.json:
        print(json.dumps(run.as_dict(), ensure_ascii=False))
    else:
        print(run.as_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
