# Research: Validation Failure Package-Kind Expansion Contract

## Decision: Split by package kind before choosing new no-live experiments

**Rationale**: The current failures share `execution_failed`, but one is a strategy package and one is a portfolio package. Treating them as one bucket makes the next action too narrow. Package kind is already emitted by candidate-packages and candidate-results, so it is the most stable first split.

**Alternatives considered**:

- Split by candidate id only: rejected because it loses the common strategy-vs-portfolio learning axis.
- Split by raw command text only: rejected because command text is too low-level for the operator and next autonomous-work candidate.
- Split by final status only: rejected because both current packages are `fail`, which preserves the ambiguity.

## Decision: Use existing result evidence and never rerun commands

**Rationale**: Candidate-result-executor already stores commands, exit codes, stdout/stderr excerpts, and raw metrics. The package-kind child should classify and route existing failures, not create new market evidence.

**Alternatives considered**:

- Rerun portfolio-walk-forward commands: rejected because data readiness already proved inputs are ready, and rerun drift would obscure the contract.
- Parse only HANDOFF prose: rejected because prose does not preserve package-level references reliably enough.

## Decision: Keep deep walk-forward hints as hints, not promotion evidence

**Rationale**: The strategy package contains one failed portfolio-walk-forward execution and one deep walk-forward text excerpt with positive long-horizon candidates. That is useful for next no-live axes, but it does not overturn the candidate-result fail status or open live trading.

**Alternatives considered**:

- Promote based on the deep walk-forward excerpt: rejected because the current package result is fail and money-path still says `PREVIEW_ONLY` / `NO_EDGE_YET`.
- Ignore the excerpt entirely: rejected because it contains a useful signal-family and holding-period hint for the next no-live design.

## Decision: Close with a released-work marker

**Rationale**: Released-work already scans SDD artifacts for `completed_candidate_id`. Adding the marker lets autonomous-work advance to `candidate-broad-validation-failure-promotion-recheck-contract` without a new state store.

**Alternatives considered**:

- Add a new automation branch: rejected because SDD completion markers already solve this.
- Manually edit autonomous-work sidecar: rejected because sidecars are outputs, not source truth.
