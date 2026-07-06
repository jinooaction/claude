# Data Model: Regime Timeline Coverage Contract

## RegimeTimelineCoverageReport

Top-level deterministic report emitted by the probe.

- `schema_version`: Contract version.
- `run_id`: Workflow or local run id.
- `commit`: Source commit for the report.
- `timestamp_utc`: Report generation time.
- `completed_candidate_id`: Stable released-work marker `candidate-regime-timeline-coverage-contract`.
- `next_candidate_id`: Stable next candidate `candidate-data-evidence-liveness-contract`.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `evidence_surfaces`: Parsed input list.
- `timeline_summary`: Timeline shape and label coverage facts.
- `stratified_summary`: Section-level regime-stratify facts.
- `liveness_summary`: Read-only collect-public-data and regime-stratify freshness facts.
- `released_work_summary`: Whether this candidate is already released.
- `quality_gates`: PASS/WAIT/FAIL gate decisions.
- `safety_invariants`: Invariants preserved by the report.

## EvidenceSurface

Represents one consumed sidecar input.

- `key`: Stable input key.
- `source_ref`: Branch/file reference.
- `present`: Whether the sidecar was supplied.
- `parse_status`: `ok`, `missing`, or `malformed`.
- `summary_ko`: Human-readable Korean summary.

## TimelineSummary

Facts parsed from `regime_timeline.csv`.

- `parseable`: Whether the CSV parsed and exposed `date,label`.
- `row_count`: Number of timeline rows.
- `first_date`: First parsed timeline date.
- `last_date`: Last parsed timeline date.
- `label_counts`: Count by non-empty label.
- `canonical_labels_present`: Canonical labels present among `RISK_ON`, `CAUTION`, and `RISK_OFF`.
- `canonical_labels_missing`: Canonical labels absent from the timeline.
- `missing_label_rows`: Rows with blank label values.
- `duplicate_dates`: Duplicate date values.
- `invalid_date_rows`: Rows whose date cannot be parsed.
- `out_of_order_dates`: Whether date order is not monotonic ascending.

## StratifiedSectionSummary

Facts parsed from one `regime-stratify` strategy section.

- `section_name`: Markdown section title or generated fallback name.
- `parseable`: Whether a stratified JSON object was parsed.
- `total_return_days`: Joined return count.
- `join_rule`: Reported join rule.
- `forward_join`: Whether the join rule explicitly states d+1 or future-leak prevention.
- `label_counts`: `by_label[*].n_days` counts.
- `count_sum`: Sum of label counts.
- `count_matches_total`: Whether `count_sum == total_return_days`.
- `sparse_labels`: Canonical labels with count below 20.
- `missing_labels`: Canonical labels absent from this section.
- `unknown_labels`: Labels not present in the timeline label set, excluding accepted diagnostic `UNLABELED`.
- `unlabeled_days`: `UNLABELED` joined return days, if any.

## QualityGate

One gate in the contract.

- `key`: Stable machine id.
- `status`: `PASS`, `WAIT`, or `FAIL`.
- `summary_ko`: Korean explanation.
- `evidence_keys`: Evidence refs used by the gate.

## Completed Candidate Marker

The contract marker consumed by released-work:

- `completed_candidate_id: candidate-regime-timeline-coverage-contract`

This closes this timeline coverage contract only. It must not close `candidate-data-evidence-liveness-contract`.

## State Transitions

- Public-data input-quality candidate released and regime timeline coverage candidate not released -> autonomous-work selects `candidate-regime-timeline-coverage-contract`.
- Regime timeline coverage candidate released -> autonomous-work advances to `candidate-data-evidence-liveness-contract`.
- Higher-priority repair, regular, operator-approval, or blocked packets still win.
