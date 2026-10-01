"""Verify a fixed public-issuer store or unpack its bounded SSH archive."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tarfile
from pathlib import Path

from filing_publication import (
    STORE_MAX_BYTES,
    STORE_MAX_FILES,
    inventory,
    inventory_digest,
)

from auto_invest.analytics.filing_observations import MAX_BYTES, RunStore

FILE_NAME = re.compile(
    r"(?:blobs/[0-9a-f]{64}|observations/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}"
    r"-[0-9a-f]{12}\.json|runs/[A-Za-z0-9][A-Za-z0-9_-]{0,99}\.json)"
)
DIRECTORIES = {"blobs", "observations", "runs"}


def inspect(source: Path) -> dict:
    files = inventory(source)
    store = RunStore(source, read_only=True)
    runs = store.verify()
    if not runs:
        raise ValueError("server store has no completed run")
    if any(re.fullmatch(r"server-[0-9a-f]{32}", run["manifest"]["run_id"]) is None
           for run in runs):
        raise ValueError("snapshot contains a different run identity")
    if any("recovery_sha256" in run["manifest"] for run in runs):
        raise ValueError("snapshot cannot splice a recovered source")
    if any(item.source_kind not in {"issuer_listing", "issuer_primary"}
           for run in runs for item in store._receipts(run["manifest"])):
        raise ValueError("snapshot contains a different source")
    if any(failure.get("source_kind") not in {"issuer_listing", "issuer_primary"}
           for run in runs for failure in run["manifest"]["failures"]):
        raise ValueError("snapshot contains a different failure source")
    return {"completed_runs": len(runs), "head_sha256": runs[-1]["sha256"],
            "inventory_sha256": inventory_digest(files), "files": len(files),
            "bytes": sum((source / name).stat().st_size for name in files)}


def unpack(archive: Path, destination: Path) -> dict:
    if destination.exists() or archive.stat().st_size > STORE_MAX_BYTES:
        raise ValueError("snapshot destination or archive limit")
    destination.mkdir(parents=True)
    seen = set()
    total = 0
    with archive.open("rb") as source, tarfile.open(fileobj=source, mode="r:gz") as bundle:
        for member in bundle:
            name = member.name.removeprefix("./").rstrip("/")
            if member.isdir() and name in DIRECTORIES:
                (destination / name).mkdir(exist_ok=True)
                continue
            if not member.isfile() or FILE_NAME.fullmatch(name) is None or name in seen:
                raise ValueError("unexpected snapshot entry")
            if member.size > MAX_BYTES or len(seen) >= STORE_MAX_FILES:
                raise ValueError("snapshot file limit")
            total += member.size
            if total > STORE_MAX_BYTES:
                raise ValueError("snapshot size limit")
            seen.add(name)
            reader = bundle.extractfile(member)
            if reader is None:
                raise ValueError("missing snapshot member")
            raw = reader.read(MAX_BYTES + 1)
            if len(raw) != member.size:
                raise ValueError("truncated snapshot member")
            target = destination / name
            target.parent.mkdir(exist_ok=True)
            with target.open("xb") as output:
                output.write(raw)
    return inspect(destination)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    source = subcommands.add_parser("inspect-store")
    source.add_argument("--source", required=True, type=Path)
    extraction = subcommands.add_parser("unpack")
    extraction.add_argument("--archive", required=True, type=Path)
    extraction.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = inspect(args.source) if args.command == "inspect-store" else unpack(
            args.archive, args.destination)
    except (OSError, ValueError, tarfile.TarError):
        print("Issuer snapshot refused: malformed or unverified source.", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
