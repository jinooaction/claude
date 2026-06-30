# Research: Candidate Evidence Diagnostics

## Decision: Diagnostics are additive result metadata, not new promotion evidence

**Rationale**: A diagnostic explains why evidence is pending or blocked. It must not change the semantics of `pass`, `fail`, `pending`, or `blocked`, otherwise the loop could accidentally promote a candidate because the error classification improved.

**Alternatives considered**:
- Convert known operational gaps directly to `pass`: rejected because missing data or bad command contracts are not strategy evidence.
- Store diagnostics only in Markdown: rejected because downstream automation needs machine-readable fields.

## Decision: Classify common failure output by stable codes

**Rationale**: Current pending rows already contain bounded stderr excerpts. Stable codes such as `data_history_missing`, `command_contract_error`, and `insufficient_pass_evidence` let the next loop choose a safe remediation path without regexing prose.

**Alternatives considered**:
- Keep only Korean free text: rejected because it is not reliable as an automation contract.
- Preserve full raw logs: rejected because logs may be noisy, large, or sensitive.

## Decision: Carry diagnostics into candidate factory promotion evidence

**Rationale**: Promotion scan consumes enriched candidate backlog, not the raw result sidecar. If diagnostics stay only in `candidate_results.json`, the next loop still sees a generic pending stage.

**Alternatives considered**:
- Have promotion loop read result sidecar directly: rejected for this slice because factory is already the merge point between package results and candidate backlog.
- Add a separate diagnostics sidecar branch: rejected because it splits one evidence contract across multiple branches.

## Decision: Keep next actions declarative and no-live

**Rationale**: Next actions should help the system choose the next safe work item, not perform real money actions. Data ingestion, package command repair, or output contract hardening may become future loops, but this feature only publishes the action plan.

**Alternatives considered**:
- Auto-run missing data ingestion from diagnostics: rejected for this slice because it changes execution scope and needs separate safety review.
- Auto-edit candidate package commands: rejected because the factory command templates need explicit tests before mutation.

## Decision: Treat unsupported or unsafe surfaces as blocked and non-retryable

**Rationale**: Unknown package kinds and live-order command fragments are not evidence gaps; they are outside the autonomous executor boundary. Marking them retryable would encourage repeated unsafe attempts.

**Alternatives considered**:
- Mark unsafe command as pending: rejected because it blurs safety boundary violations with ordinary missing inputs.
