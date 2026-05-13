"""Kernel-touch guard — spec 006 FR-D13, constitution IX.

Reads `.specify/memory/kernel.toml` and decides whether a given diff
intersects the Kernel. If yes, the deploy automation must abort and
emit a `DEPLOY_BLOCKED_KERNEL_TOUCH` audit row (constitution IX.B-1).

Path semantics
--------------
- File paths protect exactly that file.
- Directory paths (entries ending with `/`) protect every file under
  them recursively.
- Comparison is case-sensitive and uses POSIX-style separators; the
  caller is expected to feed paths from `git diff --name-only` which
  already produces POSIX paths.

This module deliberately has zero runtime dependencies beyond the
standard library + pydantic so it can be imported by the deploy
script before `uv sync` runs.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_MANIFEST_PATH = Path(".specify/memory/kernel.toml")


class KernelGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str
    files: tuple[str, ...] = Field(default_factory=tuple)


class KernelManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    groups: dict[str, KernelGroup]
    source_path: str

    @property
    def all_paths(self) -> tuple[str, ...]:
        out: list[str] = []
        for group in self.groups.values():
            out.extend(group.files)
        return tuple(out)

    def match(self, changed_path: str) -> tuple[str, ...]:
        """Return the manifest groups that protect `changed_path`.

        A path matches a manifest entry if the entry equals the path
        exactly OR the entry ends with `/` and is a path-prefix of the
        changed path.
        """
        normalized = changed_path.replace("\\", "/")
        # Strip a single leading "./" only (so ".specify/..." is preserved).
        if normalized.startswith("./"):
            normalized = normalized[2:]
        hits: list[str] = []
        for group_name, group in self.groups.items():
            for protected in group.files:
                if protected.endswith("/"):
                    if normalized.startswith(protected):
                        hits.append(group_name)
                        break
                elif normalized == protected:
                    hits.append(group_name)
                    break
        return tuple(hits)


class KernelManifestError(ValueError):
    """Raised on missing manifest, unreadable TOML, or schema violation."""


def load_kernel_manifest(path: Path | None = None) -> KernelManifest:
    """Load and validate the kernel manifest TOML."""
    manifest_path = path or DEFAULT_MANIFEST_PATH
    if not manifest_path.exists():
        raise KernelManifestError(f"kernel manifest not found: {manifest_path}")
    try:
        raw = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise KernelManifestError(
            f"kernel manifest {manifest_path} is not valid TOML: {exc}"
        ) from exc

    groups: dict[str, KernelGroup] = {}
    for name, block in raw.items():
        if not isinstance(block, dict):
            raise KernelManifestError(f"kernel manifest entry {name!r} must be a TOML table")
        try:
            groups[name] = KernelGroup(
                description=block.get("description", ""),
                files=tuple(block.get("files", [])),
            )
        except (ValueError, TypeError) as exc:
            raise KernelManifestError(
                f"kernel manifest entry {name!r} failed validation: {exc}"
            ) from exc

    if not groups:
        raise KernelManifestError(f"kernel manifest {manifest_path} is empty")

    # K-meta MUST exist — without it the kernel is autonomously revocable
    # (constitution IX.A "K-meta must be its own fixed-point").
    if "K_meta" not in groups:
        raise KernelManifestError(f"kernel manifest {manifest_path} missing required K_meta group")

    return KernelManifest(groups=groups, source_path=str(manifest_path))


@dataclass(frozen=True)
class KernelGroupTouch:
    """One file from the diff that touched one or more Kernel groups."""

    path: str
    groups: tuple[str, ...]


@dataclass(frozen=True)
class KernelTouchReport:
    """Result of `kernel_diff_check`. Empty `touches` means safe to auto-merge."""

    touches: tuple[KernelGroupTouch, ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        return len(self.touches) == 0

    @property
    def touched_groups(self) -> tuple[str, ...]:
        seen: list[str] = []
        for t in self.touches:
            for g in t.groups:
                if g not in seen:
                    seen.append(g)
        return tuple(seen)

    def reason(self) -> str:
        if self.is_clean:
            return "no kernel files in diff"
        parts = [f"{t.path} (groups: {', '.join(t.groups)})" for t in self.touches]
        return "kernel files touched: " + "; ".join(parts)


def kernel_diff_check(
    changed_paths: list[str] | tuple[str, ...],
    manifest: KernelManifest | None = None,
) -> KernelTouchReport:
    """Decide whether a diff intersects the Kernel.

    Args:
        changed_paths: list of POSIX-style paths from `git diff --name-only`.
        manifest: pre-loaded manifest; loaded from default path if None.

    Returns:
        `KernelTouchReport`. `is_clean=True` means autonomous merge is
        permitted by constitution IX.B-1; the deploy still needs to
        satisfy IX.B-2 (hardened canary, when 007 ships).
    """
    if manifest is None:
        manifest = load_kernel_manifest()

    touches: list[KernelGroupTouch] = []
    for path in changed_paths:
        groups = manifest.match(path)
        if groups:
            touches.append(KernelGroupTouch(path=path, groups=groups))
    return KernelTouchReport(touches=tuple(touches))
