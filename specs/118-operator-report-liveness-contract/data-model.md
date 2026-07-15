# Data Model: Operator Report Liveness Contract

## OperatorReportLivenessReport

- `schema_version`: Report schema version.
- `run_id`: Workflow or local probe run id.
- `commit`: Source commit associated with the report.
- `timestamp_utc`: UTC report timestamp.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `completed_candidate_id`: Always `candidate-operator-report-liveness-contract`.
- `next_candidate_id`: `none` until a later frontier map adds a successor.
- `evidence_surfaces`: Input surfaces and parse status.
- `rule_surface_summary`: Deterministic summary of repository rule surfaces.
- `final_report_summary`: Deterministic summary of supplied final-report observation.
- `quality_gates`: PASS/WAIT/FAIL gates.
- `released_work_summary`: Completion marker state from released-work evidence.
- `safety_invariants`: Forbidden side effects.

## EvidenceSurface

- `key`: Stable evidence key.
- `source_ref`: Local file or supplied evidence reference.
- `present`: Whether evidence exists.
- `parse_status`: `ok`, `present`, `missing`, or `malformed`.
- `summary_ko`: Short Korean explanation for the report.

## QualityGate

- `gate_id`: Stable gate key.
- `status`: `PASS`, `WAIT`, or `FAIL`.
- `summary_ko`: Operator-readable reason.
- `evidence_keys`: Inputs used for the gate.

## FinalReportObservation

- `state`: PASS/WAIT/FAIL summary.
- `present_categories`: Required meaning categories found in supplied text.
- `missing_categories`: Required meaning categories not found.
- `evidence_only`: Whether the text appears to rely only on PR/hash/test evidence without operational meaning.

## State Transitions

```text
all rule surfaces PASS + final report PASS + released-work PASS -> CONTRACT_READY
final report missing or released-work not consumed -> OBSERVATION_WAIT
required rule surface broken or final report FAIL or released-work malformed -> BLOCKED
```
