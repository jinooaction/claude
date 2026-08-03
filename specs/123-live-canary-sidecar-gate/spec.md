# Feature Specification: Live Canary Sidecar Gate

**Feature Branch**: `codex/live-canary-sidecar-before-production-gate`
**Created**: 2026-08-03
**Status**: In Progress
**Input**: User description: "다음 해야할 것 확인하고 목표 스킬 활용해서 완수해줘" after the latest pipeline liveness report showed `rebalance-live-canary` stale because the whole live-canary workflow was waiting for production approval even when `armed=false`.

## User Scenarios & Testing

### User Story 1 - Keep Unarmed Live Canary Evidence Fresh (Priority: P1)

As the operator, I need the live canary workflow to publish a fresh dry-run preview and sidecar when the live sentinel is not armed, so pipeline liveness and capital readiness can tell whether the live-money path is healthy instead of mistaking an approval queue for fresh evidence.

**Why this priority**: The current next action is not to force real orders. It is to restore a truthful status report for the existing guarded live-canary channel, because stale sidecars hide whether the system is blocked by evidence, approval, or workflow mechanics.

**Independent Test**: Can be tested by proving the preview/status job can publish the sidecar without production approval and contains no real-order command.

**Acceptance Scenarios**:

1. **Given** the live sentinel is `armed=false`, **When** the live canary workflow runs on schedule or manual dispatch, **Then** it publishes a fresh sidecar showing dry-run preview only and zero real orders.
2. **Given** production approval is not granted, **When** the workflow is unarmed, **Then** the status sidecar still refreshes instead of remaining late.
3. **Given** the dry-run preview fails because of an external read or SSH problem, **When** the workflow publishes the sidecar, **Then** the failure is visible in the sidecar instead of being hidden behind a pending approval job.

---

### User Story 2 - Preserve the Real-Order Approval Gate (Priority: P1)

As the operator, I need any command that can place real orders to remain behind the production approval gate and the existing arming, capital, and event guards, so restoring observability never widens the money-loss surface.

**Why this priority**: The fastest safe path to money is truthful evidence plus unchanged safety gates. Removing the approval gate from real orders would solve a stale report by weakening the account boundary, which is not acceptable.

**Independent Test**: Can be tested by proving every `--mode live --confirm-live` command is absent from the preview/status job and present only in a separate real-order job that requires production approval, `armed=true`, capital not blocked, and a non-push event.

**Acceptance Scenarios**:

1. **Given** the sentinel is `armed=false`, **When** the workflow runs, **Then** the real-order job is skipped and no broker order command runs.
2. **Given** the sentinel is `armed=true` on a push event, **When** the workflow runs, **Then** the real-order job is skipped because a sentinel merge must not place orders.
3. **Given** the sentinel is `armed=true` on a schedule or manual dispatch and capital is allowed, **When** production approval is granted, **Then** only the real-order job may run the live order command.

---

### User Story 3 - Make the Sidecar Meaning Unambiguous (Priority: P2)

As the operator or next Codex session, I need the sidecar to distinguish "preview refreshed" from "real orders executed", so a fresh status report is not confused with a trade.

**Why this priority**: A live-money status surface that is fresh but ambiguous can cause the next session to make the wrong decision about whether money moved.

**Independent Test**: Can be tested by reading the generated sidecar text and workflow tests: preview output must say the real-order job is production-gated, and production output must be the only path that reports real-order execution.

**Acceptance Scenarios**:

1. **Given** the preview/status job publishes the sidecar, **When** a reader inspects `LIVE 스텝`, **Then** it says the preview job skipped real orders and that real orders are handled by the production-gated job.
2. **Given** a production-approved real-order job completes, **When** it publishes the sidecar, **Then** it overwrites the preview sidecar with the actual live rebalance result and after-order live measurement.

### Edge Cases

- If `armed=true` but production approval is pending, the preview/status job must not take a live NAV snapshot that could be mistaken for an after-order measurement.
- If the capital guard blocks the run, the status sidecar must publish the blocked state and the real-order job must not run.
- If the event is `push`, real orders must remain skipped even when the sentinel text says `armed=true`.
- If a production-approved real-order job fails, the production sidecar must make the failure visible instead of leaving only the preview sidecar.
- If the workflow YAML is edited later, tests must fail if a real-order command reappears in the preview/status job.

## Requirements

### Functional Requirements

- **FR-001**: The live canary workflow MUST have a preview/status path that can refresh the latest run sidecar when the sentinel is not armed.
- **FR-002**: The preview/status path MUST NOT contain or execute any real-order command.
- **FR-003**: The real-order path MUST require all of these before any live order command can run: `armed=true`, capital guard not blocked, non-push event, and production approval.
- **FR-004**: The preview/status path MUST publish sidecar text that clearly says it is a preview-only run and that real orders are owned by the production-gated path.
- **FR-005**: The real-order path MUST publish the actual live rebalance result and after-order live measurement if it runs.
- **FR-006**: The preview/status path MUST skip live-track measurement when `armed=true`, so an approval-pending run cannot write a pre-order measurement as if it followed real orders.
- **FR-007**: The change MUST NOT alter capital ladder authority, whitelist/caps, strategy fingerprint gates, live sentinel semantics, secrets, audit logs, broker order code, or account capital allocation.
- **FR-008**: Automated tests MUST prove the preview/status path is not production-gated, the real-order path is production-gated, and the real-order command exists only in the real-order path.
- **FR-009**: Post-merge verification MUST refresh the live canary sidecar while `armed=false` and then refresh pipeline liveness or equivalent evidence to confirm `rebalance-live-canary` is no longer late.

### Key Entities

- **LiveCanaryPreviewRun**: A workflow run segment that reads the live sentinel, runs dry-run preview/status checks, and publishes the latest sidecar without placing real orders.
- **RealOrderGate**: The separate production-approved workflow segment that is the only place where live order commands may run.
- **LiveCanarySidecar**: The `automation/rebalance-live-canary-last-run` report that records whether the latest run was preview-only or production-approved real execution.
- **Arming Sentinel**: The existing request file that says whether live canary orders are armed and how much capital is authorized.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Focused workflow tests prove the preview/status job contains sidecar publication, contains no `--mode live --confirm-live`, and has no production approval gate.
- **SC-002**: Focused workflow tests prove the real-order job depends on the preview/status job, requires `armed=true`, blocks push events, keeps production approval, validates capital, and contains the only `--mode live --confirm-live` command.
- **SC-003**: Full local validation passes: focused tests, pipeline-liveness/readiness tests, full `pytest`, `ruff`, strict harness, HANDOFF fact check, and diff whitespace check.
- **SC-004**: After merge, a main-branch live canary run refreshes the sidecar with `armed=false`, preview-only wording, and zero real orders.
- **SC-005**: After sidecar refresh, pipeline liveness no longer reports `rebalance-live-canary` as late unless a new unrelated freshness threshold has failed.

## Assumptions

- The latest observed live sentinel remains `armed=false`; the task is to repair observability, not to arm live trading.
- The stale `rebalance-live-canary` report is caused by job-level production approval blocking the whole workflow before sidecar publication.
- Dry-run preview and read-only status checks are acceptable outside production approval only because they do not submit broker orders.
- Real order execution remains an explicit production-approved path; this feature does not grant permission to approve or force that job.
- Workflow dispatch after merge is safe while `armed=false`, because the real-order job's own conditions skip it.

## Release Ledger

completed_candidate_id: candidate-live-canary-sidecar-gate
next_candidate_id: none
