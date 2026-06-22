#!/usr/bin/env python3
"""Validate that HANDOFF.md summary rows match local repository facts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
HANDOFF_ONLY_PREFIXES = ("specs/",)


@dataclass(frozen=True)
class FactResult:
    id: str
    status: str
    evidence: str
    message: str


@dataclass(frozen=True)
class HandoffFactReport:
    status: str
    facts: list[FactResult]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MainBaseline:
    log: str
    reason: str

    @property
    def short(self) -> str:
        return self.log.split(maxsplit=1)[0] if self.log else ""


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if out.returncode != 0:
        return ""
    return out.stdout.strip()


def _is_handoff_only_path(path: str) -> bool:
    return path.endswith(".md") or path.startswith(HANDOFF_ONLY_PREFIXES)


def _main_baselines(repo: Path) -> list[MainBaseline]:
    main_log = _git(repo, "log", "-1", "--pretty=%h %s", "origin/main")
    baselines = [MainBaseline(log=main_log, reason="origin/main")]

    parents = _git(repo, "rev-list", "--parents", "-n", "1", "origin/main").split()
    if len(parents) < 3:
        return baselines

    current, first_parent = parents[0], parents[1]
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", current):
        return baselines
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", first_parent):
        return baselines

    changed = _git(repo, "diff", "--name-only", first_parent, current).splitlines()
    if changed and all(_is_handoff_only_path(path) for path in changed):
        parent_log = _git(repo, "log", "-1", "--pretty=%h %s", first_parent)
        if parent_log:
            baselines.append(
                MainBaseline(
                    log=parent_log,
                    reason="previous main before handoff-only merge",
                )
            )
    return baselines


def _row_value(text: str, label: str) -> str | None:
    pattern = rf"^\|\s*{re.escape(label)}\s*\|\s*(.*?)\s*\|$"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _fact(passed: bool, *, id: str, evidence: str, ok: str, fail: str) -> FactResult:
    return FactResult(
        id=id,
        status="PASS" if passed else "FAIL",
        evidence=evidence,
        message=ok if passed else fail,
    )


def evaluate(
    repo: Path,
    *,
    handoff_path: Path | None = None,
    expect_pytest: str | None = None,
    expect_ruff: str | None = None,
    expect_open_pr: str | None = None,
) -> HandoffFactReport:
    handoff = handoff_path or repo / "HANDOFF.md"
    facts: list[FactResult] = []
    try:
        text = handoff.read_text(encoding="utf-8")
    except OSError as exc:
        facts.append(
            FactResult(
                id="handoff_readable",
                status="FAIL",
                evidence=str(handoff),
                message=f"cannot read HANDOFF: {exc}",
            )
        )
        return HandoffFactReport(status="DEGRADED", facts=facts)

    baselines = _main_baselines(repo)
    main_row = _row_value(text, "마지막 main 커밋")
    matched = next(
        (
            baseline
            for baseline in baselines
            if baseline.short and main_row and baseline.short in main_row
        ),
        None,
    )
    facts.append(
        _fact(
            matched is not None,
            id="main_commit",
            evidence=(
                "baselines="
                + ", ".join(
                    f"{baseline.reason}:{baseline.log or '(missing)'}"
                    for baseline in baselines
                )
                + f"; HANDOFF={main_row or '(missing)'}"
            ),
            ok=(
                "HANDOFF main commit row matches "
                f"{matched.reason if matched else 'local repository facts'}"
            ),
            fail="HANDOFF main commit row is stale or missing",
        )
    )

    checks = [
        ("main_pytest", "main 테스트", expect_pytest),
        ("main_ruff", "main 린트", expect_ruff),
        ("open_pr", "열린 PR", expect_open_pr),
    ]
    for fact_id, label, expected in checks:
        if expected is None:
            continue
        row = _row_value(text, label)
        facts.append(
            _fact(
                bool(row and expected in row),
                id=fact_id,
                evidence=f"expected={expected}; HANDOFF={row or '(missing)'}",
                ok=f"HANDOFF {label} row contains expected evidence",
                fail=f"HANDOFF {label} row is missing expected evidence",
            )
        )

    status = "OK" if all(fact.status == "PASS" for fact in facts) else "DEGRADED"
    return HandoffFactReport(status=status, facts=facts)


def render_text(report: HandoffFactReport) -> str:
    lines = ["HANDOFF 사실 검증", f"종합 판정: {report.status}", "", "검증 항목:"]
    lines.extend(
        f"- {fact.status} {fact.id}: {fact.message} [{fact.evidence}]"
        for fact in report.facts
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate HANDOFF.md summary facts.")
    parser.add_argument("--repo", type=Path, default=REPO, help="Repository root to inspect.")
    parser.add_argument("--handoff", type=Path, help="HANDOFF path; defaults to repo/HANDOFF.md")
    parser.add_argument("--expect-pytest", help="Expected substring for the main 테스트 row.")
    parser.add_argument("--expect-ruff", help="Expected substring for the main 린트 row.")
    parser.add_argument("--expect-open-pr", help="Expected substring for the 열린 PR row.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    handoff = args.handoff.resolve() if args.handoff else None
    report = evaluate(
        repo,
        handoff_path=handoff,
        expect_pytest=args.expect_pytest,
        expect_ruff=args.expect_ruff,
        expect_open_pr=args.expect_open_pr,
    )
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(render_text(report))
    return 0 if report.status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
