# Contract: Broad NO_EDGE Data Gap Audit

completed_candidate_id: candidate-broad-no-edge-data-gap-audit
next_candidate_id: wait-for-fresh-evidence
risk_grade: 2
mode: read-only no-live audit

## Consumed Inputs

```text
public-data-last-run	automation/public-data	LAST_RUN.md
public-data-summary	automation/public-data	summary.json
public-data-regime	automation/public-data	regime.json
public-data-regime-timeline	automation/public-data	regime_timeline.csv
regime-stratify	automation/regime-stratify-last-run	LAST_RUN.md
rebalance-paper-forward	automation/rebalance-paper-forward-last-run	LAST_RUN.md
money-path	automation/money-path-last-run	LAST_RUN.md
edge-autoarm	automation/edge-autoarm-last-run	LAST_RUN.md
released-work	automation/released-work-last-run	released_work.json
pipeline-liveness	automation/pipeline-liveness-last-run	LAST_RUN.md
```

## Output Requirements

- JSON output contains `audit_id`, `completed_candidate_id`, `next_candidate_id`, `overall_status`, `public_data_gaps`, `cross_check_gaps`, `regime_indicator_gaps`, `timeline_gap_summary`, `stratified_join_summary`, `forward_no_edge_summary`, `causal_findings`, `validation_gates`, `money_state`, `edge_autoarm_state`, and `safety_boundary`.
- Markdown output contains summary, data gaps, timeline gaps, causal findings, validation gates, and safety boundary.
- Missing or malformed critical input produces `BLOCKED`.
- Parseable evidence with important but classified data gaps can still produce `CONTRACT_READY`; the gap itself must be visible in `causal_findings`.

## Safety Boundary

- No broker API call.
- No orders.
- No capital allocation.
- No live strategy change.
- No whitelist/caps change.
- No secret read/write.
- No constitution/kernel change.
- No fresh external collection.
- No paid external service.
