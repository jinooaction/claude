# Contract: Execution Cost Basis

completed_candidate_id: candidate-execution-cost-basis-contract

## Command

```bash
uv run python scripts/execution_cost_basis_probe.py \
  --repo-root . \
  --format json \
  --json-out /tmp/execution_cost_basis.json \
  --summary-out /tmp/execution_cost_basis.md
```

## Inputs

| Key | Source ref | Required |
|-----|------------|----------|
| `execution-quality` | `automation/execution-quality-last-run:LAST_RUN.md` | yes |
| `kis-smoke` | `automation/kis-smoke-last-run:LAST_RUN.md` | yes |
| `rebalance-micro-gtaa` | `automation/rebalance-micro-gtaa-last-run:LAST_RUN.md` | yes |
| `money-path` | `automation/money-path-last-run:LAST_RUN.md` | yes |
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
  "overall_status": "OBSERVATION_WAIT",
  "completed_candidate_id": "candidate-execution-cost-basis-contract",
  "next_candidate_id": "candidate-broker-diagnostic-liveness-contract",
  "evidence_surfaces": [],
  "execution_quality_summary": {},
  "money_path_summary": {},
  "cost_basis_summary": {},
  "quality_gates": [],
  "released_work_summary": {},
  "capital_path_summary": {},
  "safety_invariants": []
}
```

## Status Rules

- `CONTRACT_READY`: Required evidence is parseable and measurable accepted/fill cost basis is complete.
- `OBSERVATION_WAIT`: Required evidence is parseable but `execution_cost_basis` is absent or accepted/fill cost basis is incomplete.
- `BLOCKED`: Required evidence is missing or malformed, or money-path context cannot be audited.

## Cost Basis Rules

- A ready report requires measurable accepted/fill cost basis, not just rejected-order evidence.
- Missing `execution_cost_basis` is observation wait when required inputs otherwise parse.
- Accepted/fill count without measurable slippage or turnover basis remains observation wait.
- `PREVIEW_ONLY` money-path state must not be interpreted as permission to collect real-order samples.

## Safety Boundary

The probe is read-only. It must not call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.
