# Research: Frontier Candidate Discovery

## Decision 1: Emit one frontier discovery candidate after known queues are closed

**Decision**: Add `candidate-autonomous-frontier-discovery` as a deterministic generated work packet when regular candidates and existing macro-growth candidates are all closed.

**Rationale**: The current sidecar can end with `ranked_work=0` and a released candidate in `selected_work`, which invites duplicate work. A single frontier candidate makes the next action explicit without inventing several unvalidated domain candidates.

**Alternatives considered**:

- Add more static macro templates indefinitely. Rejected because it repeats the fixed-template saturation problem.
- Return `selected_work=null`. Rejected because it leaves the operator without a concrete next Codex task.
- Re-rank released candidates lower only. Rejected because the loop still needs a new executable packet.

## Decision 2: Preserve existing macro-growth order before frontier discovery

**Decision**: Keep specs 088, 089, and 091 macro candidates first. Frontier discovery is emitted only after all existing macro candidates are released or already present.

**Rationale**: Those macro candidates were intentionally sequenced. Frontier discovery is a fallback after the sequence is exhausted, not a replacement for it.

**Alternatives considered**:

- Always emit frontier discovery when the regular queue closes. Rejected because it would skip unreleased macro work.

## Decision 3: Treat blocked and operator-approval candidates as stronger than frontier discovery

**Decision**: Do not emit frontier discovery when a blocked or operator-approval candidate exists.

**Rationale**: Safety and missing-input gates are not "no work"; they are explicit stop states. A frontier candidate must not hide them.

**Alternatives considered**:

- Emit frontier discovery alongside blocked candidates. Rejected because `selected_work` could become ambiguous and mask a safety stop.

## Decision 4: Close the candidate through released-work after implementation

**Decision**: Add `completed_candidate_id: candidate-autonomous-frontier-discovery` in this spec's contract once tasks are complete.

**Rationale**: This follows the repo's completion ledger pattern and prevents this same frontier candidate from being selected again after the implementation ships.

**Alternatives considered**:

- Suppress by hard-coded ID after merge. Rejected because released-work is the reusable source of truth for completed candidates.
