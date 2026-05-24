"""auto-tuner-report.json 직렬화 (스펙 005, FR-A07, contracts/tune-cli.md).

`TunerRunResult` → 기계 판독 JSON. `{output_root}/{session_date}/auto-tuner-report.json`
에 원자적으로 쓴다(reports/daily.py 경로 규칙 미러).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from auto_invest.tuner.models import Classification, TunerRunResult

SCHEMA_VERSION = "1.0"


def _classification_to_dict(c: Classification) -> dict:
    cand = c.candidate
    return {
        "candidate_id": cand.candidate_id,
        "detection_rule": cand.detection_rule,
        "kpi_name": cand.kpi_name,
        "observed_value": cand.observed_value,
        "observed_tier": cand.observed_tier,
        "window": cand.window,
        "authority_tier": c.tier,
        "kernel_groups": list(c.kernel_groups),
        "classification_reason": c.reason,
        "proposed": {
            "kind": cand.proposed.kind,
            "target_paths": list(cand.proposed.target_paths),
            "config_key": cand.proposed.config_key,
            "old_value": cand.proposed.old_value,
            "new_value": cand.proposed.new_value,
        },
        "rationale": cand.rationale,
        "measurement_sample": cand.measurement_sample,
    }


def to_dict(result: TunerRunResult) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_date": result.session_date,
        "generated_at_utc": result.generated_at_utc,
        "mode": result.mode,
        "candidates": [_classification_to_dict(c) for c in result.candidates],
        "applied": [
            {
                "candidate_id": a.candidate_id,
                "config_key": a.config_key,
                "old_value": a.old_value,
                "new_value": a.new_value,
                "audit_seq": a.audit_seq,
            }
            for a in result.applied
        ],
        "canary_entered": [_classification_to_dict(c) for c in result.canary_entered],
        "awaiting_human_merge": [
            _classification_to_dict(c) for c in result.awaiting_human_merge
        ],
        "skipped": [[cid, reason] for cid, reason in result.skipped],
    }


def to_json(result: TunerRunResult) -> str:
    return json.dumps(to_dict(result), ensure_ascii=False, indent=2, sort_keys=False)


def write_report(result: TunerRunResult, *, output_root: Path) -> Path:
    """`{output_root}/{session_date}/auto-tuner-report.json` 원자적 작성. 경로 반환."""
    out_dir = output_root / result.session_date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "auto-tuner-report.json"
    payload = to_json(result) + "\n"
    fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=".tuner-report-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, out_path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return out_path


__all__ = ["SCHEMA_VERSION", "to_dict", "to_json", "write_report"]
