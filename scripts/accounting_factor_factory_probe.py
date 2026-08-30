#!/usr/bin/env python3
"""Run the no-order preregistered accounting-factor research factory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.accounting_factor_factory import (
    ARCHIVE_URL,
    CURRENT_URL,
    build_accounting_factor_bundle,
    parse_fama_french_five_factor_zip,
    render_accounting_factor_markdown,
    run_accounting_factor_factory,
)

DEFAULT_SCHEMA = Path(
    "specs/174-accounting-cross-sectional-factors/contracts/"
    "accounting-factor-result.schema.json"
)


def _read_bytes(path: Path | None, url: str) -> bytes:
    if path is not None:
        return path.read_bytes()
    last_error: Exception | None = None
    for attempt in range(3):
        request = urllib.request.Request(  # noqa: S310
            url,
            headers={"User-Agent": "auto-invest-research/1.0 (public factor validation)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
                return response.read()
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
    raise OSError(f"official factor download failed after 3 attempts: {url}") from last_error


def _object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _matches_type(value: object, expected: str) -> bool:
    return {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "null": value is None,
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
    }.get(expected, True)


def _validate_schema_node(value: object, schema: Mapping[str, object], path: str) -> None:
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _matches_type(value, expected_type):
        raise ValueError(f"result schema type mismatch at {path}: expected {expected_type}")
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"result schema constant mismatch at {path}")
    choices = schema.get("enum")
    if isinstance(choices, list) and value not in choices:
        raise ValueError(f"result schema enum mismatch at {path}")
    if (
        isinstance(value, str)
        and isinstance(schema.get("minLength"), int)
        and len(value) < int(schema["minLength"])
    ):
        raise ValueError(f"result schema string too short at {path}")
    if (
        isinstance(value, list)
        and isinstance(schema.get("minItems"), int)
        and len(value) < int(schema["minItems"])
    ):
        raise ValueError(f"result schema array too short at {path}")
    if isinstance(value, Mapping):
        required = schema.get("required")
        if isinstance(required, list):
            missing = [key for key in required if key not in value]
            if missing:
                raise ValueError(f"result schema missing keys at {path}: {missing}")
        properties = schema.get("properties")
        if isinstance(properties, Mapping):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, Mapping):
                    _validate_schema_node(value[key], child_schema, f"{path}.{key}")


def _validate_schema(payload: Mapping[str, object], schema_payload: Mapping[str, object]) -> None:
    _validate_schema_node(payload, schema_payload, "$")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-file", type=Path)
    parser.add_argument("--current-file", type=Path)
    parser.add_argument("--prior-factory-json", type=Path, required=True)
    parser.add_argument("--calibration-json", type=Path, required=True)
    parser.add_argument("--result-schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    timestamp = args.timestamp_utc or datetime.now(UTC).isoformat()
    try:
        current_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
        archive_raw = _read_bytes(args.archive_file, ARCHIVE_URL)
        current_raw = _read_bytes(args.current_file, CURRENT_URL)
        bundle = build_accounting_factor_bundle(
            parse_fama_french_five_factor_zip(archive_raw),
            parse_fama_french_five_factor_zip(current_raw),
            archive_digest="sha256:" + hashlib.sha256(archive_raw).hexdigest(),
            current_digest="sha256:" + hashlib.sha256(current_raw).hexdigest(),
            current_date=current_date,
        )
        prior = _object(args.prior_factory_json)
        prior_rows = prior.get("audit_records")
        if not isinstance(prior_rows, list):
            raise ValueError("prior factory audit_records are missing")
        payload = run_accounting_factor_factory(
            bundle=bundle,
            prior_audit_records=prior_rows,
            calibration=_object(args.calibration_json),
            code_commit=args.code_commit,
            generated_at=timestamp,
        )
        _validate_schema(payload, _object(args.result_schema))
    except (KeyError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Accounting factor factory input error: {exc}", file=sys.stderr)
        return 2

    summary = render_accounting_factor_markdown(payload)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.summary_out is not None:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(summary + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False) if args.json else summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
