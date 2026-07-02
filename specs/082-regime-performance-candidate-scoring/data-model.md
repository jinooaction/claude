# Data Model: 레짐·성과 후보 점수화

## EvidenceRequirement

- `key`: `promote-readiness`
- `branch`: `automation/promote-readiness-last-run`
- `filename`: `LAST_RUN.md`
- `max_age_hours`: 30
- `kind`: `sidecar`

Validation:

- Missing or unparsable text must not produce a performance boost.
- Freshness must use the same freshness state model as existing sidecars.

## RegimePerformanceSignal

- `regime_fresh`: whether `regime-stratify` is fresh enough.
- `public_data_fresh`: whether `public-data` is fresh enough.
- `performance_fresh`: whether `promote-readiness` is fresh enough.
- `performance_ready`: whether readiness output reports `READY=true`.
- `performance_not_ready`: whether readiness output reports `READY=false`.
- `setup_error`: whether readiness output looks like setup or SSH failure rather than a conservative not-ready result.

Validation:

- `READY=false` with a normal report is valid evidence, not an error.
- `ssh_exit` values other than 0 or 1 are setup-error-like and should not boost confidence.

## BreakthroughCandidate

Existing entity extended by changed values only:

- Analysis candidate `evidence_refs` includes `regime-stratify`, `public-data`, and `promote-readiness`.
- Analysis candidate score components are adjusted deterministically from `RegimePerformanceSignal`.
- Analysis candidate `evidence_dependency` becomes `sidecar_freshness` when any required analysis evidence is stale, missing, or setup-error-like.

State transitions:

- Fresh all evidence -> `new`.
- Missing/stale/setup-error-like required analysis evidence -> `evidence_dependent`.
- Safety keywords detected -> existing operator review behavior.
