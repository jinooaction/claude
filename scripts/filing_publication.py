"""Prepare an append-only filing tree; Git publication belongs to the remote job."""

import argparse
import hashlib
import json
import sys
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


def stage(source: Path, destination: Path) -> dict:
    source, destination = Path(source).absolute(), Path(destination).absolute()
    _no_symlink(source)
    _no_symlink(destination)
    left, right = source.resolve(), destination.resolve()
    _require(not left.is_relative_to(right) and not right.is_relative_to(left),
             "publication paths overlap")
    incoming = inventory(source)
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
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(stage(args.source, args.destination), sort_keys=True))
        return 0
    except (ValueError, TypeError, OSError):
        print("Filing publication refused: existing history must remain unchanged.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
