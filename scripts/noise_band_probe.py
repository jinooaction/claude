#!/usr/bin/env python3
"""Run or verify frozen noise-band development research without reading holdout prices."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from auto_invest.analytics import noise_band_intraday as research

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "specs/192-noise-band-research/contracts/preregistration.json"
PRIOR = ROOT / "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"


def clean_commit() -> str:
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--", "src", "scripts", str(CONTRACT.parent)],
        cwd=ROOT, text=True,
    )
    if dirty:
        raise ValueError("commit code and contract before research or verification")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def read_bundle(directory: Path) -> tuple[dict, bytes]:
    payload = json.loads((directory / "result.json").read_text())
    if not isinstance(payload, dict):
        raise ValueError("evidence root must be an object")
    ledger = (directory / "ledger.jsonl").read_bytes()
    research.validate_seal(payload, ledger)
    commit = payload["code_commit"]
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"],
                   cwd=ROOT, check=True, capture_output=True)
    subprocess.run(["git", "cat-file", "-e",
                    f"{commit}:src/auto_invest/analytics/noise_band_intraday.py"],
                   cwd=ROOT, check=True, capture_output=True)
    return payload, ledger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("develop", "verify"))
    parser.add_argument("--bars-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.stage == "develop":
            if args.output_dir is None or args.evidence is not None:
                raise ValueError("develop requires only --output-dir")
            if args.output_dir.exists():
                raise ValueError("output already exists; existing evidence is immutable")
        elif args.evidence is None or args.output_dir is not None:
            raise ValueError("verify requires only --evidence")
        commit = clean_commit()
        contract, prior = research.load_contract(CONTRACT, PRIOR)
        if args.stage == "verify":
            payload, ledger = read_bundle(args.evidence)
        dataset = research.load_development(args.bars_dir, args.manifest, prior)
        if args.stage == "verify":
            result = research.verify_development(payload, ledger, dataset, contract, prior)
        else:
            result, ledger = research.run_development(dataset, contract, prior, code_commit=commit)
            args.output_dir.mkdir(parents=True, exist_ok=False)
            with (args.output_dir / "ledger.jsonl").open("xb") as handle:
                handle.write(ledger)
            with (args.output_dir / "result.json").open("x") as handle:
                json.dump(result, handle, sort_keys=True, indent=2, allow_nan=False)
                handle.write("\n")
        print(json.dumps({"valid": True, "verdict": result["verdict"],
                          "selected_candidate_id": result["selected_candidate_id"],
                          "capital_eligible": False, "ledger_row_count": result["ledger_row_count"],
                          "content_sha256": result["content_sha256"]}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"valid": False, "capital_eligible": False, "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())

