#!/usr/bin/env python3
"""SessionStart hook for spec 003-session-cache.

Surfaces the long-lived context (constitution + active spec/plan/data-model)
as additionalContext so Claude Code can anchor prompt caching at a stable
prefix. The output is byte-stable until the underlying files change, which
gives the harness a natural cache key.

Per FR-S03, we also emit a SHA-256 fingerprint so 005's autonomous tuner can
correlate cache-hit-rate with context stability.

The hook reads stdin (JSON event), writes a JSON response on stdout, and exits
with code 0 on success. On any unexpected error it prints a short message on
stderr and exits 0 — it must NEVER block a session from starting.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

CONSTITUTION = REPO / ".specify" / "memory" / "constitution.md"


def _long_lived() -> list[Path]:
    """The genuinely long-lived docs to anchor for prompt-cache stability.

    Used to hardcode specs/001 (the first, long-shipped feature), which both
    wasted the cached prefix on irrelevant content and lied to every session
    about the "active feature". Anchor instead the docs that are actually
    long-lived AND current: the constitution, the workflow policy (CLAUDE.md),
    and the live HANDOFF entry points. These stay byte-stable until they
    change, so the cache key is still natural — but it now reflects reality.

    The newest-numbered HANDOFF-NNN.md is the live work pointer; HANDOFF.md is
    the main-branch entry point. We include both and let the live git-state
    hook supply the volatile details.
    """
    paths = [CONSTITUTION, REPO / "CLAUDE.md", REPO / "HANDOFF.md"]
    numbered = sorted(REPO.glob("HANDOFF-*.md"), reverse=True)
    if numbered:
        paths.append(numbered[0])
    return [p for p in paths if p.exists()]


LONG_LIVED = _long_lived()


def _read_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _build_context() -> tuple[str, str]:
    """Return (assembled_text, sha256). Empty inputs yield an empty body."""
    parts: list[str] = []
    parts.append(
        "# auto-invest — long-lived session context\n"
        "# (constitution + workflow policy + live HANDOFF entry points)\n"
        "# Anchored here so Claude Code can amortize this prefix via prompt caching.\n"
        "# For the CURRENT branch / main / PR state, see the live git ground-truth block.\n"
    )
    for p in LONG_LIVED:
        body = _read_safe(p)
        if not body:
            continue
        parts.append(f"\n\n----- {p.relative_to(REPO)} -----\n\n{body}")
    text = "".join(parts)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, sha


def main() -> int:
    try:
        # Drain stdin so the harness sees a clean handshake even if it sent JSON.
        if not sys.stdin.isatty():
            try:
                sys.stdin.read()
            except Exception:
                pass

        text, sha = _build_context()
        response = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": text,
            },
            "systemMessage": (
                f"session-context fingerprint: {sha[:12]} "
                f"({len(text)} chars from {len(LONG_LIVED)} sources)"
            ),
        }
        json.dump(response, sys.stdout)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:  # never block a session
        sys.stderr.write(f"session_context hook: non-fatal error: {exc}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
