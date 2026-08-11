# Research: Validation Failure Command Replay Contract

## Decision: Build a read-only contract instead of replaying commands

**Rationale**: The selected candidate asks for a command replay contract, not live command execution. Current sidecars may lack execution rows, and inventing exit codes would make the next diagnosis worse. A read-only contract can honestly record the command, safety scope, and missing execution evidence.

**Alternatives considered**:
- Blindly re-run candidate commands: rejected because the next candidate is a contract and because current missing history roots may produce environment-dependent failures.
- Extend candidate-result executor to always run again: rejected because that changes execution behavior rather than closing the command-replay diagnosis.

## Decision: Reuse candidate-result command safety rules

**Rationale**: The candidate-result executor already owns the allowlist and unsafe fragments for no-live validation commands. Reusing that rule avoids a second, drifting safety policy.

**Alternatives considered**:
- Duplicate allowlist strings in the new module: rejected because duplicated safety policy drifts.
- Treat package status as enough for safety: rejected because command-level live fragments must still block replay.

## Decision: Mark command replay complete through spec 127

**Rationale**: The autonomous-work loop already advances to data-readiness when `candidate-broad-validation-failure-command-replay-contract` is released. Adding the completion marker lets released-work drive the next child candidate without bespoke state.

**Alternatives considered**:
- Add a new state file outside SDD: rejected because released-work already scans completed SDD artifacts.
