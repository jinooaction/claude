# Research: Stale Evidence Failure Separation

## Decision 1: Put the separation in `capital_path_readiness`

**Decision**: Add `observability_issues` directly to the capital path readiness report.

**Rationale**: The autonomous work execution loop consumes `capital_path_readiness.json` first. If the separation happens only later, the same stale candidate can still appear as a priority candidate in the upstream report.

**Alternatives considered**:

- Add a brand-new evidence-quality sidecar. Rejected for this iteration because it would add another workflow before fixing the source report that already feeds work selection.
- Only change `autonomous_work_execution`. Rejected because it already suppresses released work; the stale interpretation still remains visible in `capital-path-readiness`.

## Decision 2: Treat released-candidate echoes as observability issues

**Decision**: If `released-work` marks a candidate released but backlog or promotion still lists it, suppress it and emit an issue with `issue_type=released_candidate_echo`.

**Rationale**: The issue is stale evidence propagation, not a failed strategy or a candidate that needs implementation.

## Decision 3: Treat liveness non-OK checks as sidecar freshness issues

**Decision**: Convert `status` values other than `OK`, `PRESENT`, or `PASS` into `pipeline_liveness` observability issues.

**Rationale**: Liveness is about evidence freshness and availability. It should not directly change money-path readiness or strategy quality.

## Decision 4: Keep the workflow read-only

**Decision**: The existing workflow still fetches automation sidecar branches, runs a local probe, and publishes only its own sidecar.

**Rationale**: The feature is a reporting improvement. It must not introduce broker calls, secret reads beyond the GitHub token used for sidecar publication, live commands, PR commands, or merge commands.
