# Research: Learning Ledger Candidate Memory

## Decision: Reuse the existing learning ledger

**Rationale**: Spec 067 created `learning_ledger.json` as durable memory for autonomous candidates, and spec 075 already uses it for rejected decisions. Reusing it avoids a second state file and keeps all not-yet-released candidate memory in one place.

**Alternatives considered**:

- Add a new review ledger sidecar: rejected because it would split candidate memory and make autonomous-work input reconciliation harder.
- Patch candidate backlog directly: rejected because backlog is an output, while the ledger is the intended durable input.

## Decision: Conservative suppression for hold/review decisions

**Rationale**: A ledger entry with `evidence_dependent`, `deferred`, `observe`, or `operator_review` means the system already learned a reason not to auto-start the candidate. The safest default is to keep it out of `safe_high_leverage_work` until a later run explicitly changes or removes that ledger decision.

**Alternatives considered**:

- Automatically parse Korean recheck conditions: rejected because free-text condition evaluation would be brittle and could accidentally re-enable held work.
- Ignore hold entries and only suppress rejected: rejected because this is the current gap that caused repeated rediscovery.

## Decision: Keep released-work separate

**Rationale**: `released-work` means an implemented Speckit task is shipped. `learning_ledger` means a candidate is rejected, held, or needs review. Keeping the two meanings separate preserves the current completion model.

**Alternatives considered**:

- Treat all ledger entries as released work: rejected because evidence-dependent and operator-review candidates are not shipped.
