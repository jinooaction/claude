# Contract: Broker Diagnostic Liveness

completed_candidate_id: candidate-broker-diagnostic-liveness-contract

## Command

```bash
uv run python scripts/broker_diagnostic_liveness_probe.py \
  --repo-root . \
  --format json \
  --json-out /tmp/broker_diagnostic_liveness.json \
  --summary-out /tmp/broker_diagnostic_liveness.md
```

## Inputs

| Key | Source ref | Required |
|-----|------------|----------|
| `kis-smoke` | `automation/kis-smoke-last-run:LAST_RUN.md` | yes |
| `execution-quality` | `automation/execution-quality-last-run:LAST_RUN.md` | yes |
| `pipeline-liveness` | `automation/pipeline-liveness-last-run:LAST_RUN.md` | yes |
| `released-work` | `automation/released-work-last-run:released_work.json` | yes |
| `capital-path-readiness` | `automation/capital-path-readiness-last-run:capital_path_readiness.json` | yes |

## Output JSON Shape

```json
{
  "schema_version": "1.0",
  "run_id": "local",
  "commit": "unknown",
  "timestamp_utc": "2026-07-08T00:00:00Z",
  "overall_status": "CONTRACT_READY",
  "completed_candidate_id": "candidate-broker-diagnostic-liveness-contract",
  "next_candidate_id": "candidate-agent-ops-frontier-map",
  "evidence_surfaces": [],
  "kis_smoke_summary": {},
  "execution_quality_summary": {},
  "pipeline_liveness_summary": {},
  "diagnostic_summary": {},
  "quality_gates": [],
  "released_work_summary": {},
  "capital_path_summary": {},
  "safety_invariants": []
}
```

## Status Rules

- `CONTRACT_READY`: Required evidence is parseable, standalone KIS smoke is healthy, execution-quality contains healthy broker smoke evidence, and pipeline-liveness reports relevant checks as OK.
- `OBSERVATION_WAIT`: Required evidence is parseable and standalone KIS smoke is healthy, but embedded broker smoke or relevant pipeline check coverage is incomplete.
- `BLOCKED`: Required evidence is missing or malformed, KIS smoke fails, key validity is false, smoke exit is nonzero, or relevant pipeline checks are stale/critical.

## Safety Boundary

The probe is read-only. It must not call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.
