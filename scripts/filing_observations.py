"""Bounded public filing collection and offline evidence commands."""

import argparse
import fcntl
import json
import os
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import httpx

from auto_invest.analytics.filing_observations import Observation, RunStore
from auto_invest.analytics.filing_recovery import recover
from auto_invest.market_data.filing_collector import Collector, Scope, _json
from auto_invest.market_data.issuer_filings import USER_AGENT, IssuerCollector, IssuerScope


def write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as target:
        json.dump(value, target, indent=2, sort_keys=True, allow_nan=False)
        target.write("\n")


def external_output(store: RunStore, path: Path) -> None:
    if path.resolve().is_relative_to(store.root.resolve()):
        raise ValueError("output cannot modify the evidence store")


def export_observation(store: RunStore, identity: str, output: Path) -> dict:
    external_output(store, output)
    selected = None
    runs = store.verify()
    if runs:
        for item in store.query(runs[-1]["finalized_at"])["observations"]:
            if item["observation_id"] == identity:
                receipt = Observation.from_dict({field.name: item[field.name]
                                                 for field in fields(Observation)})
                run = next(run for run in runs if run["manifest"]["run_id"] == item["run_id"])
                selected = receipt, run
    if selected is None or selected[0].source_kind not in {"primary", "issuer_primary"}:
        raise ValueError("completed primary observation required")
    receipt, run = selected
    raw = store.blobs.read(receipt.blob_sha256)
    metadata = {
        "schema_version": 1, "observation": receipt.to_dict(),
        "run_sha256": run["sha256"], "collector_available_at": run["finalized_at"],
        "reviewed_event": False, "source_file": "source.bin",
        "review_instruction": "Use a new explicit document ID and current review time in spec195.",
    }
    output.mkdir(exist_ok=False)
    with (output / "source.bin").open("xb") as target:
        target.write(raw)
    # Written last so a partially written export has no completion metadata.
    write_json(output / "metadata.json", metadata)
    return {"exported": True, "observation_id": identity, "reviewed_event": False}


def source_commit() -> str:
    repository = Path(__file__).resolve().parents[1]
    subprocess.run(["git", "-C", str(repository), "diff", "--quiet", "HEAD"],
                   check=True, capture_output=True, timeout=10)
    return subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True, timeout=10).strip()


def recover_command(args) -> dict:
    commit = source_commit()
    store = RunStore(args.store)
    descriptor = os.open(store.root / ".collector.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                         0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return recover(store, args.artifact, run_id=args.run_id, source_commit=commit)
    finally:
        os.close(descriptor)


def collect(args) -> tuple[dict, int]:
    issuer = args.command == "collect-issuer"
    user_agent = USER_AGENT if issuer else os.environ.get("SEC_USER_AGENT", "")
    collector_class = IssuerCollector if issuer else Collector
    if not collector_class.valid_agent(user_agent):
        raise ValueError("SEC_USER_AGENT identification required")
    with args.config.open("rb") as source:
        raw = source.read(65537)
    if len(raw) > 65536:
        raise ValueError("scope file size limit exceeded")
    scope = (IssuerScope if issuer else Scope).from_dict(_json(raw))
    commit = source_commit()
    store = RunStore(args.store)
    # The lock spans initial chain verification, collection, and publication.
    # Keep the inode: unlinking a flock file can split concurrent writers.
    descriptor = os.open(store.root / ".collector.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                         0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with httpx.Client(trust_env=False, follow_redirects=False) as client:
            result = collector_class(store, scope, user_agent=user_agent, client=client).collect(
                run_id=args.run_id, source_commit=commit)
    finally:
        os.close(descriptor)
    return result, 0 if result["complete"] else 3


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("collect", "collect-issuer", "verify", "query", "export", "recover"):
        command = commands.add_parser(name)
        command.add_argument("--store", type=Path, required=True)
        if name in {"collect", "collect-issuer"}:
            command.add_argument("--config", type=Path, required=True)
            command.add_argument("--run-id", required=True)
        elif name == "recover":
            command.add_argument("--artifact", type=Path, required=True)
            command.add_argument("--run-id", required=True)
        elif name == "query":
            command.add_argument("--as-of", required=True)
            command.add_argument("--output", type=Path, required=True)
        elif name == "export":
            command.add_argument("--observation", required=True)
            command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        status = 0
        if args.command in {"collect", "collect-issuer"}:
            result, status = collect(args)
        elif args.command == "recover":
            result = recover_command(args)
        else:
            store = RunStore(args.store, read_only=True)
            if args.command == "verify":
                runs = store.verify()
                result = {"verified": True, "completed_runs": len(runs),
                          "head_sha256": runs[-1]["sha256"] if runs else None}
            elif args.command == "query":
                external_output(store, args.output)
                query = store.query(args.as_of)
                write_json(args.output, query)
                result = {"written": True, "observations": len(query["observations"]),
                          "completed_runs": len(query["runs"])}
            else:
                result = export_observation(store, args.observation, args.output)
        print(json.dumps(result, sort_keys=True))
        return status
    except (ValueError, TypeError, OSError, subprocess.SubprocessError):
        # Neither arbitrary source bytes, exception strings nor request headers
        # belong in public logs. A failed store cannot claim a persisted run.
        print("Filing operation refused: no successful result asserted.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
