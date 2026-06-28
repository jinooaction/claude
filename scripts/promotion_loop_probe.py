#!/usr/bin/env python3
"""스펙 068 — 자율 승격 루프 probe."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.promotion_loop import scan_promotion, write_promotion_artifacts


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


def _read_evidence(evidence_dir: Path) -> dict[str, str | None]:
    evidence: dict[str, str | None] = {}
    for item in sorted(evidence_dir.glob("*.md")):
        try:
            evidence[item.stem] = item.read_text(encoding="utf-8")
        except OSError:
            evidence[item.stem] = None
    return evidence


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
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--summary-out", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--queue-out", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="summary JSON을 stdout에 출력")
    parser.add_argument("--now", default=None, help="기준 시각 ISO-8601 UTC")
    parser.add_argument("--commit", default=None, help="보고서에 기록할 커밋")
    parser.add_argument("--run-id", default="local", help="보고서 run_id")
    args = parser.parse_args(argv)

    if args.evidence_dir is None:
        parser.error("--evidence-dir 가 필요합니다.")

    summary = scan_promotion(
        candidate_backlog=_read_json(args.evidence_dir / "candidate_backlog.json"),
        evolution_summary=_read_json(args.evidence_dir / "evolution_summary.json"),
        evidence_texts=_read_evidence(args.evidence_dir),
        now=_parse_now(args.now),
        commit=args.commit or _git_commit(),
        run_id=args.run_id,
    )
    write_promotion_artifacts(
        summary,
        summary_out=args.summary_out,
        json_out=args.json_out,
        queue_out=args.queue_out,
    )
    if args.json:
        print(json.dumps(summary.as_dict(), ensure_ascii=False))
    else:
        print(summary.as_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
