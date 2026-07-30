# Research: Evidence-Based Candidate Source Diversification

## Decision: Synthesize a new work packet from blocked validation evidence

**Rationale**: Current sidecars show the money path is `PREVIEW_ONLY` / `NO_EDGE_YET`, and the candidate-result executor has two retryable `execution_failed` package blockers. These are useful evidence sources, but the autonomous work loop can still surface closed candidates because blocked packages prevent the regular queue from being treated as closed. A synthesized packet converts that bottleneck into the next safe Codex task.

**Alternatives considered**:
- Approve pending guarded live workflows: rejected because money-path and forward verdict do not allow real orders.
- Reopen released static candidates: rejected because released-work is the completion ledger.
- Ignore blocked packages and wait: rejected because the blockers are retryable and safe to inspect.

## Decision: Keep the feature in read-only analytics surfaces

**Rationale**: The change should improve candidate flow, not trading authority. Existing sidecar reports already carry candidate IDs, package IDs, package kinds, diagnostics, retryability, and next actions. The work packet can consume those without broker calls, capital changes, or secret access.

**Alternatives considered**:
- Add a new workflow with privileged access: rejected because the current evidence is already public-safe.
- Store candidate decisions in a database: rejected because the existing Git sidecar model is sufficient and deterministic.

## Decision: Exclude released and suppressed candidates before choosing the selected work

**Rationale**: If a candidate is already released or suppressed, selecting it as the active work makes the operator do the same reasoning twice. Closed candidates may remain visible in suppressed work for auditability, but `selected_work` should prefer fresh execution-ready packets or a wait state.

**Alternatives considered**:
- Keep selected_work as the top closed candidate when no ranked item exists: rejected because it reads like unfinished work.
- Hide closed candidates entirely: rejected because auditability and learning metrics need to show why they were skipped.

## Decision: Treat pending guarded live workflows as safety context only

**Rationale**: A protected live workflow in `waiting` or `pending` state is an approval boundary. It is not evidence that the strategy has edge or that the session should approve live money. The packet must point back to candidate validation while preserving `PREVIEW_ONLY`.

**Alternatives considered**:
- Cancel or approve the waiting workflows in this feature: rejected because that is outside the candidate source problem and touches real-money boundaries.
