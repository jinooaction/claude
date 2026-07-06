# Data Model: Public Data Input Quality Contract

## PublicDataInputQualityReport

Top-level deterministic report emitted by the probe.

- `schema_version`: Contract version.
- `run_id`: Workflow or local run id.
- `commit`: Source commit for the report.
- `timestamp_utc`: Report generation time.
- `contract_id`: Stable id `public-data-input-quality-contract`.
- `completed_candidate_id`: Stable released-work marker `candidate-public-data-input-quality-contract`.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `headline_ko`: Korean one-line interpretation.
- `required_inputs`: Required evidence refs.
- `evidence_surfaces`: Parsed input list.
- `public_data_summary`: Publication and cross-check facts.
- `regime_coverage`: Regime summary, timeline, and stratify coverage facts.
- `validation_gates`: PASS/WAIT/FAIL gate decisions.
- `released_work_summary`: Whether this candidate is already released.
- `capital_path_summary`: Read-only money path context.
- `safety_boundary`: Invariants preserved by the report.

## EvidenceSurface

Represents one consumed sidecar input.

- `key`: Stable input key.
- `source_ref`: Branch/file reference.
- `present`: Whether the sidecar was supplied.
- `parse_status`: `ok`, `missing`, or `malformed`.
- `summary_ko`: Human-readable Korean summary.

## PublicDataSummary

Facts parsed from public-data summary.

- `overall_ok`: Whether the collector considered the snapshot OK.
- `published`: Number of published items.
- `total_items`: Expected item count.
- `item_count`: Parsed items.
- `failed_items`: Item identifiers with `ok=false`.
- `cross_check_count`: Number of cross-checks.
- `failed_cross_checks`: Cross-check pair identifiers whose status is not PASS.
- `min_cross_check_overlap`: Smallest parsed overlap count.

## RegimeCoverageSummary

Facts parsed from regime summary, regime timeline, and regime-stratify.

- `overall_label`: Public-data regime label.
- `available_indicators`: Number of available public-data regime indicators.
- `total_indicators`: Expected regime indicators.
- `timeline_rows`: Number of regime timeline rows.
- `timeline_first_date`: First timeline date.
- `timeline_last_date`: Last timeline date.
- `timeline_labels`: Labels present in the timeline.
- `stratified_return_days`: Joined regime-stratify return days.
- `stratified_labels`: Labels present in regime-stratify output.

## ValidationGate

One gate in the contract.

- `gate_id`: Stable machine id.
- `status`: `PASS`, `WAIT`, or `FAIL`.
- `summary_ko`: Korean explanation.
- `required_evidence`: Evidence refs used by the gate.

## Completed Candidate Marker

The contract marker consumed by released-work:

- `completed_candidate_id: candidate-public-data-input-quality-contract`

This closes this input-quality contract only. It must not close `candidate-regime-timeline-coverage-contract` or `candidate-data-evidence-liveness-contract`.

## State Transitions

- Public-data input-quality candidate not released -> autonomous-work selects `candidate-public-data-input-quality-contract`.
- Public-data input-quality candidate released -> autonomous-work advances to `candidate-regime-timeline-coverage-contract`.
- Higher-priority repair, regular, operator-approval, or blocked packets still win.
