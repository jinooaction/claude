# Feature Specification: Promote Readiness Observe Gateway

**Feature Branch**: `codex/promote-readiness-observe-gateway`; follow-up `codex/promote-readiness-gateway-self-refresh`
**Created**: 2026-07-31
**Status**: Draft
**Input**: User description: "다음 해야할 작업도 목표 스킬로 이어서 완수해줘" after the latest sidecars showed autonomous work in `OBSERVATION_WAIT` and `promote-readiness` failing with `ssh_exit=126` because the server forced-command gateway refused a raw `promote-check` command.

## User Scenarios & Testing

### User Story 1 - Publish Promotion Readiness Through the Fixed Observe Gateway (Priority: P1)

As the operator, I need the daily full-live promotion readiness report to run through the same fixed observation gateway as other read-only money evidence, so the report is published instead of being blocked by the server refusing arbitrary commands.

**Why this priority**: The current `promote-readiness` sidecar is the freshest non-trading fault: it reports `ssh_exit=126` and `refused command`, which hides whether the VI live track-record gate is merely not ready or actually broken.

**Independent Test**: Can be fully tested by checking that the workflow sends only `observe promote-readiness` over SSH and no longer sends raw `cd /opt/auto-invest && uv run ...` commands.

**Acceptance Scenarios**:

1. **Given** the production server only accepts fixed gateway commands, **When** the promotion readiness workflow runs, **Then** it sends `observe promote-readiness` and receives a readiness JSON or a not-ready exit without a refused-command error.
2. **Given** the promotion gate is not ready, **When** the observe command returns exit 1, **Then** the sidecar still publishes the JSON and marks READY false.
3. **Given** the promotion gate is ready, **When** the observe command returns exit 0, **Then** the sidecar publishes the JSON and marks READY true.

---

### User Story 2 - Preserve the Server Safety Boundary (Priority: P1)

As the operator, I need this repair to add one narrow read-only observation command without letting GitHub Actions run arbitrary shell, submit orders, change capital, or alter live configuration.

**Why this priority**: The server forced-command gateway exists to prevent exactly the kind of arbitrary remote command that the current workflow is attempting. The repair must keep that protection intact.

**Independent Test**: Can be fully tested by inspecting the gateway allowlist and helper behavior: only the exact `observe promote-readiness` command is accepted, and the helper command contains no live-order, live-arming, capital-change, systemd, shell-eval, or secret-printing behavior.

**Acceptance Scenarios**:

1. **Given** any command other than the fixed allowlist, **When** the gateway receives it, **Then** it is refused with exit 126.
2. **Given** `observe promote-readiness`, **When** the gateway receives it, **Then** it invokes only the installed observation helper with no user-provided arguments.
3. **Given** the observation helper is reviewed, **When** its allowed commands are checked, **Then** promotion readiness is read-only and does not place orders or change runtime state.

---

### User Story 3 - Self-Refresh Root-Owned Gateway Helpers During Deploy (Priority: P1)

As the operator, I need the deployed server to refresh its root-owned forced-command gateway and helper scripts from `origin/main` before the unprivileged deploy state machine runs, so a merged gateway allowlist fix is actually installed on the server without reopening arbitrary SSH command execution.

**Why this priority**: After the first fix merged, the deploy succeeded but the manual `promote-readiness` workflow still returned `ssh_exit=126` with `refused command: observe promote-readiness`. That proved the repository code was fixed, but the server's installed root-owned gateway/helpers remained stale.

**Independent Test**: Can be fully tested by checking that `auto-invest-deploy.service` runs a root-only pre-step that fetches the refresh helper from `origin/main`, and that the refresh helper only reinstalls fixed gateway/helper/sudoers files without key rotation, worker control, live arming, or capital changes.

**Acceptance Scenarios**:

1. **Given** the server has an older root-owned gateway, **When** a deploy runs after `origin/main` contains a new gateway allowlist, **Then** the deploy pre-step refreshes the gateway and helper files from `origin/main` before the normal deploy command runs.
2. **Given** the refresh helper runs, **When** it invokes the boundary repair path, **Then** it uses helper-only mode and does not require or install a deploy public key.
3. **Given** the refresh helper is reviewed, **When** its command surface is checked, **Then** it does not start the worker, arm live trading, change capital, submit orders, or edit secrets.

### Edge Cases

- The server has not yet installed the updated helper: the workflow may still get `unknown observe command`, which should be reported as setup/update drift, not as a live-money approval problem.
- The repository code has merged but the server's root-owned gateway/helper files are stale: the next deploy must refresh those files from `origin/main` before running the unprivileged deploy state machine.
- The readiness command exits 1 because the gate is not ready: the workflow must publish the JSON as a normal not-ready state.
- The readiness command emits malformed or empty JSON: the sidecar must still publish stdout/stderr so the next session can diagnose the input failure.
- A caller attempts to append arguments after `observe promote-readiness`: the gateway must reject it because the command has no variable inputs.
- The workflow is manually dispatched: it must still be report-only and must not arm, submit, allocate, or promote anything.

## Requirements

### Functional Requirements

- **FR-001**: The promotion readiness workflow MUST call the production server through the fixed command `observe promote-readiness`.
- **FR-002**: The promotion readiness workflow MUST NOT send raw shell, `cd /opt/auto-invest`, `bash -s`, or direct `/usr/local/bin/uv run auto-invest ...` commands over SSH.
- **FR-003**: The server forced-command gateway MUST allow exactly `observe promote-readiness` and continue rejecting any unrecognized or argument-bearing variant.
- **FR-004**: The observation helper MUST implement promotion readiness as a report-only command using the existing promotion readiness evaluation.
- **FR-005**: A not-ready readiness result MUST remain publishable as READY false rather than being treated as workflow infrastructure failure.
- **FR-006**: The sidecar output MUST continue to include run id, commit, trigger, timestamp, readiness value, SSH exit code, JSON output, and stderr.
- **FR-007**: The repair MUST NOT place orders, submit broker requests, arm live trading, promote to full live, change capital, change whitelist/caps, modify secrets, or mutate audit logs.
- **FR-008**: Tests MUST prove the workflow, gateway, and helper stay inside fixed-command observation boundaries.
- **FR-009**: The deploy service MUST refresh root-owned SSH gateway/helper files from `origin/main` before running the normal unprivileged deploy state machine.
- **FR-010**: The refresh path MUST run in helper-only mode and MUST NOT create users, install deploy keys, retire root keys, start or restart the worker, arm live trading, change capital, change whitelist/caps, modify secrets, or mutate audit logs.
- **FR-011**: Tests MUST prove the deploy pre-step is ordered before deployment and that the refresh helper sources the repair script from `origin/main`.

### Key Entities

- **Promotion Readiness Report**: The daily or manual result that says whether the VI live track-record gate is ready.
- **Forced-Command Gateway**: The server SSH boundary that accepts only fixed commands from GitHub Actions.
- **Observation Helper**: The root-installed helper that runs approved read-only or paper-only evidence commands as the application user.
- **Gateway Helper Refresh Step**: The root-only deploy pre-step that installs the latest fixed-command gateway and helper scripts from `origin/main`.
- **Safety Boundary**: The unchanged set of trading protections: no live arming, no order submission, no capital allocation, no whitelist/caps change, no secret exposure.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Workflow inspection finds `observe promote-readiness` and finds zero raw remote `cd /opt/auto-invest`, direct `uv run auto-invest`, or `bash -s` command strings in `promote-readiness.yml`.
- **SC-002**: Gateway tests verify exactly one new allowlisted command, `observe promote-readiness`, and verify unknown variants are still refused.
- **SC-003**: Helper tests verify promotion readiness is exposed without order submission, live arming, capital mutation, system service control, shell eval, or secret printing behavior.
- **SC-004**: Deploy service and repair tests verify stale root-owned gateway/helper files are refreshed from `origin/main` before deployment without key rotation or live-money side effects.
- **SC-005**: Full pre-merge validation passes: test suite, lint, HANDOFF fact check, strict harness, PR quality gate, and post-merge sidecar truth check.

## Assumptions

- The current `promote-readiness` failure is caused by the workflow sending a raw remote command to a server that now correctly enforces fixed commands.
- `promote-check` remains a report-only readiness evaluator; it does not perform promotion.
- The existing forced-command gateway and observation helper are the correct security boundary for this repair.
- The one-shot deploy service is the correct place to refresh root-owned gateway/helper files because it already runs after the unit sync and before the unprivileged deploy state machine.
- This work repairs observability only. It does not make the money path live and does not weaken `PREVIEW_ONLY` / `NO_EDGE_YET`.

## Release Ledger

completed_candidate_id: candidate-promote-readiness-observe-gateway
next_candidate_id: none
