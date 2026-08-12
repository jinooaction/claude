# Data Model: Broad NO_EDGE Data Gap Audit

## Data Gap Audit Report

- `schema_version`: report schema version.
- `run_id`: local or workflow run id.
- `commit`: source commit.
- `timestamp_utc`: report generation time.
- `audit_id`: stable audit id `broad-no-edge-data-gap-audit`.
- `completed_candidate_id`: `candidate-broad-no-edge-data-gap-audit`.
- `next_candidate_id`: next state `wait-for-fresh-evidence`.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `evidence_surfaces`: consumed sidecar parse summaries.
- `public_data_gaps`: item-level publication and freshness gaps.
- `cross_check_gaps`: cross-check pass/skip/fail gaps.
- `regime_indicator_gaps`: regime indicator status and impact.
- `timeline_gap_summary`: CSV shape, labels, and missing columns.
- `stratified_join_summary`: regime-stratify section and label coverage.
- `forward_no_edge_summary`: forward paper rows and `NO_EDGE` count.
- `causal_findings`: deterministic impact conclusions.
- `validation_gates`: pass/wait/fail gates.
- `money_state`: money-path status.
- `edge_autoarm_state`: edge-autoarm action.
- `safety_boundary`: invariant list.

## Evidence Surface

- `key`: stable input key.
- `source_ref`: branch/file reference.
- `present`: whether raw input exists.
- `parse_status`: `ok`, `missing`, or `malformed`.
- `summary_ko`: short Korean summary.

## Public Data Item Gap

- `kind`, `item_id`: public-data item identity.
- `ok`: whether the source item reports success.
- `rows`, `first_date`, `last_date`, `missing`: coverage values.
- `published`: emitted path, if any.
- `issues`: issue text from the sidecar.
- `gap_causes`: deterministic cause codes.
- `no_edge_impact`: `LOW`, `MEDIUM`, `HIGH`, or `UNKNOWN`.
- `reason_ko`: operator-readable explanation.

## Cross Check Gap

- `pair`, `kind`, `status`, `overlap`, `detail`: source cross-check fields.
- `gap_cause`: `PASS`, `SKIPPED_MISSING_INPUT`, `FAILED_CROSS_CHECK`, or `INSUFFICIENT_OVERLAP`.
- `no_edge_impact`: deterministic impact level.

## Regime Indicator Gap

- `indicator`, `status`, `state`, `reason`, `source`: regime indicator fields.
- `gap_cause`: `READY` or a deterministic gap cause.
- `no_edge_impact`: deterministic impact level.

## Timeline Gap Summary

- `row_count`, `first_date`, `last_date`: CSV coverage.
- `label_counts`: label distribution.
- `canonical_labels_missing`: missing canonical labels.
- `missing_column_counts`: missing values by important column.
- `missing_column_pcts`: missing percentages by important column.
- `min_available`, `available_distribution`: regime input availability across rows.

## Stratified Join Summary

- `section_count`: parsed stratified section count.
- `sections`: section name, join rule, total return days, label counts, sparse labels, and mismatch flags.
- `sparse_labels`: labels with fewer than 20 observations.
- `non_forward_sections`: sections without d+1 forward join.
- `count_mismatches`: sections where labels do not sum to total return days.

## Forward No Edge Summary

- `track_count`: number of forward rows.
- `no_edge_count`: rows with `NO_EDGE` verdict.
- `rows`: key, label, verdict, observation count, rank, incumbent flag.

## Causal Finding

- `finding_id`: stable finding key.
- `impact`: `LOW`, `MEDIUM`, `HIGH`, or `UNKNOWN`.
- `summary_ko`: concise Korean conclusion.
- `evidence_keys`: source evidence keys.

## Validation Gate

- `gate_id`: stable gate key.
- `status`: `PASS`, `WAIT`, or `FAIL`.
- `summary_ko`: reason.
- `required_evidence`: input refs used by the gate.
