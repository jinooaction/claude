#!/usr/bin/env python3
"""Run spec 190 research with source replay before any holdout access."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from auto_invest.analytics.cost_aware_intraday import (
    load_contract,
    require_selected_development,
    run_confirmation,
    run_development,
    validate_seal,
    verify_development,
)
from auto_invest.analytics.intraday_paper_challenger import load_intraday_dataset

ROOT = Path(__file__).resolve().parents[1]


def read_bundle(directory: Path, stage: str) -> tuple[dict, bytes]:
    payload = json.loads((directory / "result.json").read_text())
    if not isinstance(payload, dict):
        raise ValueError("evidence root must be an object")
    ledger = (directory / "ledger.jsonl").read_bytes()
    validate_seal(payload, ledger, stage=stage)
    commit = payload["code_commit"]
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=ROOT, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "cat-file", "-e",
         f"{commit}:src/auto_invest/analytics/cost_aware_intraday.py"],
        cwd=ROOT, check=True, capture_output=True,
    )
    return payload, ledger


def verified_development_inputs(args, contract, prior, *, require_selected: bool):
    if not all((args.development, args.development_bars_dir, args.development_manifest)):
        raise ValueError("development evidence and original inputs are required")
    payload, ledger = read_bundle(args.development, "development")
    if require_selected:
        require_selected_development(payload)
    development = load_intraday_dataset(
        args.development_bars_dir, args.development_manifest, prior,
    )
    verified = verify_development(payload, ledger, development, contract, prior)
    if require_selected:
        require_selected_development(verified)
    return verified, development


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("develop", "confirm"))
    parser.add_argument("--bars-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, default=ROOT /
                        "specs/190-cost-aware-intraday/contracts/preregistration.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--development", type=Path)
    parser.add_argument("--development-bars-dir", type=Path)
    parser.add_argument("--development-manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output_dir.exists():
            raise ValueError("output directory already exists; existing evidence is immutable")
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("cannot bind research to a code commit")
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain", "--", "src", "scripts",
             "specs/190-cost-aware-intraday/contracts"],
            cwd=ROOT, text=True,
        )
        if dirty:
            raise ValueError("commit research code and preregistration before evaluation")
        contract, prior = load_contract(args.preregistration, ROOT /
                                       "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")
        if args.stage == "confirm":
            verified, development = verified_development_inputs(
                args, contract, prior, require_selected=True,
            )
            # This is intentionally after source replay and selection validation.
            dataset = load_intraday_dataset(args.bars_dir, args.manifest, prior)
            result, ledger = run_confirmation(
                dataset, development, verified, contract, prior, code_commit=commit,
            )
        else:
            if any((args.development, args.development_bars_dir, args.development_manifest)):
                raise ValueError("development stage does not accept prior selection inputs")
            dataset = load_intraday_dataset(args.bars_dir, args.manifest, prior)
            result, ledger = run_development(dataset, contract, prior, code_commit=commit)
        args.output_dir.mkdir(parents=True, exist_ok=False)
        with (args.output_dir / "ledger.jsonl").open("xb") as handle:
            handle.write(ledger)
        with (args.output_dir / "result.json").open("x") as handle:
            json.dump(result, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
        print(json.dumps({"verdict": result["verdict"],
                          "selected_candidate_id": result["selected_candidate_id"],
                          "content_sha256": result["content_sha256"]}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"cost-aware research error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
