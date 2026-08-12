#!/usr/bin/env python3
"""Probe for the validation failure data readiness contract."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.candidate_history_support import manifest_document
from auto_invest.analytics.validation_failure_data_readiness import (
    build_validation_failure_data_readiness,
    write_validation_failure_data_readiness_artifacts,
)

CONSUMED_SIDECARS: tuple[tuple[str, str, str], ...] = (
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
    ("public-data", "automation/public-data", "LAST_RUN.md"),
    ("regime-stratify", "automation/regime-stratify-last-run", "LAST_RUN.md"),
    (
        "candidate-history-support",
        "repo",
        "scripts/candidate_history_support_probe.py --json",
    ),
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


def _read_text(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None


def _parse_now(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
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
    parser = argparse.ArgumentParser(
        description="Build validation failure data readiness contract"
    )
    parser.add_argument("--manifest", action="store_true")
    parser.add_argument("--package-plan", type=Path)
    parser.add_argument("--result-evidence", type=Path)
    parser.add_argument("--history-manifest", type=Path)
    parser.add_argument("--public-data", type=Path)
    parser.add_argument("--regime-stratify", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--now")
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--commit")
    args = parser.parse_args(argv)

    if args.manifest:
        for key, branch, filename in CONSUMED_SIDECARS:
            print(f"{key}\t{branch}\t{filename}")
        return 0

    report = build_validation_failure_data_readiness(
        package_plan=_read_json(args.package_plan),
        result_evidence=_read_json(args.result_evidence),
        history_manifest=_read_json(args.history_manifest) or manifest_document(),
        public_data_text=_read_text(args.public_data),
        regime_stratify_text=_read_text(args.regime_stratify),
        repo_root=args.repo_root,
        now=_parse_now(args.now),
        run_id=args.run_id,
        commit=args.commit or _git_commit(),
    )
    write_validation_failure_data_readiness_artifacts(
        report,
        summary_out=args.summary_out,
        json_out=args.json_out,
    )
    print(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        if args.json
        else report.as_markdown()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
