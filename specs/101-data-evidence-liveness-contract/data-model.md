# Data Model: Data Evidence Liveness Contract

## DataEvidenceLivenessReport

- `schema_version`: Contract schema version.
- `run_id`: Local or workflow run identifier.
- `commit`: Source commit hash used to generate the report.
- `timestamp_utc`: Report creation time.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `completed_candidate_id`: Stable marker `candidate-data-evidence-liveness-contract`.
- `next_candidate_id`: Expected next autonomous candidate `candidate-execution-quality-frontier-map`.
- `evidence_surfaces`: Ordered list of consumed sidecar inputs and parse status.
- `data_liveness_checks`: Parsed liveness facts for `collect-public-data` and `regime-stratify`.
- `source_observations`: Direct source LAST_RUN timestamp observations for audited checks.
- `quality_gates`: PASS/WAIT/FAIL decisions.
- `released_work_summary`: Released-work state for this candidate marker.
- `capital_path_summary`: Read-only money-path context proving no mutation.
- `safety_invariants`: Explicit no-mutation safety boundary.

## DataLivenessCheck

- `key`: `collect-public-data` or `regime-stratify`.
- `status`: Pipeline status such as `OK`, `LATE`, `STALE`, `MISSING`, or `PENDING`.
- `critical`: Boolean copied from the pipeline row or registry default.
- `age_hours`: Numeric sidecar age from pipeline-liveness when present.
- `max_age_hours`: Expected maximum age for the check.
- `pipeline_timestamp_utc`: Pipeline row timestamp (`timestamp_utc` or `last_success_utc`).
- `source_timestamp_utc`: Matching source LAST_RUN timestamp when parseable.
- `source_matches_pipeline`: Whether direct source timestamp equals the pipeline timestamp.
- `summary_ko`: Korean explanation of the row.

## SourceSidecarObservation

- `key`: Source observation key, such as `public-data-last-run`.
- `check_key`: Matching pipeline check key.
- `timestamp_utc`: Parsed report timestamp from the source LAST_RUN.
- `present`: Whether the source file exists.
- `parse_status`: `ok`, `missing`, or `malformed`.
- `summary_ko`: Korean explanation of auditability.

## QualityGate

- `key`: Stable gate identifier.
- `status`: `PASS`, `WAIT`, or `FAIL`.
- `summary_ko`: Human-readable Korean explanation.
- `evidence_keys`: Evidence surfaces used by the gate.

## EvidenceSurface

- `key`: Internal evidence key.
- `source_ref`: Source sidecar ref, matching autonomous-work required inputs.
- `present`: Whether evidence was present.
- `parse_status`: `ok`, `present`, `missing`, or `malformed`.
- `summary_ko`: Short Korean parse summary.
