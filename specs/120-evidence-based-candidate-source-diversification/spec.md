# Feature Specification: Evidence-Based Candidate Source Diversification

**Feature Branch**: `codex/evidence-based-candidate-source-diversification`
**Created**: 2026-07-31
**Status**: Draft
**Input**: User description: "목표 스킬로 진행해" after the live-money path was verified as `PREVIEW_ONLY` / `NO_EDGE_YET` and the next concrete action was identified as evidence-based candidate source diversification.

## User Scenarios & Testing

### User Story 1 - Select a Fresh Evidence-Based Candidate (Priority: P1)

As the operator, I need the autonomous work loop to stop circling around already released, rejected, or suppressed candidates and instead choose a fresh work packet derived from current sidecar bottlenecks.

**Why this priority**: The money path is waiting for verified edge, so repeatedly selecting closed candidates wastes the loop that should be producing new evidence and strategy candidates.

**Independent Test**: Can be fully tested with a current sidecar fixture where released-work marks prior candidates complete, candidate-result evidence has blocked packages, and the autonomous work report must select a new evidence-source-diversification packet rather than a closed candidate.

**Acceptance Scenarios**:

1. **Given** all static high-ranked candidates are released, rejected, or suppressed, **When** the autonomous work loop ranks candidates, **Then** it selects a new evidence-driven source-diversification candidate with a clear next action.
2. **Given** a candidate appears in both the backlog and released-work, **When** the loop builds its top candidate list, **Then** the released state wins and the candidate is not selected as active work.
3. **Given** fresh pipeline sidecars show no actionable bottleneck, **When** the loop cannot create a new candidate, **Then** it reports a wait state instead of pretending stale work remains.

---

### User Story 2 - Turn Blocked Validation Packages Into Actionable Evidence (Priority: P1)

As the operator, I need blocked strategy and portfolio validation packages to explain the specific next safe action, not just say that validation failed.

**Why this priority**: Current candidate-result evidence reports two retryable `execution_failed` blockers, but the loop does not yet turn them into a useful work packet that can improve future edge discovery.

**Independent Test**: Can be fully tested by feeding blocked strategy and portfolio package evidence into the candidate selection path and verifying the output includes reason class, package kind, retry condition, and a safe next action.

**Acceptance Scenarios**:

1. **Given** a blocked strategy-backtest package with retryable diagnostics, **When** candidate source diversification is built, **Then** the system records an inspect-validation-failure action tied to that package.
2. **Given** a blocked portfolio-backtest package with retryable diagnostics, **When** candidate source diversification is built, **Then** the system records it as a portfolio comparison bottleneck rather than as live-money approval evidence.
3. **Given** multiple blocked packages with the same cause, **When** the report is generated, **Then** it groups the cause without losing package-level traceability.

---

### User Story 3 - Preserve Real-Money Safety While Improving Candidate Flow (Priority: P2)

As the operator, I need the system to improve the route toward a verified edge without approving pending live-money workflows, changing capital, or weakening risk gates.

**Why this priority**: The desired outcome is eventually making money, but current evidence says the correct next step is more and better validation, not bypassing the capital ladder.

**Independent Test**: Can be fully tested by including `PREVIEW_ONLY`, `NO_EDGE_YET`, and pending guarded live workflow evidence in the fixture and verifying the selected work stays read-only and never marks real orders as allowed.

**Acceptance Scenarios**:

1. **Given** live-money workflows are waiting or pending under a protected environment, **When** candidate selection runs while money-path is `PREVIEW_ONLY`, **Then** the output says not to approve live execution.
2. **Given** forward verdict is `NO_EDGE`, **When** the next action is generated, **Then** it recommends candidate evidence expansion and forward validation rather than live rearming.
3. **Given** sidecars contain account-scale or broker-sensitive fields, **When** public reports are generated, **Then** the work packet avoids exposing those sensitive values.

### Edge Cases

- All candidate sources are stale or missing: report `WAIT_FOR_FRESH_EVIDENCE` with the missing source names and do not select a fake candidate.
- Released-work is stale but `origin/main` contains newer merges: prefer the latest synchronized sidecar and mark the decision as needing sidecar refresh.
- Blocked validation packages have no diagnostics: report `INSPECT_VALIDATION_FAILURE` with package IDs and mark the package as retryable only when evidence says so.
- A protected live-money workflow is pending: classify it as an approval boundary, not as an invitation to approve live money.
- Candidate evidence includes account values, host details, or tokens: keep them out of public summaries.
- The first evidence-source-diversification candidate is already released but the same sidecar chain still shows retryable blocked validation packages: generate a deterministic broad-frontier candidate from the package/diagnostic fingerprint instead of falling straight to `WAIT_FOR_FRESH_EVIDENCE`.
- The first evidence-source-diversification candidate is already released, no retryable blocked package remains, but money-path and edge-autoarm still say `PREVIEW_ONLY` / `NO_EDGE_YET` / `WAIT_EDGE`: generate a deterministic no-edge broad-frontier candidate instead of passively waiting.
- The same broad-frontier fingerprint is already released: do not loop on it; wait for a changed evidence fingerprint or a new sidecar bottleneck.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST treat released-work and learning-ledger suppression as exclusion signals when selecting the next autonomous work packet.
- **FR-002**: The system MUST distinguish `released`, `rejected`, `suppressed`, `blocked`, `new`, and `wait` states in the selected-work decision.
- **FR-003**: The system MUST derive a new evidence-source-diversification work packet when closed static candidates leave blocked validation packages or sidecar bottlenecks as the most actionable remaining evidence.
- **FR-004**: The system MUST preserve package-level traceability for blocked strategy-backtest and portfolio-backtest evidence, including candidate ID, package ID, package kind, retryability, reason class, and next safe action.
- **FR-005**: The system MUST group repeated validation failure causes while keeping the individual package references visible.
- **FR-006**: The system MUST emit a Korean next action that explains what to inspect or generate next without requiring the operator to infer the task from raw diagnostics.
- **FR-007**: The system MUST classify `PREVIEW_ONLY`, `NO_EDGE_YET`, `WAIT_EDGE`, and pending protected live workflows as safety context, not as permission to place orders.
- **FR-008**: The system MUST NOT change live arming, capital allocation, position caps, whitelist, drawdown budget, KIS secrets, audit log semantics, or production environment approvals.
- **FR-009**: The system MUST keep public reports free of account-scale, token, host, or private-key values.
- **FR-010**: The system MUST produce deterministic output for the same sidecar inputs so regressions can be tested from fixtures.
- **FR-011**: The system MUST emit a deterministic `candidate-broad-frontier-expansion-validation-failures-<fingerprint>` packet when all known candidates are closed, the original evidence-source-diversification candidate is released, and current retryable blocked validation packages remain actionable.
- **FR-012**: The system MUST emit a deterministic `candidate-broad-frontier-expansion-no-edge-<fingerprint>` packet when all known candidates are closed, no retryable blocked validation package remains, and money-path / edge-autoarm still indicate `NO_EDGE_YET`, `NO_EDGE`, `WAIT_EDGE`, `ACCUMULATING_EDGE`, or `PREVIEW_ONLY`.
- **FR-013**: The broad-frontier packet MUST widen the no-live review scope across strategy families, signal families, holding periods, asset universes, regime windows, cost sensitivity, data coverage, and execution-quality evidence while preserving the same read-only money safety boundary.
- **FR-014**: The system MUST NOT re-emit a broad-frontier packet whose exact fingerprint already appears in released-work.

### Key Entities

- **Work Candidate**: A possible autonomous work item with identity, status, score, evidence references, safety impact, and next action.
- **Released Work Entry**: Evidence that a candidate has already been completed and should not be selected again.
- **Validation Package Result**: A strategy or portfolio validation package with status, diagnostics, retryability, and package-level references.
- **Source Diversification Packet**: A synthesized work packet that turns stale, closed, or blocked evidence into a fresh candidate source improvement.
- **Safety Context**: Read-only money-path and live workflow status that constrains what the work packet may recommend.

## Success Criteria

### Measurable Outcomes

- **SC-001**: In a fixture where the top 8 ranked candidates are released and 2 validation packages are blocked, the selected work is a fresh source-diversification packet rather than any released candidate.
- **SC-002**: Blocked package diagnostics in the selected work include 100% of candidate IDs, package IDs, package kinds, retryability flags, and safe next actions from the input evidence.
- **SC-003**: The selected work report includes an explicit statement that real-money execution remains unavailable when money-path is `PREVIEW_ONLY` or forward verdict is `NO_EDGE`.
- **SC-004**: Existing release-ledger, autonomous-work, candidate-factory, and candidate-result tests continue to pass with no increase in skipped live-broker tests.
- **SC-005**: Full validation before merge passes: test suite, lint, HANDOFF fact check, strict harness, and PR quality gate.
- **SC-006**: A focused fixture with every known candidate released and two retryable blocked validation packages selects a broad-frontier expansion packet before waiting, and the same fingerprint falls back to wait only after released-work records it.
- **SC-007**: A focused fixture with every known candidate released, no retryable blocked validation package, and `PREVIEW_ONLY` / `NO_EDGE_YET` evidence selects a no-edge broad-frontier packet before waiting.

## Assumptions

- The current correct money-path state is `PREVIEW_ONLY` / `NO_EDGE_YET`; this feature does not attempt to change that state.
- The useful next work is to improve evidence generation and validation flow so future forward tournaments have better candidates.
- Existing public sidecar branches remain the operator-visible evidence surface.
- Existing SDD, PR quality, and HANDOFF rules remain mandatory for completion.

## Release Ledger

completed_candidate_id: candidate-evidence-source-diversification-validation-failures
next_candidate_id: none
