# Contract: Broad Frontier Expansion NO_EDGE Refresh

completed_candidate_id: candidate-broad-frontier-expansion-no-edge-122eb31c06bd
next_candidate_id: candidate-broad-no-edge-cross-asset-relative-value-experiment
risk_grade: 2
mode: read-only no-live candidate routing

## Consumed Inputs

```text
released-work	automation/released-work-last-run	released_work.json
money-path	automation/money-path-last-run	LAST_RUN.md
edge-autoarm	automation/edge-autoarm-last-run	LAST_RUN.md
rebalance-paper-forward	automation/rebalance-paper-forward-last-run	LAST_RUN.md
capital-path-readiness	automation/capital-path-readiness-last-run	capital_path_readiness.json
public-data	automation/public-data	LAST_RUN.md
public-data-summary	automation/public-data	summary.json
public-data-regime	automation/public-data	regime.json
public-data-regime-timeline	automation/public-data	regime_timeline.csv
regime-stratify	automation/regime-stratify-last-run	LAST_RUN.md
execution-quality	automation/execution-quality-last-run	LAST_RUN.md
kis-smoke	automation/kis-smoke-last-run	LAST_RUN.md
rebalance-micro-gtaa	automation/rebalance-micro-gtaa-last-run	LAST_RUN.md
pipeline-liveness	automation/pipeline-liveness-last-run	LAST_RUN.md
```

## Output Requirements

- `broad_no_edge_frontier_map` contains first-wave and second-wave no-live candidates in deterministic priority order.
- Parent broad no-edge candidate is not reissued after any broad no-edge parent is present in released-work.
- The first unreleased second-wave candidate becomes `EXECUTION_READY` when money path is still no-live.

## Safety Boundary

- No broker API call.
- No orders.
- No capital allocation.
- No live strategy change.
- No whitelist/caps change.
- No secret read/write.
- No constitution/kernel change.
- No external paid service.
