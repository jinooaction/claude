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
ACTIVE_SPEC_DIR = REPO / "specs" / "001-automated-trading-mvp"

LONG_LIVED = [
    CONSTITUTION,
    ACTIVE_SPEC_DIR / "spec.md",
    ACTIVE_SPEC_DIR / "plan.md",
    ACTIVE_SPEC_DIR / "data-model.md",
    ACTIVE_SPEC_DIR / "research.md",
]


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
        "# (constitution + active feature: 001-automated-trading-mvp)\n"
        "# Anchored here so Claude Code can amortize this prefix via prompt caching.\n"
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
