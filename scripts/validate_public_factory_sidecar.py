#!/usr/bin/env python3
"""Fail closed when a redacted public strategy-factory sidecar loses audit identity."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number}: JSONL row must be an object")
        rows.append(payload)
    return rows


def _required_unique(rows: list[dict[str, object]], key: str) -> set[str]:
    values: list[str] = []
    for index, row in enumerate(rows, 1):
        value = row.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"audit row {index} has no non-empty {key}")
        values.append(value)
    unique = set(values)
    if len(unique) != len(values):
        raise ValueError(f"audit {key} values are not unique: {len(unique)}/{len(values)}")
    return unique


def _research_families(rows: list[dict[str, object]], expected: int) -> set[str]:
    families = {
        str(row.get("family_id") or row.get("research_family_id") or "") for row in rows
    }
    if "" in families or len(families) != expected:
        raise ValueError(
            f"audit research family count mismatch: {len(families - {''})} != {expected}"
        )
    return families


def validate(
    strategy_path: Path,
    audit_path: Path,
    ledger_path: Path,
) -> dict[str, int]:
    strategy = _read_json(strategy_path)
    audit = _read_jsonl(audit_path)
    ledger = _read_jsonl(ledger_path)
    expected_rows = strategy.get("global_audit_trial_count")
    expected_families = strategy.get("program_research_family_count")
    if not isinstance(expected_rows, int) or expected_rows <= 0:
        raise ValueError("strategy global_audit_trial_count must be a positive integer")
    if not isinstance(expected_families, int) or expected_families <= 0:
        raise ValueError("strategy program_research_family_count must be a positive integer")
    if len(audit) != expected_rows:
        raise ValueError(f"audit row count mismatch: {len(audit)} != {expected_rows}")
    candidate_ids = _required_unique(audit, "candidate_id")
    fingerprints = _required_unique(audit, "strategy_fingerprint")
    families = _research_families(audit, expected_families)
    embedded_raw = strategy.get("audit_records")
    if not isinstance(embedded_raw, list) or any(
        not isinstance(row, dict) for row in embedded_raw
    ):
        raise ValueError("strategy audit_records must be a list of objects")
    embedded = [dict(row) for row in embedded_raw]
    if len(embedded) != expected_rows:
        raise ValueError(
            f"embedded audit row count mismatch: {len(embedded)} != {expected_rows}"
        )
    _required_unique(embedded, "candidate_id")
    _required_unique(embedded, "strategy_fingerprint")
    _research_families(embedded, expected_families)
    external_identity = {
        (row["candidate_id"], row["strategy_fingerprint"]) for row in audit
    }
    embedded_identity = {
        (row["candidate_id"], row["strategy_fingerprint"]) for row in embedded
    }
    if external_identity != embedded_identity:
        raise ValueError("external and embedded audit identities do not match")
    return {
        "audit_rows": len(audit),
        "unique_candidate_ids": len(candidate_ids),
        "unique_strategy_fingerprints": len(fingerprints),
        "research_families": len(families),
        "ledger_rows": len(ledger),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy-json", type=Path, required=True)
    parser.add_argument("--audit-catalog", type=Path, required=True)
    parser.add_argument("--trial-ledger", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = validate(args.strategy_json, args.audit_catalog, args.trial_ledger)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"public factory sidecar validation error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
