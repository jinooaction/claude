# Research: Live Canary Sidecar Gate

## Decision: Split preview/status publication from real-order execution

**Rationale**: The latest pipeline-liveness sidecar reports `rebalance-live-canary` as late because the entire workflow waits for production approval. When the sentinel is `armed=false`, no real order can run, so making the sidecar wait for production approval gives the operator stale status without adding account safety. A separate preview/status job restores truthful evidence while leaving the actual real-order command in a production-gated job.

**Alternatives considered**:

- Approve production on every scheduled unarmed run: rejected because it requires manual intervention for zero-order status refreshes and trains the operator to approve noisy jobs.
- Remove production approval from the existing single job: rejected because it would put the live order command outside the approval gate.
- Leave the stale sidecar and rely on other liveness reports: rejected because `capital-path-readiness` consumes pipeline liveness and then reports a degraded path.

## Decision: Keep live measurement in the preview job only while unarmed

**Rationale**: An unarmed run can safely refresh dry-run preview and live-track status. An armed run with pending production approval must not write a pre-order live NAV snapshot that could be confused with after-order measurement. The real-order job measures after orders when it actually runs.

**Alternatives considered**:

- Always measure in preview: rejected because armed approval-pending runs could create a misleading pre-order live measurement.
- Never measure in preview: rejected because unarmed liveness would lose useful live-track status despite placing zero orders.

## Decision: Guard the workflow with static tests

**Rationale**: The highest-risk regression is a future edit that accidentally moves `--mode live --confirm-live` into the preview/status job or removes production approval from the real-order job. Static tests over the workflow text are cheap, deterministic, and directly prove this command boundary.

**Alternatives considered**:

- Only rely on GitHub Actions review: rejected because the exact failure mode is structural and should break locally before PR.
- Run the live workflow as a local integration test: rejected because local tests cannot safely exercise GitHub production approval or the real broker boundary.

## Decision: Verify post-merge with main-branch sidecars

**Rationale**: Local tests prove the workflow shape, but the observed bug is in live GitHub Actions behavior. After merge, a main-branch workflow dispatch while `armed=false` should refresh the sidecar without real orders, and a pipeline-liveness refresh should prove the stale status is cleared.

**Alternatives considered**:

- Stop after local tests: rejected because it would not prove the actual sidecar freshness problem is fixed.
- Dispatch a production-approved real-order job: rejected because the user did not approve real orders and the current sentinel is unarmed.

## Decision: Route preview/status through fixed observe commands

**Rationale**: Post-merge verification of PR #568 proved the sidecar timestamp refreshed, but the live canary backfill, dry-run preview, and live-track measurement all returned `refused command` because the hardened SSH gateway no longer accepts raw remote shell command strings. Adding fixed observe verbs keeps the gateway narrow while allowing the preview/status job to produce meaningful sidecar content.

**Alternatives considered**:

- Reopen raw SSH command execution: rejected because it would undo the SSH trust-boundary repair and widen the server command surface.
- Add a live-order observe verb now: rejected because actual real-order gateway enablement is a separate money-path change and is not needed while `armed=false`.
- Publish fresh sidecars with refused-command logs: rejected because it makes liveness fresh but not useful for operator judgment.
