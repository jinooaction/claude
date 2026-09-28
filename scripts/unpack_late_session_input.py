#!/usr/bin/env python3
"""Restore the attributed, pre-2022 development snapshot without accessing holdout data."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from auto_invest.analytics.late_session_intraday import MANIFEST_SHA256

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "research-fixtures/198"
SYMBOLS = ("SPY", "QQQ", "IWM", "TLT", "GLD")
MAX_CSV_BYTES = 10 * 1024 * 1024


def unpack(source: Path, output: Path) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError("output already exists; refusing to overwrite")
    raw = (source / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("development manifest fingerprint mismatch")
    manifest = json.loads(raw)
    # Authenticate and bound every payload before creating any output.
    payloads = {}
    for symbol in SYMBOLS:
        with gzip.open(source / f"{symbol}.csv.gz", "rb") as handle:
            payload = handle.read(MAX_CSV_BYTES + 1)
        if len(payload) > MAX_CSV_BYTES:
            raise ValueError("development CSV exceeds size bound")
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        if digest != manifest["files"][symbol]["sha256"]:
            raise ValueError(f"development CSV fingerprint mismatch: {symbol}")
        payloads[symbol] = payload
    output.mkdir(parents=True, exist_ok=False)
    for symbol, payload in payloads.items():
        with (output / f"{symbol}.csv").open("xb") as handle:
            handle.write(payload)
    with (output / "manifest.json").open("xb") as handle:
        handle.write(raw)
    return {"valid": True, "manifest_sha256": MANIFEST_SHA256,
            "symbols": list(SYMBOLS), "holdout_included": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = unpack(FIXTURE, args.output_dir)
    except (OSError, EOFError, ValueError, KeyError) as exc:
        print(json.dumps({"valid": False, "reason": str(exc)}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
