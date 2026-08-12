# Research: Validation Failure Data Readiness Contract

## Decision: Use existing sidecar evidence instead of rerunning validation commands

**Rationale**: Candidate-result-executor already executed the validation commands and stores stdout/stderr excerpts, exit codes, package identity, and package status. Rerunning would blur the purpose of this child candidate and could create new evidence drift.

**Alternatives considered**:
- Rerun portfolio-walk-forward commands: rejected because this candidate is a readiness contract, not execution retry.
- Parse only HANDOFF prose: rejected because prose is not machine-readable enough for autonomous-work progression.

## Decision: Treat public-data partial research failures as observations unless they block package inputs

**Rationale**: The latest public-data sidecar is research-only and can have unrelated CPI freshness issues. The current validation package portfolio commands use candidate history support roots and portfolio TOMLs. A public-data limitation should be recorded, but it must not falsely turn a data-ready package into a data-input failure.

**Alternatives considered**:
- Fail all packages when public-data `overall_ok=false`: rejected because it conflates unrelated research data with candidate package inputs.
- Ignore public-data entirely: rejected because the selected candidate explicitly requires it as context.

## Decision: Use completed candidate marker in SDD artifacts

**Rationale**: Released-work already scans SDD artifacts for `completed_candidate_id`. Adding the marker lets autonomous-work advance to `candidate-broad-validation-failure-package-kind-expansion-contract` without bespoke state.

**Alternatives considered**:
- Add a new state file outside SDD: rejected because released-work already has a stable scan path.
