# Contract: Credit Spread Factory Evidence

The JSON result MUST include:

- `schema_version`, `gate_version`, `batch_id`, `timestamp_utc`, `code_commit`.
- `credit_data_fingerprint`, `candidate_count=64`, `complete_trial_count=64`.
- `prior_trial_count=576`, `global_audit_trial_count=640`, `multiplicity_trial_count=64`.
- `prior_audit_lineage` is exactly 256 production, 192 exploratory, 64 macro, and 64 Treasury
  unique strategy fingerprints; repeated batches do not increase it.
- `audit_catalog.jsonl` contains exactly the 640 unique reconstructed records; `trial_ledger.jsonl`
  remains the append-only historical event stream and may contain repeated executions.
- `family_raw_trial_count=64`, bounded `family_effective_trial_count`.
- `statistical_family` with objective, benchmark, selection rule, development, embargo, holdout.
- `development_selection`, `holdout_confirmation`, `trial_records`, `credit_data`.
- `research_live_parity`, `live_credit_evidence`, `decision`, benchmarks, blend, safety.

`decision.verdict=FACTORY_EDGE` is valid only if every blocking gate passes. Even then,
`decision.live_whitelist_authorized` MUST remain false in this feature, and no capital or order action is implied.

Legacy gate results, stale evidence, identity mismatch, incomplete gates, or a target-weight digest mismatch MUST
be rejected before broker access.
