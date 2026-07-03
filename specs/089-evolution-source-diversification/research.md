# Research: Evolution Source Diversification

## Decision: Generate evidence-derived candidates after ledger application

**Rationale**: The selected macro work exists because the static backlog is already exhausted downstream. Generating candidates before ledger and promotion failure application would be misleading because stale static candidates would still appear actionable.

**Alternatives considered**:

- Add more fixed templates: rejected because it repeats the same saturation failure.
- Generate candidates in `autonomous_work_execution.py`: rejected because that loop consumes upstream backlog; source diversification belongs in the producer.

## Decision: Use only existing read-only evidence

**Rationale**: The feature is risk grade 2 and must stay inside the existing safety perimeter. Existing sidecars already expose enough signals: learning ledger, promotion failures, pipeline liveness, released-work saturation, and capital-path observability.

**Alternatives considered**:

- Query GitHub Actions or broker APIs directly: rejected because it would add external calls and extra failure modes.
- Use LLM-generated candidate discovery: rejected because this repo's current autonomous loop is deterministic and no new judgment point is needed.

## Decision: Keep synthesized candidates subordinate to live actionable static candidates

**Rationale**: If a normal safe candidate still exists, the operator already has an actionable next step. Source diversification is valuable when the fixed candidate set is closed, not when it would distract from live work.

**Alternatives considered**:

- Always add the synthesized candidate: rejected because it would create queue noise and could mask simpler work.
- Suppress it forever once one static candidate exists: rejected because it would not solve the closed-queue failure mode.
