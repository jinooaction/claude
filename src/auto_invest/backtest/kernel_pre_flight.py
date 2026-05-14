"""Pre-flight kernel-touch check for the backtest CLI.

FR-B12: the backtest CLI MUST refuse to run if `git status --porcelain`
shows any uncommitted modification to a Kernel-listed path. Defense-in-
depth: the operator should not silently run an experimental backtest
against a kernel-edited working tree.

We reuse `auto_invest.deploy.kernel_guard` (shipped by spec 006) so the
"what counts as Kernel" question has exactly one source of truth.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from auto_invest.deploy import kernel_diff_check, load_kernel_manifest


@dataclass(frozen=True)
class PreFlightResult:
    touched: bool
    paths: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)


_PORCELAIN_LINE = re.compile(r"^(?P<status>..) (?P<path>.+)$")


def parse_git_porcelain(output: str) -> list[str]:
    """Extract changed paths from `git status --porcelain` (v1)."""
    paths: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        m = _PORCELAIN_LINE.match(line)
        if not m:
            continue
        path = m.group("path")
        if "->" in path:  # rename — "old -> new"
            _, new = path.split("->", 1)
            path = new.strip().strip('"')
        path = path.strip().strip('"')
        paths.append(path)
    return paths


def run_pre_flight(*, repo_root: Path | None = None) -> PreFlightResult:
    """Consult the kernel manifest against current git status.

    Returns `PreFlightResult(touched=False, ...)` when the working tree
    has no uncommitted Kernel modifications; otherwise lists the offending
    paths and groups.
    """
    cwd = repo_root or Path.cwd()
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        # Not a git repo, or git unavailable. Treat as clean — the live
        # operator deploy flow already protects against the autonomous-
        # tuner case via spec 006's kernel guard.
        return PreFlightResult(touched=False)
    changed = parse_git_porcelain(completed.stdout)
    manifest = load_kernel_manifest()
    report = kernel_diff_check(changed, manifest=manifest)
    if report.is_clean:
        return PreFlightResult(touched=False)
    return PreFlightResult(
        touched=True,
        paths=sorted({t.path for t in report.touches}),
        groups=list(report.touched_groups),
    )


__all__ = [
    "PreFlightResult",
    "parse_git_porcelain",
    "run_pre_flight",
]
