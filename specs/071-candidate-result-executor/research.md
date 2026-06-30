# Research: Candidate Result Executor

## Decision: Execute by package kind, not by arbitrary shell command

**Rationale**: Candidate packages contain command strings for operator readability, but an autonomous executor should not run arbitrary text. Mapping package kinds to known handlers lets the loop remain deterministic and blocks live-order or secret-bearing paths.

**Alternatives considered**:
- Execute package command strings directly: rejected because it creates a broad shell execution surface.
- Keep result generation manual: rejected because it leaves `evidence_passed=0` as a permanent manual bottleneck.

## Decision: Conservative evidence normalization

**Rationale**: Strategy evidence should become `pass` only when a validation output clearly supports it. Missing statistics, missing data, timeouts, or unsupported output stay `pending` or `blocked`.

**Alternatives considered**:
- Treat successful process exit as full pass: rejected because a command can run successfully while still producing insufficient evidence.
- Treat missing evidence as failure: rejected because missing data is often an operational input gap rather than a strategy failure.

## Decision: Sidecar branch as the result handoff

**Rationale**: Existing loops already use automation sidecar branches. Publishing `automation/candidate-implementation-results` lets the candidate factory consume the latest result without modifying tracked main files.

**Alternatives considered**:
- Commit result JSON to main: rejected because it would create noisy state PRs for every scheduled run.
- Store only GitHub Action artifacts: rejected because later workflows cannot reliably consume them without extra API permissions.

## Decision: Non-critical liveness registration

**Rationale**: If the result executor is stale, autonomous improvement slows down but money safety remains fail-closed because no evidence means no promotion. The liveness watchdog should surface staleness without treating it as a critical trading-path outage.

**Alternatives considered**:
- Critical liveness status: rejected because this loop is not required for immediate trading safety.
