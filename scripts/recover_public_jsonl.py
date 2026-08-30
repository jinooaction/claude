#!/usr/bin/env python3
"""Validate public sidecar JSONL and recover known legacy redaction damage."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

KNOWN_LEGACY_MARKER = "[REDACTED_ACCOUNT]"
KNOWN_LEGACY_NUMERIC_DAMAGE = re.compile(
    r"-?\d+\.\[REDACTED_ACCOUNT\](?=\s*[,}\]])"
)
STRATEGY_FINGERPRINT = re.compile(r"^sha256:([0-9a-f]{64})$")


def _repair_legacy_candidate_identity(payload: dict[str, object], line_number: int) -> bool:
    candidate_id = payload.get("candidate_id")
    if not isinstance(candidate_id, str) or KNOWN_LEGACY_MARKER not in candidate_id:
        return False
    strategy_fingerprint = payload.get("strategy_fingerprint")
    match = (
        STRATEGY_FINGERPRINT.fullmatch(strategy_fingerprint)
        if isinstance(strategy_fingerprint, str)
        else None
    )
    if match is None:
        raise ValueError(
            "legacy-redacted candidate_id requires a valid strategy_fingerprint "
            f"at line {line_number}"
        )
    payload["candidate_id"] = f"legacy-redacted-candidate-{match.group(1)[:20]}"
    return True


def recover_jsonl(
    source: Path,
    destination: Path,
    *,
    allow_known_redaction_drop: bool,
) -> dict[str, int]:
    valid: list[str] = []
    dropped = 0
    repaired_identities = 0
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            if (
                allow_known_redaction_drop
                and KNOWN_LEGACY_MARKER in line
                and KNOWN_LEGACY_NUMERIC_DAMAGE.search(line) is not None
            ):
                dropped += 1
                continue
            raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"JSONL line {line_number} must contain an object")
        if _repair_legacy_candidate_identity(payload, line_number):
            repaired_identities += 1
        valid.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            if valid:
                handle.write("\n".join(valid) + "\n")
        os.replace(temporary_name, destination)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return {
        "valid_lines": len(valid),
        "dropped_known_redaction_lines": dropped,
        "repaired_redacted_candidate_ids": repaired_identities,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-known-redaction-drop", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = recover_jsonl(
            args.input,
            args.output,
            allow_known_redaction_drop=args.allow_known_redaction_drop,
        )
    except (OSError, ValueError) as exc:
        print(f"public JSONL recovery error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
