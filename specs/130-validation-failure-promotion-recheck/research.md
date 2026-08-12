# Research: Validation Failure Promotion Recheck Contract

## Decision: Treat promotion recheck as a read-only contract, not a rerun

**Rationale**: The selected candidate asks for conditions that allow a failed candidate to be reconsidered. Running validation commands or reopening candidates inside this change would cross into behavior with larger blast radius. A read-only contract records the rule first.

**Alternatives considered**: Directly rerun candidate-result packages. Rejected because the previous child contracts already separated command replay, data readiness, and package kind; this step is about the recheck gate, not execution.

## Decision: Use the latest learning-ledger entry per candidate

**Rationale**: `candidate-cc96b35062da` has an older evidence-dependent ledger entry and a newer rejected entry. The current operating decision must follow the latest entry, while historical recheck text remains useful context.

**Alternatives considered**: Any historical recheck condition reopens the candidate. Rejected because a newer rejection can supersede it.

## Decision: Fingerprint stable failure evidence

**Rationale**: Promotion sidecar run ids can change without the actual candidate failure changing. The contract fingerprints package id, package kind, promotion diagnostics, result status, validation layer status, metric highlights, and execution digests instead.

**Alternatives considered**: Use promotion run id as freshness. Rejected because it would falsely reopen the same suppressed candidate every time the sidecar is regenerated.

## Decision: Keep current candidates suppressed

**Rationale**: Current evidence still says both candidate-results are `fail`, promotion stage is `DISCARD`, and the latest ledger entries have no explicit recheck condition. The correct action is to keep suppression active while recording what must change.

**Alternatives considered**: Reopen because one deep walk-forward output includes a positive long-horizon hint. Rejected because the candidate-result package still fails the current machine-readable validation layers.
