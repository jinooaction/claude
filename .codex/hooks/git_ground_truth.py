#!/usr/bin/env python3
"""SessionStart hook - live git ground truth.

WHY THIS EXISTS
---------------
`session_context.py` anchors the *static* long-lived context (constitution +
the active feature docs) so the harness can amortize a stable prompt-cache
prefix. By design it is byte-stable, so it must NOT carry anything that changes
every commit. But a session that only sees static files keeps mis-reading the
*current* repo state (which branch, what is actually on `main`, which HANDOFF is
live). That is the recurring "history/state confusion" failure.

This second, deliberately SMALL hook closes that gap. It emits a compact,
dynamic snapshot of the LOCAL git state: current branch, HEAD, how far HEAD sits
from `origin/main`, the most recent `origin/main` commits, a small dirty-worktree
sample, and only the live HANDOFF entry points. It is intentionally local-only
(no `git fetch`, no network) so it can never hang a session start; the heavier
network discovery (open PRs, remote branches) lives in the `/sync` skill, which
this snapshot points to.

Like every SessionStart hook here it MUST never block a session: any error is
swallowed and we exit 0 with whatever we managed to gather.
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAIN_LOG_LIMIT = 5
HEAD_LOG_LIMIT = 4
DIRTY_SAMPLE_LIMIT = 6
NUMBERED_HANDOFF_LIMIT = 3


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def _title(path: Path) -> str:
    with contextlib.suppress(OSError):
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                return raw.lstrip("# ").strip()
    return ""


def _handoff_number(path: Path) -> int:
    match = re.match(r"HANDOFF-(\d+)-", path.name)
    return int(match.group(1)) if match else -1


def _handoff_lines() -> list[str]:
    """Return only the handoff entry points needed to orient a new session."""
    files: list[Path] = []
    root_handoff = REPO / "HANDOFF.md"
    if root_handoff.exists():
        files.append(root_handoff)
    files.extend(
        sorted(
            REPO.glob("HANDOFF-*.md"),
            key=lambda p: (_handoff_number(p), p.name),
            reverse=True,
        )[:NUMBERED_HANDOFF_LIMIT]
    )

    lines: list[str] = []
    for f in files:
        title = ""
        title = _title(f)
        lines.append(f"  - {f.name}: {title}")
    return lines


def _dirty_summary(porcelain: str) -> tuple[str, list[str]]:
    rows = [ln for ln in porcelain.splitlines() if ln.strip()]
    if not rows:
        return "clean", []
    sample = rows[:DIRTY_SAMPLE_LIMIT]
    if len(rows) > DIRTY_SAMPLE_LIMIT:
        sample.append(f"... {len(rows) - DIRTY_SAMPLE_LIMIT} more path(s)")
    return f"{len(rows)} changed path(s)", [f"  {ln}" for ln in sample]


def _build() -> str:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
    head = _git("log", "-1", "--pretty=%h %s")
    dirty = _git("status", "--porcelain")
    dirty_text, dirty_sample = _dirty_summary(dirty)

    # ahead/behind vs origin/main using local refs only (reflects last fetch).
    ab = _git("rev-list", "--left-right", "--count", "origin/main...HEAD")
    behind = ahead = "?"
    if ab and len(ab.split()) == 2:
        behind, ahead = ab.split()

    main_log = _git("log", "origin/main", f"-{MAIN_LOG_LIMIT}", "--pretty=  %h %s")
    head_log = _git("log", "HEAD", f"-{HEAD_LOG_LIMIT}", "--pretty=  %h %s")

    parts = [
        "# auto-invest - LIVE git ground truth (local, dynamic)",
        "# Read this before trusting any prose 'active feature' line.",
        "# No network here. Run /sync for open PRs, remote branches, and refreshed refs.",
        "",
        f"current branch : {branch}",
        f"HEAD           : {head}",
        f"working tree   : {dirty_text}",
        f"vs origin/main : {ahead} ahead, {behind} behind (local refs; /sync to refresh)",
    ]
    if dirty_sample:
        parts += ["dirty sample   :", *dirty_sample]
    parts += [
        "",
        f"recent origin/main (latest {MAIN_LOG_LIMIT} local commit(s)):",
        main_log or "  (origin/main ref not found - run /sync)",
    ]
    if branch != "main" and ahead not in ("0", "?"):
        parts += ["", "recent HEAD (this branch's unmerged work):", head_log]
    handoff = _handoff_lines()
    if handoff:
        parts += [
            "",
            "HANDOFF entry points:",
            *handoff,
        ]
    parts += [
        "",
        "NOTE: trust this local snapshot + HANDOFF.md before older prose;",
        "run /sync before PR, merge, deploy, or remote-branch decisions.",
    ]
    return "\n".join(parts)


def main() -> int:
    try:
        if not sys.stdin.isatty():
            with contextlib.suppress(Exception):
                sys.stdin.read()
        text = _build()
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": text,
                },
                "systemMessage": "git ground-truth emitted (run /sync for PRs + remote branches)",
            },
            sys.stdout,
        )
        sys.stdout.write("\n")
        return 0
    except Exception as exc:  # never block a session
        sys.stderr.write(f"git_ground_truth hook: non-fatal error: {exc}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
