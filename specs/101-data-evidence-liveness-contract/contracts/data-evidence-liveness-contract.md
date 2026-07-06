# Contract: Data Evidence Liveness

## Command

```bash
uv run python scripts/data_evidence_liveness_probe.py \
  --repo-root . \
  --format json \
  --json-out /tmp/data_evidence_liveness.json \
  --summary-out /tmp/data_evidence_liveness.md
```

## Inputs

| Key | Source ref | Required |
|-----|------------|----------|
| `public-data-last-run` | `automation/public-data:LAST_RUN.md` | yes |
| `public-data-summary` | `automation/public-data:summary.json` | yes |
| `public-data-regime` | `automation/public-data:regime.json` | yes |
| `public-data-regime-timeline` | `automation/public-data:regime_timeline.csv` | yes |
| `regime-stratify` | `automation/regime-stratify-last-run:LAST_RUN.md` | yes |
| `pipeline-liveness` | `automation/pipeline-liveness-last-run:LAST_RUN.md` | yes |
| `released-work` | `automation/released-work-last-run:released_work.json` | yes |
| `capital-path-readiness` | `automation/capital-path-readiness-last-run:capital_path_readiness.json` | yes |

## Output JSON Shape

```json
{
  "schema_version": "1.0",
  "run_id": "local",
  "commit": "unknown",
  "timestamp_utc": "2026-07-07T00:00:00Z",
  "overall_status": "CONTRACT_READY",
  "completed_candidate_id": "candidate-data-evidence-liveness-contract",
  "next_candidate_id": "candidate-execution-quality-frontier-map",
  "evidence_surfaces": [],
  "data_liveness_checks": [],
  "source_observations": [],
  "quality_gates": [],
  "released_work_summary": {},
  "capital_path_summary": {},
  "safety_invariants": []
}
```

## Status Rules

- `CONTRACT_READY`: All required evidence is parseable; both data checks are registered, `OK`, and source timestamps match pipeline timestamps.
- `OBSERVATION_WAIT`: The registry is parseable and required checks are registered, but at least one data check is `LATE`, `STALE`, `MISSING`, or `PENDING`.
- `BLOCKED`: The registry is missing/malformed, required checks are absent, source timestamps for OK checks are missing, or source/check timestamps disagree.

## Safety Boundary

The probe is read-only. It must not call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.
