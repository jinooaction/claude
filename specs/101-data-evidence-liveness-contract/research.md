# Research: Data Evidence Liveness Contract

## Decision 1: Reuse pipeline-liveness as the registry source of truth

**Decision**: Parse `automation/pipeline-liveness-last-run:LAST_RUN.md` and evaluate only the `collect-public-data` and `regime-stratify` rows for this contract.

**Rationale**: `pipeline_liveness.default_specs()` already defines the expected key names, thresholds, criticality, and timestamp extraction model. Duplicating the registry in this contract would create drift.

**Alternatives Considered**:

- Recompute liveness directly from every source file. Rejected because it would duplicate sidecar age policy and hide registry drift.
- Trust `public-data` and `regime-stratify` reports without pipeline-liveness. Rejected because the candidate is specifically about separating pipeline-liveness checks into data-quality PASS/WAIT/FAIL criteria.

## Decision 2: Missing registry evidence is BLOCKED, non-OK data checks are WAIT

**Decision**: Missing or malformed `pipeline-liveness`, missing required check rows, and missing source/check timestamps are `BLOCKED`; non-OK but parseable data check statuses are `OBSERVATION_WAIT`.

**Rationale**: If the registry cannot be audited, the liveness contract cannot make a reliable claim. If the registry is parseable and simply reports stale/missing data sidecars, the correct action is to wait for or repair the source automation, not to declare the contract malformed.

**Alternatives Considered**:

- Treat malformed pipeline-liveness as WAIT. Rejected because this contract's primary evidence would be unauditable.
- Treat stale data checks as FAIL. Rejected because public-data and regime-stratify are research/reporting sidecars and do not mutate money path state.

## Decision 3: Cross-check source LAST_RUN timestamps

**Decision**: For OK data checks, require the source LAST_RUN timestamp to exist and match the pipeline check timestamp (`timestamp_utc` or `last_success_utc`).

**Rationale**: Pipeline summary alone can go stale or point to a different observation. The direct source timestamp makes the report reproducible for the next session.

**Alternatives Considered**:

- Record only pipeline status and age. Rejected because it does not prove the source sidecar that produced the status is auditably present.
- Allow source timestamps to be newer than the pipeline check. Rejected for v1 because the report must preserve a simple exact provenance relationship.

## Decision 4: Completion advances to execution-quality macro frontier

**Decision**: Once `candidate-data-evidence-liveness-contract` is released with the prior data evidence frontier candidates, autonomous-work should select `candidate-execution-quality-frontier-map`.

**Rationale**: The data evidence frontier has three templates. This candidate is the final open entry, so releasing it exhausts that macro area and the next highest-priority underexplored area is execution quality.

**Alternatives Considered**:

- Add another data evidence candidate immediately. Rejected because the candidate map should first prove macro advancement and avoid endlessly mining one area without explicit new evidence.
