# Research: Strategy Failure Learning

## Decision: Use autonomous promotion summary as the failure source

**Rationale**: The promotion loop is already the layer that decides `DISCARD` after candidate factory and result executor evidence. It has the final machine-readable assessment and candidate id.

**Alternatives considered**:
- Parse candidate factory LAST_RUN only: rejected because factory knows `blocked` but not final promotion stage ordering.
- Parse result executor only: rejected because result executor reports raw package results, not promotion-stage consequences.
- Add manual handoff parsing: rejected because handoff is explanatory text, not the source of truth for automation.

## Decision: Store failures in the existing learning ledger

**Rationale**: Spec 067 already defines `learning_ledger.json` as the durable memory preventing repeated rejected candidates. Reusing it avoids a second state file and keeps candidate suppression in one place.

**Alternatives considered**:
- Add a new `strategy_failures.json`: rejected because it splits learning memory and creates reconciliation work.
- Patch candidate backlog directly: rejected because backlog is an output, while ledger is the intended memory input.

## Decision: Fail open when promotion summary is missing or malformed

**Rationale**: A missing sidecar should not stop autonomous evolution from publishing other candidates. It should only skip external failure learning for that run.

**Alternatives considered**:
- Block the workflow: rejected because this loop is not an immediate trading safety gate.
- Treat malformed JSON as empty but mark overall blocked: rejected because it overstates risk for a read-only learning input.

## Decision: Record source reference as promotion evidence package id

**Rationale**: The ledger entry needs enough provenance for future sessions to reproduce why the candidate was rejected. `autonomous-promotion:<run_id>` is stable, readable, and does not require a new schema.

**Alternatives considered**:
- Store full assessment JSON inside the ledger: rejected because it bloats a compact memory file.
- Store no evidence package id: rejected because it makes future audit harder.
