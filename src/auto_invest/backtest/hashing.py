"""Determinism-floor hashing helpers (research R-5).

The six hashes recorded in every BACKTEST_STARTED payload + manifest are:
  code_sha       — git HEAD of the working tree (with optional "+dirty")
  dataset_hash   — sha256 over canonicalised OHLCV bars (canonical.py)
  rules_hash     — sha256 over canonicalised rules TOML
  caps_hash      — sha256 over the caps.py source bytes
  whitelist_hash — sha256 over the whitelist.py source bytes
  seed           — operator-provided integer (recorded as-is)

`caps_hash` and `whitelist_hash` are file-content hashes rather than
instance-data hashes because the K1/K2 invariant lives in the file
itself; rebinding caps via env var would not be a Kernel touch and
should not silently invalidate determinism. If a future change moves
caps to a non-Kernel data file, `caps_hash` is updated correspondingly
in the same change set.
"""

from __future__ import annotations

import hashlib
import subprocess
import tomllib
from pathlib import Path

from auto_invest.backtest.errors import BacktestDirtyTreeError

REPO_ROOT = Path(__file__).resolve().parents[3]
CAPS_PATH = REPO_ROOT / "src" / "auto_invest" / "config" / "caps.py"
WHITELIST_PATH = REPO_ROOT / "src" / "auto_invest" / "config" / "whitelist.py"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def code_sha(*, allow_dirty: bool = False, repo_root: Path | None = None) -> str:
    """git HEAD sha; appends ``+dirty`` when working tree has uncommitted changes.

    Raises BacktestDirtyTreeError when the tree is dirty and `allow_dirty`
    is False (CLI exit code 6).
    """
    cwd = str(repo_root or REPO_ROOT)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain=1"], cwd=cwd, text=True)
    is_dirty = bool(status.strip())
    if is_dirty and not allow_dirty:
        raise BacktestDirtyTreeError(
            "working tree has uncommitted changes; pass allow_dirty=True to proceed"
        )
    return f"{head}+dirty" if is_dirty else head


def rules_hash(toml_path: Path) -> str:
    """Hash a rules TOML by canonicalised content.

    The TOML is parsed and re-serialised in sort-key JSON form before
    hashing so whitespace / comment changes that don't affect semantics
    don't perturb the hash.
    """
    import json

    parsed = tomllib.loads(Path(toml_path).read_text())
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(canonical.encode("utf-8"))


def caps_hash() -> str:
    """Sha256 of `config/caps.py` bytes (K1 file)."""
    return _sha256_file(CAPS_PATH)


def whitelist_hash() -> str:
    """Sha256 of `config/whitelist.py` bytes (K2 file)."""
    return _sha256_file(WHITELIST_PATH)
