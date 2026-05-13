#!/usr/bin/env python3
"""SessionStart hook — long-lived context + active-work pointer.

Purpose
-------
Anchors Claude Code's prompt-cache prefix at a stable, byte-deterministic
slice of the constitution + the *currently active* feature spec, AND surfaces
the project's active-work pointer so a fresh-workspace session can re-converge
on the right branch and the right next task without operator hand-holding.

Two amendments since the spec-003 cut:

1. **Dynamic active-feature resolution.** The previous version hard-coded
   ``specs/001-automated-trading-mvp``. That meant every session, regardless
   of which feature was actually in flight, received spec 001 as its long-
   lived context — a real source of confusion when a new workspace tried to
   resume spec 008 work and saw nothing about it. The hook now reads
   ``.specify/active-work.json`` for ``active_feature_dir`` and falls back
   to spec 001 only if that file is missing or unparseable.

2. **Branch-resume diagnostics.** The hook now `git fetch origin --prune`
   (silent, idempotent, swallowed-on-failure) and surfaces the current HEAD
   vs the active-work pointer's ``active_branch``. When they diverge, the
   ``systemMessage`` shouts the diagnosis and the recovery command so the
   assistant cannot proceed with a wrong-branch checkout. This closes the
   Claude-Code-Web "fresh workspace + auto-named branch" failure mode that
   surfaced repeatedly during spec 008.

Per FR-S03 we still emit a SHA-256 fingerprint so spec 005's autonomous
tuner can correlate cache-hit-rate with context stability. The fingerprint
input now includes ``active-work.json`` so a deliberate spec switch
invalidates the cache, which is the right semantics.

The hook reads stdin (JSON event), writes a JSON response on stdout, and
exits 0 on success. On any unexpected error it prints a short message on
stderr and still exits 0 — it must NEVER block a session from starting.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

CONSTITUTION = REPO / ".specify" / "memory" / "constitution.md"
KERNEL_MANIFEST = REPO / ".specify" / "memory" / "kernel.toml"
ACTIVE_WORK = REPO / ".specify" / "active-work.json"
DEFAULT_FEATURE_DIR = REPO / "specs" / "001-automated-trading-mvp"


def _read_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _load_active_work() -> dict:
    """Parse active-work.json; return {} on any failure (never raises)."""
    try:
        return json.loads(ACTIVE_WORK.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _resolve_feature_dir(active: dict) -> Path:
    """Return the active feature directory, falling back to spec 001."""
    rel = active.get("active_feature_dir")
    if rel:
        candidate = REPO / rel
        if candidate.is_dir():
            return candidate
    return DEFAULT_FEATURE_DIR


def _git(*args: str) -> str | None:
    """Run git silently; return stripped stdout or None on any failure."""
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=str(REPO),
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        return out.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def _git_fetch_quiet() -> None:
    """Fetch origin (silent, idempotent). Failures are swallowed."""
    try:
        subprocess.run(
            ["git", "fetch", "origin", "--prune", "--quiet"],
            cwd=str(REPO),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except (subprocess.SubprocessError, OSError):
        pass


def _build_context(feature_dir: Path) -> tuple[str, str, list[Path]]:
    """Return (assembled_text, sha256, source_paths)."""
    sources = [
        CONSTITUTION,
        KERNEL_MANIFEST,
        ACTIVE_WORK,
        feature_dir / "spec.md",
        feature_dir / "plan.md",
        feature_dir / "data-model.md",
        feature_dir / "research.md",
    ]

    feature_id = feature_dir.name
    parts: list[str] = [
        "# auto-invest — long-lived session context\n"
        f"# (constitution + kernel + active feature: {feature_id})\n"
        "# Anchored here so Claude Code can amortize this prefix via prompt caching.\n"
    ]
    for p in sources:
        body = _read_safe(p)
        if not body:
            continue
        try:
            rel = p.relative_to(REPO)
        except ValueError:
            rel = p
        parts.append(f"\n\n----- {rel} -----\n\n{body}")

    text = "".join(parts)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, sha, sources


def _build_branch_diagnostic(active: dict) -> tuple[str, bool]:
    """Compare current HEAD to active_branch from active-work.json.

    Returns (one-line summary, is_mismatch). When `is_mismatch` is True the
    assistant SHOULD switch branches before doing any code work.
    """
    current = _git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    tip = _git("log", "-1", "--oneline") or "?"

    desired = active.get("active_branch", "")
    if not desired:
        return f"branch={current} tip={tip}", False

    if current == desired:
        return f"branch={current} OK (matches active-work) tip={tip}", False

    # Mismatch: tell the assistant exactly what to run.
    msg = (
        f"branch MISMATCH -- current={current} active={desired}. "
        f"Run: git checkout {desired} && git pull --ff-only "
        f"(active-work.json is the source of truth; the auto-named branch "
        f"in this fresh workspace is to be ignored unless the operator "
        f"explicitly asked for a new branch). tip={tip}"
    )
    return msg, True


def _next_tasks_summary(active: dict) -> str:
    nt = active.get("next_tasks") or []
    if not nt:
        return ""
    return f" | next: {','.join(nt[:4])}"


def main() -> int:
    try:
        # Drain stdin so the harness sees a clean handshake even if it sent JSON.
        if not sys.stdin.isatty():
            try:
                sys.stdin.read()
            except Exception:
                pass

        # Refresh remote refs before reporting branch state — best-effort.
        _git_fetch_quiet()

        active = _load_active_work()
        feature_dir = _resolve_feature_dir(active)
        text, sha, sources = _build_context(feature_dir)
        branch_msg, is_mismatch = _build_branch_diagnostic(active)
        next_msg = _next_tasks_summary(active)

        marker = "ACTION REQUIRED -- " if is_mismatch else ""
        system_msg = (
            f"{marker}session-context fingerprint: {sha[:12]} "
            f"({len(text)} chars from {len(sources)} sources) | "
            f"{branch_msg}{next_msg}"
        )

        response = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": text,
            },
            "systemMessage": system_msg,
        }
        json.dump(response, sys.stdout)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:  # never block a session
        sys.stderr.write(f"session_context hook: non-fatal error: {exc}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
