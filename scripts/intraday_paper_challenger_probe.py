#!/usr/bin/env python3
"""Run the frozen, broker-free spec 177 intraday paper research batch."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.intraday_paper_challenger import (
    DatasetContractError,
    PreregistrationContractError,
    load_intraday_dataset,
    load_preregistration,
    render_intraday_markdown,
    run_intraday_paper_challenger,
)
from auto_invest.analytics.intraday_paper_challenger_evidence import (
    assess_intraday_evidence,
)

DEFAULT_PREREGISTRATION = Path(
    "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"
)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--ledger-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    generated_at = args.timestamp_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        preregistration_bytes = args.preregistration.read_bytes()
        preregistration = load_preregistration(args.preregistration)
        dataset = load_intraday_dataset(args.bars_dir, args.manifest, preregistration)
        payload, ledger = run_intraday_paper_challenger(
            dataset,
            preregistration,
            preregistration_bytes=preregistration_bytes,
            code_commit=args.code_commit,
            generated_at_utc=generated_at,
        )
        assessment = assess_intraday_evidence(
            payload,
            preregistration,
            preregistration_bytes=preregistration_bytes,
            ledger_bytes=ledger,
        )
        if not assessment.valid:
            raise ValueError(f"independent evidence validation failed: {assessment.reasons}")
        rendered_json = (
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
        summary = (render_intraday_markdown(payload) + "\n").encode("utf-8")
        _atomic_write(args.ledger_out, ledger)
        _atomic_write(args.json_out, rendered_json)
        _atomic_write(args.summary_out, summary)
    except (
        DatasetContractError,
        PreregistrationContractError,
        OSError,
        ValueError,
    ) as exc:
        print(f"intraday paper input/evidence error: {exc}", file=sys.stderr)
        return 2
    print(rendered_json.decode("utf-8") if args.json else summary.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
