#!/usr/bin/env python3
"""SessionStart hook — live git ground-truth.

WHY THIS EXISTS
---------------
`session_context.py` anchors the *static* long-lived context (constitution +
the active feature docs) so the harness can amortize a stable prompt-cache
prefix. By design it is byte-stable, so it must NOT carry anything that changes
every commit. But a session that only sees static files keeps mis-reading the
*current* repo state (which branch, what is actually on `main`, which HANDOFF is
live). That is the recurring "history/state confusion" failure.

This second, deliberately SMALL hook closes that gap. It emits a short, dynamic
snapshot of the LOCAL git state — current branch, HEAD, how far HEAD sits from
`origin/main`, the most recent `origin/main` commits, and the HANDOFF files
newest-first. It is intentionally local-only (no `git fetch`, no network) so it
can never hang a session start; the heavier network discovery (open PRs, remote
`claude/*` branches) lives in the `/sync` skill, which this snapshot points to.

Like every SessionStart hook here it MUST never block a session: any error is
swallowed and we exit 0 with whatever we managed to gather.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


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


def _handoff_lines() -> list[str]:
    """HANDOFF*.md at repo root, newest-number first, with their title line."""
    files = sorted(REPO.glob("HANDOFF*.md"), reverse=True)
    lines: list[str] = []
    for f in files:
        title = ""
        with contextlib.suppress(OSError):
            for raw in f.read_text(encoding="utf-8").splitlines():
                if raw.strip():
                    title = raw.lstrip("# ").strip()
                    break
        lines.append(f"  - {f.name}: {title}")
    return lines


def _build() -> str:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
    head = _git("log", "-1", "--pretty=%h %s")
    dirty = _git("status", "--porcelain")
    dirty_n = len([ln for ln in dirty.splitlines() if ln.strip()])

    # ahead/behind vs origin/main using local refs only (reflects last fetch).
    ab = _git("rev-list", "--left-right", "--count", "origin/main...HEAD")
    behind = ahead = "?"
    if ab and len(ab.split()) == 2:
        behind, ahead = ab.split()

    main_log = _git("log", "origin/main", "-8", "--pretty=  %h %s")
    head_log = _git("log", "HEAD", "-6", "--pretty=  %h %s")

    parts = [
        "# auto-invest — LIVE git ground-truth (dynamic)",
        "# Read this before trusting any prose 'active feature' line.",
        "# Local refs only — for open PRs and remote claude/* branches, run the /sync skill.",
        "",
        f"current branch : {branch}",
        f"HEAD           : {head}",
        f"working tree   : {'clean' if dirty_n == 0 else f'{dirty_n} uncommitted path(s)'}",
        f"vs origin/main : {ahead} ahead, {behind} behind (local refs; /sync to refresh)",
        "",
        "recent origin/main (what is actually merged):",
        main_log or "  (origin/main ref not found — run /sync)",
    ]
    if branch != "main" and ahead not in ("0", "?"):
        parts += ["", "recent HEAD (this branch's unmerged work):", head_log]
    handoff = _handoff_lines()
    if handoff:
        parts += [
            "",
            "HANDOFF files (newest first — the highest-numbered one is usually live):",
            *handoff,
        ]
    parts += [
        "",
        "NOTE: the static context block hardcodes nothing about 'active feature' anymore;",
        "trust THIS snapshot + the newest HANDOFF for current state, and run /sync for PRs.",
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
