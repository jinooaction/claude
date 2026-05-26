"""스펙 005 — auto-tuner-report 직렬화."""

from __future__ import annotations

import json
from pathlib import Path

from auto_invest.tuner.models import (
    AppliedChange,
    CandidateChange,
    Classification,
    ProposedChange,
    TunerRunResult,
)
from auto_invest.tuner.report import to_dict, write_report


def _result(mode: str = "apply") -> TunerRunResult:
    cand = CandidateChange(
        candidate_id="threshold_tighten:latency_p95_ms",
        detection_rule="threshold_tighten",
        kpi_name="latency_p95_ms",
        observed_value="1400",
        observed_tier="B",
        window="30d",
        proposed=ProposedChange(
            kind="threshold_tighten",
            target_paths=("config/llm_kpi_thresholds.toml",),
            config_key="latency_p95_ms.tier_b",
            old_value="2000",
            new_value="1760",
        ),
        rationale="stable B",
        measurement_sample=42,
    )
    cls = Classification(candidate=cand, tier="L1", kernel_groups=(), reason="L1")
    applied = AppliedChange(
        candidate_id=cand.candidate_id,
        config_key="latency_p95_ms.tier_b",
        old_value="2000",
        new_value="1760",
        audit_seq=123,
    )
    return TunerRunResult(
        session_date="2026-05-24",
        generated_at_utc="2026-05-24T22:00:00.000Z",
        mode=mode,  # type: ignore[arg-type]
        candidates=(cls,),
        applied=(applied,) if mode == "apply" else (),
        canary_entered=(),
        awaiting_human_merge=(),
        skipped=(),
    )


def test_report_structure() -> None:
    d = to_dict(_result())
    assert d["schema_version"] == "1.1"
    assert d["session_date"] == "2026-05-24"
    assert d["mode"] == "apply"
    assert d["candidates"][0]["authority_tier"] == "L1"
    assert d["candidates"][0]["proposed"]["new_value"] == "1760"
    assert d["applied"][0]["audit_seq"] == 123
    # 스펙 012: 신규 섹션 존재(기본 빈 리스트).
    assert d["canary_candidates"] == []
    assert d["canary_validations"] == []


def test_applied_matches_candidate() -> None:
    """applied 항목이 후보와 정합."""
    d = to_dict(_result())
    assert len(d["applied"]) == 1
    assert d["applied"][0]["candidate_id"] == "threshold_tighten:latency_p95_ms"


def test_dry_run_has_empty_applied() -> None:
    d = to_dict(_result(mode="dry_run"))
    assert d["mode"] == "dry_run"
    assert d["applied"] == []


def test_write_report_to_file(tmp_path: Path) -> None:
    out = write_report(_result(), output_root=tmp_path)
    assert out == tmp_path / "2026-05-24" / "auto-tuner-report.json"
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["session_date"] == "2026-05-24"
    assert loaded["applied"][0]["new_value"] == "1760"
