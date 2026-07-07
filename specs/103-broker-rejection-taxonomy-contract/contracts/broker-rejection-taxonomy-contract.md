# Contract: Broker Rejection Taxonomy

completed_candidate_id: candidate-broker-rejection-taxonomy-contract

## Command

```bash
uv run python scripts/broker_rejection_taxonomy_probe.py \
  --repo-root . \
  --format json \
  --json-out /tmp/broker_rejection_taxonomy.json \
  --summary-out /tmp/broker_rejection_taxonomy.md
```

## Inputs

| Key | Source ref | Required |
|-----|------------|----------|
| `execution-quality` | `automation/execution-quality-last-run:LAST_RUN.md` | yes |
| `kis-smoke` | `automation/kis-smoke-last-run:LAST_RUN.md` | yes |
| `rebalance-micro-gtaa` | `automation/rebalance-micro-gtaa-last-run:LAST_RUN.md` | yes |
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
  "completed_candidate_id": "candidate-broker-rejection-taxonomy-contract",
  "next_candidate_id": "candidate-execution-cost-basis-contract",
  "evidence_surfaces": [],
  "rejection_summary": {},
  "taxonomy": [],
  "live_intent_context": {},
  "broker_smoke_summary": {},
  "quality_gates": [],
  "released_work_summary": {},
  "capital_path_summary": {},
  "safety_invariants": []
}
```

## Status Rules

- `CONTRACT_READY`: Required evidence is parseable, broker rejection signatures are classified, KIS smoke is healthy, and safety boundary is intact.
- `OBSERVATION_WAIT`: Required evidence is parseable but rejected-order observations are absent or KIS smoke/live-gate evidence indicates waiting.
- `BLOCKED`: Required evidence is missing or malformed, or the report cannot audit the execution-quality broker rejection block.

## Taxonomy Rules

- Known KIS message code `APBK1672` maps to `kis_order_response_rejection`.
- Unknown KIS message codes map to `unknown_broker_response` while preserving only aggregated counts.
- The taxonomy must not claim total broker outage from rejected-order rows.
- If live intent context contains `latest_signal=INTENT_LOSS`, the action category must remain no automatic retry.

## Safety Boundary

The probe is read-only. It must not call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.
