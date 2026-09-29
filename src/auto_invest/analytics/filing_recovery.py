"""Archive verified failed-publication evidence under a new availability marker."""

import json
import re
import tempfile
from pathlib import Path

from auto_invest.analytics.filing_observations import (
    MAX_BYTES,
    RunStore,
    _encode,
    _fields,
    _no_symlink,
    _require,
    utc,
)

MAX_FILES = 5000
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_RECOVERY_DEPTH = 4


def _allowed(name: str) -> bool:
    return re.fullmatch(
        r"(?:blobs/[a-f0-9]{64}|observations/[a-f0-9-]{36}\.json|"
        r"runs/[A-Za-z0-9][A-Za-z0-9_-]{0,99}\.json)", name) is not None


def recovery_view(store: RunStore, fingerprint: str) -> dict:
    _require(store.recovery_depth < MAX_RECOVERY_DEPTH, "recovery nesting limit exceeded")
    raw = store.blobs.read(fingerprint)
    index = json.loads(raw)
    _fields(index, {"schema_version", "files"})
    _require(type(index["schema_version"]) is int and index["schema_version"] == 1,
             "invalid recovery version")
    _require(_encode(index) == raw, "noncanonical recovery index")
    _require(isinstance(index["files"], dict) and len(index["files"]) <= MAX_FILES,
             "recovery file count exceeded")
    with tempfile.TemporaryDirectory(prefix="filing-recovery-") as temporary:
        # Resolve only our freshly allocated temp root (macOS /var is an alias).
        # User-provided evidence roots still reject symlinks before resolving.
        root = Path(temporary).resolve()
        for name in ("blobs", "observations", "runs"):
            (root / name).mkdir()
        total = 0
        for name, digest in index["files"].items():
            _require(_allowed(name), "invalid recovery path")
            content = store.blobs.read(digest)
            total += len(content)
            _require(total <= MAX_TOTAL_BYTES, "recovery size limit exceeded")
            with (root / name).open("xb") as output:
                output.write(content)
        recovered = RunStore(root, read_only=True, _recovery_depth=store.recovery_depth + 1)
        runs = recovered.verify()
        _require(bool(runs), "empty recovery artifact")
        return recovered.query(runs[-1]["finalized_at"])


def recover(store: RunStore, artifact: Path, *, run_id: str, source_commit: str) -> dict:
    """Caller holds the same writer lock used by collect; source is read-only."""
    _require(not store.read_only, "read-only recovery destination")
    source_path = Path(artifact).absolute()
    _no_symlink(source_path)
    left, right = source_path.resolve(), store.root.resolve()
    _require(not left.is_relative_to(right) and not right.is_relative_to(left),
             "recovery paths overlap")
    source = RunStore(source_path, read_only=True)
    originals = source.verify()
    _require(bool(originals), "empty recovery artifact")
    current = store.verify()
    started = store.clock()
    _require(utc(originals[-1]["finalized_at"]) <= utc(started), "recovery clock reversal")
    if current:
        _require(utc(current[-1]["finalized_at"]) <= utc(started), "recovery clock reversal")
    incoming = source.query(originals[-1]["finalized_at"])
    existing = store.query(started)
    by_id = {item["observation_id"]: item for item in existing["observations"]}
    for item in incoming["observations"]:
        old = by_id.get(item["observation_id"])
        if old is not None:
            for key in ("blob_sha256", "url", "issuer_cik", "accession", "source_kind",
                        "requested_at", "received_at", "verified_at", "source_claims"):
                _require(old[key] == item[key], "conflicting recovered observation ID")
    files, total = {}, 0
    for directory in ("blobs", "observations", "runs"):
        for path in sorted((source.root / directory).iterdir()):
            _no_symlink(path)
            name = path.relative_to(source.root).as_posix()
            if path.name.startswith(".pending-"):
                continue
            _require(_allowed(name) and path.is_file(), "invalid recovery artifact file")
            _require(len(files) < MAX_FILES, "recovery file count exceeded")
            with path.open("rb") as handle:
                raw = handle.read(MAX_BYTES + 1)
            total += len(raw)
            _require(total <= MAX_TOTAL_BYTES, "recovery size limit exceeded")
            files[name] = store.blobs.put(raw)
    fingerprint = store.blobs.put(_encode({"schema_version": 1, "files": files}))
    recovery_view(store, fingerprint)
    # Retain the stricter existing circuit; a recovery must not clear a block.
    states = [run["manifest"]["circuit"] for run in (current[-1:] + originals[-1:])]
    until = [state["cooldown_until"] for state in states if state["cooldown_until"] is not None]
    circuit = {"consecutive_failures": max(state["consecutive_failures"] for state in states),
               "cooldown_until": max(until, key=utc) if until else None}
    manifest = {
        "schema_version": 1, "run_id": run_id, "source_commit": source_commit,
        "config_sha256": originals[-1]["manifest"]["config_sha256"],
        "started_at": started, "ended_at": store.clock(),
        "previous_run_sha256": current[-1]["sha256"] if current else None,
        "observations": [], "failures": [],
        "coverage": {"succeeded": 0, "failed": 0, "skipped": 0},
        "circuit": circuit, "recovery_sha256": fingerprint,
    }
    digest = store.publish(manifest, [])
    return {"run_id": run_id, "run_sha256": digest, "recovery_sha256": fingerprint,
            "recovered_observations": len(incoming["observations"]),
            "new_network_observations": 0}
