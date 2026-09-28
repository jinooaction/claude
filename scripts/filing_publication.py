"""Prepare an append-only filing tree; Git publication belongs to the remote job."""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from auto_invest.analytics.filing_observations import (
    MAX_BYTES,
    Observation,
    RunStore,
    _load,
    _no_symlink,
    _publish_file,
    _require,
)
from auto_invest.analytics.filing_recovery import _allowed

DELTA_MAX_BYTES = 64 * 1024 * 1024
STORE_MAX_BYTES = 512 * 1024 * 1024
STORE_MAX_FILES = 100_000
RUN_FILE_RESERVE = 32


def check_capacity(source: Path) -> dict:
    """Reserve one bounded run before any HTTP request; never prune old evidence."""
    _no_symlink(source)
    items = inventory(source) if source.exists() else {}
    size = sum((source / name).stat().st_size for name in items)
    _require(size + DELTA_MAX_BYTES <= STORE_MAX_BYTES
             and len(items) + RUN_FILE_RESERVE <= STORE_MAX_FILES,
             "retained store capacity exhausted")
    return {"capacity_available": True, "retained_bytes": size,
            "retained_files": len(items), "maximum_bytes": STORE_MAX_BYTES,
            "reserved_bytes": DELTA_MAX_BYTES}


def inventory_digest(items: dict[str, str]) -> str:
    raw = json.dumps(items, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def pack_delta(source: Path, base: Path | None, destination: Path) -> dict:
    """Retain only additions, bound to the exact verified base inventory."""
    incoming = inventory(source)
    previous = inventory(base) if base is not None else {}
    _require(all(incoming.get(name) == digest for name, digest in previous.items()),
             "delta would change or delete history")
    _no_symlink(destination)
    _require(not destination.exists(), "delta output already exists")
    for root in (source, base):
        if root is not None:
            _require(not destination.resolve().is_relative_to(root.resolve()),
                     "delta output overlaps evidence")
    names = sorted(incoming.keys() - previous.keys())
    _require(sum((source / name).stat().st_size for name in names) <= DELTA_MAX_BYTES,
             "delta size exceeded")
    destination.mkdir(parents=True)
    files = {}
    total = 0
    for name in names:
        _no_symlink(source / name)
        with (source / name).open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        total += len(raw)
        _require(len(raw) <= MAX_BYTES and total <= DELTA_MAX_BYTES, "delta size exceeded")
        _require(hashlib.sha256(raw).hexdigest() == incoming[name], "source changed during packing")
        path = destination / "files" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        _publish_file(path, raw)
        files[name] = incoming[name]
    (destination / "files").mkdir(exist_ok=True)
    manifest = {"schema_version": 1, "base_sha256": inventory_digest(previous),
                "target_sha256": inventory_digest(incoming), "files": files}
    _publish_file(destination / "delta.json",
                  json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
    return {"added_files": len(files), "delta_bytes": total,
            "base_sha256": manifest["base_sha256"], "target_sha256": manifest["target_sha256"]}


def apply_delta(source: Path, destination: Path) -> dict:
    """Validate the complete reconstructed store before appending any evidence."""
    _no_symlink(source)
    _no_symlink(destination)
    _require(not source.resolve().is_relative_to(destination.resolve())
             and not destination.resolve().is_relative_to(source.resolve()), "delta paths overlap")
    _require({p.name for p in source.iterdir()} in ({"delta.json", "files"}, {"delta.json"}),
             "unexpected delta entry")
    manifest = _load(source / "delta.json")[0]
    _require(set(manifest) == {"schema_version", "base_sha256", "target_sha256", "files"}
             and type(manifest["schema_version"]) is int and manifest["schema_version"] == 1,
             "invalid delta manifest")
    files = manifest["files"]
    _require(isinstance(files, dict) and all(isinstance(n, str) and _allowed(n) for n in files),
             "invalid delta paths")
    for digest in [manifest["base_sha256"], manifest["target_sha256"], *files.values()]:
        _require(isinstance(digest, str) and len(digest) == 64
                 and all(c in "0123456789abcdef" for c in digest), "invalid delta digest")
    root = source / "files"
    _no_symlink(root)
    _require(root.is_dir() or (not files and not root.exists()), "missing delta files")
    actual = set()
    total = 0
    for path in root.rglob("*"):
        _no_symlink(path)
        name = path.relative_to(root).as_posix()
        if path.is_dir():
            _require(name in {"blobs", "observations", "runs"}, "unexpected delta directory")
            continue
        _require(path.is_file() and name in files, "unexpected delta file")
        with path.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        total += len(raw)
        _require(len(raw) <= MAX_BYTES and total <= DELTA_MAX_BYTES, "delta size exceeded")
        _require(hashlib.sha256(raw).hexdigest() == files[name], "delta digest mismatch")
        actual.add(name)
    _require(actual == set(files), "missing delta file")
    previous = inventory(destination) if destination.exists() else {}
    if inventory_digest(previous) == manifest["target_sha256"]:
        _require(all(previous.get(n) == d for n, d in files.items()), "replayed delta mismatch")
        return {"added_files": 0, "already_applied": True}
    _require(inventory_digest(previous) == manifest["base_sha256"], "delta base mismatch")
    _require(not (set(files) & set(previous)), "delta replaces history")
    with tempfile.TemporaryDirectory(prefix="filing-delta-") as temporary:
        # Resolve only our own newly-created temporary directory (macOS /var alias).
        assembled = Path(temporary).resolve() / "store"
        if destination.exists():
            stage(destination, assembled)
        else:
            RunStore(assembled)
        for name in sorted(files):
            _no_symlink(root / name)
            with (root / name).open("rb") as handle:
                raw = handle.read(MAX_BYTES + 1)
            _require(len(raw) <= MAX_BYTES and hashlib.sha256(raw).hexdigest() == files[name],
                     "delta changed during application")
            _publish_file(assembled / name, raw)
        _require(inventory_digest(inventory(assembled)) == manifest["target_sha256"],
                 "delta target mismatch")
        return stage(assembled, destination)


def inventory(root: Path) -> dict[str, str]:
    _no_symlink(root)
    for path in root.iterdir():
        _no_symlink(path)
        _require(path.name in {"blobs", "observations", "runs", ".collector.lock"},
                 "unexpected store entry")
    store = RunStore(root, read_only=True)
    store.verify()
    result = {}
    for directory in ("blobs", "observations", "runs"):
        for path in (root / directory).iterdir():
            _no_symlink(path)
            name = path.relative_to(root).as_posix()
            _require(_allowed(name) and path.is_file(), "unexpected evidence path")
            with path.open("rb") as source:
                raw = source.read(MAX_BYTES + 1)
            _require(len(raw) <= MAX_BYTES, "publication file size exceeded")
            digest = hashlib.sha256(raw).hexdigest()
            if directory == "blobs":
                _require(digest == path.name, "blob digest mismatch")
            elif directory == "observations":
                item = Observation.from_dict(_load(path)[0])
                _require(path.name == f"{item.observation_id}.json", "receipt filename mismatch")
            result[name] = digest
    return result


def restore_transport_layout(root: Path) -> None:
    """Restore only structural directories omitted by Git/artifact transport.

    Receipts, blobs and run files are never reconstructed. The usual complete
    verification still rejects missing referenced bytes or altered history.
    """
    _no_symlink(root)
    _require(root.is_dir(), "missing store root")
    for path in root.iterdir():
        _no_symlink(path)
        _require(path.name in {"blobs", "observations", "runs", ".collector.lock"},
                 "unexpected store entry")
    directories = [root / name for name in ("blobs", "observations", "runs")]
    for path in directories:
        _no_symlink(path)
        _require(not path.exists() or path.is_dir(), "invalid evidence directory")
    _require((root / "runs").is_dir(), "missing completed run directory")
    for path in directories:
        path.mkdir(exist_ok=True)


def stage(source: Path, destination: Path, *, restore_layout: bool = False) -> dict:
    source, destination = Path(source).absolute(), Path(destination).absolute()
    _no_symlink(source)
    _no_symlink(destination)
    left, right = source.resolve(), destination.resolve()
    _require(not left.is_relative_to(right) and not right.is_relative_to(left),
             "publication paths overlap")
    if restore_layout:
        restore_transport_layout(source)
    incoming = inventory(source)
    if restore_layout and destination.exists():
        restore_transport_layout(destination)
    previous = inventory(destination) if destination.exists() else {}
    _require(all(incoming.get(name) == digest for name, digest in previous.items()),
             "publication would change or delete history")
    target = RunStore(destination)
    for name in sorted(incoming.keys() - previous.keys()):
        # Re-read and compare before each copy in case source changed after inspection.
        _no_symlink(source / name)
        with (source / name).open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        _require(hashlib.sha256(raw).hexdigest() == incoming[name], "source changed during staging")
        _publish_file(destination / name, raw)
    _require(inventory(destination) == incoming, "staged inventory mismatch")
    runs = target.verify()
    return {"added_files": len(incoming.keys() - previous.keys()),
            "completed_runs": len(runs), "head_sha256": runs[-1]["sha256"] if runs else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--mode", choices=("stage", "pack-delta", "apply-delta", "capacity"),
                        default="stage")
    parser.add_argument("--base", type=Path, help="Verified previous store for delta packing")
    parser.add_argument("--restore-layout", action="store_true",
                        help="Recreate structural empty directories lost during transport only")
    args = parser.parse_args()
    try:
        _require(args.base is None or args.mode == "pack-delta", "base requires packing")
        _require((args.destination is None) == (args.mode == "capacity"),
                 "destination required except for capacity check")
        _require(not args.restore_layout or args.mode in {"stage", "apply-delta"},
                 "layout requires staging or delta application")
        if args.mode == "capacity":
            result = check_capacity(args.source)
        elif args.mode == "pack-delta":
            result = pack_delta(args.source, args.base, args.destination)
        elif args.mode == "apply-delta":
            if args.restore_layout and args.destination.exists():
                restore_transport_layout(args.destination)
            result = apply_delta(args.source, args.destination)
        else:
            result = stage(args.source, args.destination, restore_layout=args.restore_layout)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, TypeError, OSError):
        print("Filing publication refused: existing history must remain unchanged.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
