"""Git rev resolution + diff + kernel-touch detection (T010).

Used by the canary run orchestrator to:

1. Resolve the candidate-rev and baseline-rev to canonical SHA-40 strings
   (recorded in `canary-run.json` for reproducibility — R-C1).
2. Compute the set of paths the candidate adds, modifies, or deletes
   relative to baseline (`git diff --name-only`).
3. Project that path set onto the kernel manifest groups
   (R-C8 — the `CANARY_KERNEL_TOUCH_DETECTED` payload is computed here).
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from auto_invest.canary.data_model import KernelGroup, KernelTouch
from auto_invest.deploy import KernelManifest, load_kernel_manifest

FALLBACK_BASELINE = "origin/main"


class GitRevResolutionError(RuntimeError):
    """Raised when a ref-or-sha cannot be resolved to a SHA-40."""


@dataclass(frozen=True)
class _GitRunner:
    """Tiny indirection so tests can swap subprocess.run."""

    cwd: Path

    def run(self, args: list[str]) -> str:
        if shutil.which("git") is None:
            raise GitRevResolutionError("git executable not found in PATH")
        result = subprocess.run(
            ["git", *args],
            cwd=self.cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise GitRevResolutionError(
                f"git {' '.join(args)} failed (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )
        return result.stdout


def resolve_rev(ref_or_sha: str, *, cwd: Path | None = None) -> str:
    """Resolve a symbolic ref or short SHA to a canonical SHA-40.

    Symbolic refs (`HEAD`, `origin/main`, tags) and abbreviated SHAs are
    expanded via ``git rev-parse``. The result is always 40 lowercase
    hex characters. Raises ``GitRevResolutionError`` on any failure.
    """

    runner = _GitRunner(cwd=cwd or Path.cwd())
    stdout = runner.run(["rev-parse", "--verify", f"{ref_or_sha}^{{commit}}"])
    sha = stdout.strip()
    if len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha):
        raise GitRevResolutionError(
            f"rev-parse returned non-SHA-40 result for {ref_or_sha!r}: {sha!r}"
        )
    return sha


def resolve_baseline(
    *,
    audit_conn: sqlite3.Connection,
    candidate_rev: str,
    cwd: Path | None = None,
    fallback: str = FALLBACK_BASELINE,
) -> str:
    """Resolve the baseline rev per R-C1.

    Priority:
      1. The most recent ``CANARY_PASSED`` audit row whose
         ``payload.candidate_rev`` differs from ``candidate_rev``.
         (Equal rev would compare the candidate against itself — no signal.)
      2. The configured fallback ref (default ``origin/main``).

    Always returns a SHA-40.
    """

    rows = audit_conn.execute(
        """
        SELECT payload_json
        FROM audit_log
        WHERE event_type = 'CANARY_PASSED'
        ORDER BY seq DESC
        """,
    ).fetchall()
    for row in rows:
        # Cheap inline JSON probe to avoid pulling pydantic in for a one-field read.
        import json

        try:
            payload = json.loads(row["payload_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        prior = payload.get("candidate_rev")
        if isinstance(prior, str) and len(prior) == 40 and prior != candidate_rev:
            return prior

    # Fallback: the configured ref. Resolve to SHA-40 for reproducibility.
    return resolve_rev(fallback, cwd=cwd)


def diff_paths(
    *,
    baseline_sha: str,
    candidate_sha: str,
    cwd: Path | None = None,
) -> list[str]:
    """Return the list of paths changed between baseline and candidate.

    Equivalent to ``git diff --name-only <baseline>..<candidate>``. The
    output is sorted lexicographically (the producer of the kernel-touch
    payload depends on stable ordering for SC-C04 reproducibility).
    """

    if baseline_sha == candidate_sha:
        return []
    runner = _GitRunner(cwd=cwd or Path.cwd())
    stdout = runner.run(["diff", "--name-only", f"{baseline_sha}..{candidate_sha}"])
    paths = [line.strip() for line in stdout.splitlines() if line.strip()]
    return sorted(paths)


def intersect_kernel(
    touched_paths: Iterable[str],
    manifest: KernelManifest | None = None,
) -> list[KernelTouch]:
    """Project touched paths onto kernel manifest groups (R-C8).

    Returns one ``KernelTouch`` per touched group, with files sorted
    lexicographically and groups sorted by kernel-rank
    (K1, K2, K3, K4, K5, K6, K_meta). The deterministic ordering is
    required for SC-C04 byte-identical reproducibility.
    """

    if manifest is None:
        manifest = load_kernel_manifest()

    per_group: dict[str, list[str]] = {}
    for path in touched_paths:
        for group in manifest.match(path):
            per_group.setdefault(group, []).append(path)

    if not per_group:
        return []

    rank: dict[str, int] = {
        "K1_position_sizing": 1,
        "K2_whitelist": 2,
        "K3_judgment_points": 3,
        "K4_append_only_audit": 4,
        "K5_secret_isolation": 5,
        "K6_market_hours_guard": 6,
        "K_meta": 7,
    }

    out: list[KernelTouch] = []
    for group_name in sorted(per_group, key=lambda g: rank.get(g, 99)):
        out.append(
            KernelTouch(
                group=cast(KernelGroup, _normalize_group_label(group_name)),
                files=sorted(set(per_group[group_name])),
            )
        )
    return out


def _normalize_group_label(group_name: str) -> str:
    """Map ``kernel.toml`` table keys onto the K1..K6 / K_meta data-model labels.

    The manifest uses descriptive table keys like ``K1_position_sizing``;
    the data model uses bare ``K1``..``K_meta``. Keep the mapping local so
    the manifest can rename groups without breaking persisted artefacts.
    """

    if group_name == "K_meta":
        return "K_meta"
    if group_name.startswith("K") and "_" in group_name:
        prefix = group_name.split("_", 1)[0]
        if prefix in {"K1", "K2", "K3", "K4", "K5", "K6"}:
            return prefix
    return group_name
