# Data Model: Candidate Implementation Factory

## ImplementationPackage

- `package_id`: stable package identifier.
- `candidate_id`: source candidate identifier.
- `title_ko`: candidate title.
- `package_kind`: one of `strategy_backtest`, `portfolio_backtest`, `gate_alignment`, `ops_liveness`, `review_ledger`, `analytics_validation`, `execution_quality`, `data_quality`, `data_collection`.
- `status`: `ready`, `pending`, `blocked`, or `evidence_passed`.
- `required_inputs`: data or sidecars required before execution can pass.
- `commands`: list of command plans. Commands are strings for operator/workflow execution, not executed by the factory.
- `produces_evidence`: evidence fields this package can produce.
- `promotion_patch`: additions to `promotion_evidence`.
- `block_reason_ko`: Korean reason when status is not pass-ready.
- `safety_note_ko`: safety boundary explanation.

## EvidenceResult

- `candidate_id`: candidate identifier.
- `historical_backtest`: `pass`, `fail`, `pending`, or `missing`.
- `recent_oos`: `pass`, `fail`, `pending`, or `missing`.
- `walk_forward`: `pass`, `fail`, `pending`, or `missing`.
- `source_ref`: source artifact path or sidecar.
- `forward_track`: optional machine-readable track config for promotion actions.
- `canary_track`: optional machine-readable canary config.

## FactoryRun

- `schema_version`: currently `1.0`.
- `run_id`: workflow or local run identifier.
- `commit`: code commit used to run the factory.
- `timestamp_utc`: run timestamp.
- `overall_status`: `ok` or `degraded`.
- `packages`: list of implementation packages.
- `missing_inputs`: run-level missing inputs.
- `enriched_candidate_backlog`: original candidate backlog with candidate-local `promotion_evidence` additions.
