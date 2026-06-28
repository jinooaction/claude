#!/usr/bin/env python3
"""스펙 067 — 자율 성장 루프 probe.

워크플로가 `--manifest`로 필요한 sidecar를 수집한 뒤, 이 스크립트가 읽기 전용으로
후보·실험 계획·학습 장부·최신 실행 요약을 만든다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.evolution_loop import (
    DEFAULT_EVIDENCE_REQUIREMENTS,
    candidate_backlog_document,
    ledger_document,
    scan_evolution,
    write_summary_artifacts,
)


def _read_evidence(evidence_dir: Path) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for req in DEFAULT_EVIDENCE_REQUIREMENTS:
        path = evidence_dir / f"{req.key}.md"
        try:
            out[req.key] = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            out[req.key] = None
    for path in sorted(evidence_dir.glob("*.md")):
        key = path.stem
        if key in out:
            continue
        try:
            out[key] = path.read_text(encoding="utf-8")
        except OSError:
            out[key] = None
    return out


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
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="소비 sidecar 목록을 key<TAB>branch<TAB>filename 형식으로 출력",
    )
    parser.add_argument("--evidence-dir", default=None, help="수집한 evidence markdown 디렉터리")
    parser.add_argument("--ledger-json", type=Path, default=None, help="기존 learning ledger JSON")
    parser.add_argument("--summary-out", type=Path, default=None, help="Markdown summary output")
    parser.add_argument(
        "--json-out", type=Path, default=None, help="Machine-readable summary output"
    )
    parser.add_argument(
        "--ledger-out", type=Path, default=None, help="Updated learning ledger output"
    )
    parser.add_argument(
        "--candidate-backlog-out",
        type=Path,
        default=None,
        help="Candidate backlog JSON output",
    )
    parser.add_argument("--json", action="store_true", help="summary JSON을 stdout에 출력")
    parser.add_argument("--now", default=None, help="기준 시각 ISO-8601 UTC")
    parser.add_argument("--commit", default=None, help="보고서에 기록할 커밋")
    parser.add_argument("--run-id", default="local", help="보고서 run_id")
    args = parser.parse_args(argv)

    if args.manifest:
        for req in DEFAULT_EVIDENCE_REQUIREMENTS:
            print(f"{req.key}\t{req.branch}\t{req.filename}")
        return 0

    if not args.evidence_dir:
        parser.error("--evidence-dir 가 필요합니다(--manifest 가 아니면).")

    evidence = _read_evidence(Path(args.evidence_dir))
    ledger = _read_json(args.ledger_json)
    summary = scan_evolution(
        evidence,
        ledger_doc=ledger,
        now=_parse_now(args.now),
        commit=args.commit or _git_commit(),
        run_id=args.run_id,
    )
    write_summary_artifacts(
        summary,
        summary_out=args.summary_out,
        json_out=args.json_out,
        ledger_out=args.ledger_out,
        candidate_backlog_out=args.candidate_backlog_out,
    )

    if args.json:
        print(json.dumps(summary.as_dict(), ensure_ascii=False))
    else:
        print(summary.as_markdown())

    # Sanity: if explicit outputs were not requested, make these docs easy to reproduce
    # from the returned summary object in tests.
    _ = ledger_document(summary.learning_ledger)
    _ = candidate_backlog_document(summary.candidates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
