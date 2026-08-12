# Contract: Broad NO_EDGE Regime Cost Robustness

completed_candidate_id: candidate-broad-no-edge-regime-cost-robustness-experiment

next_candidate_id: candidate-broad-no-edge-data-gap-audit

## Consumed Sidecars

| key | branch | file |
|-----|--------|------|
| regime-stratify | automation/regime-stratify-last-run | LAST_RUN.md |
| execution-quality | automation/execution-quality-last-run | LAST_RUN.md |
| money-path | automation/money-path-last-run | LAST_RUN.md |
| edge-autoarm | automation/edge-autoarm-last-run | LAST_RUN.md |
| rebalance-paper-forward | automation/rebalance-paper-forward-last-run | LAST_RUN.md |
| released-work | automation/released-work-last-run | released_work.json |
| evolution-ledger | automation/autonomous-evolution-last-run | learning_ledger.json |
| pipeline-liveness | automation/pipeline-liveness-last-run | LAST_RUN.md |

## Output Contract

The report MUST emit JSON and Markdown containing:

- `schema_version`
- `experiment_id`
- `completed_candidate_id`
- `next_candidate_id`
- `overall_status`
- `required_inputs`
- `evidence_surfaces`
- `regime_windows`
- `regime_metrics`
- `execution_cost_snapshot`
- `money_state`
- `edge_autoarm_state`
- `cost_stress_rows`
- `exclusion_criteria`
- `validation_gates`
- `learning_summary`
- `released_work_summary`
- `safety_boundary`

## Status Rules

- `BLOCKED`: any critical evidence is missing or malformed, pipeline is critical/fail, or learning ledger suppresses this candidate.
- `OBSERVATION_WAIT`: evidence is readable but money/edge posture is not no-live aligned, regime windows are too sparse, or released-work has not yet seen the completion marker.
- `CONTRACT_READY`: required evidence is readable, no-live posture is preserved, at least one regime window is usable, three cost stress rows exist, and released-work closure is visible.

## Safety Boundary

The contract is read-only and deterministic. It MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, modify whitelist/caps, read or write secrets, touch constitution/kernel files, or use paid external services.
