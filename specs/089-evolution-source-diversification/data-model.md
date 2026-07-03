# Data Model: Evolution Source Diversification

## ClosedStaticCandidateSignal

- `safe_open_count`: number of static candidates with status `new` or `planned`, risk grade at most 2, and no safety impact.
- `closed_count`: number of static candidates that are released, rejected, or evidence dependent.
- `ledger_decision_counts`: counts of learning ledger decisions by type.
- `promotion_failure_count`: number of promotion failure signals applied in the run.
- `stale_or_missing_evidence`: evidence keys whose freshness state is late, stale, or missing.

Validation:

- The signal is true only when `safe_open_count == 0`, no operator review or safety-impact candidate exists, and at least one static candidate exists.
- Malformed or missing ledger input must not be treated as proof of a repeated failure.

## EvidenceDerivedCandidate

- `candidate_id`: stable deterministic identifier.
- `domain_key`: expected to be `agent_ops` for this first candidate.
- `title_ko`: Korean title explaining the source diversification work.
- `problem_ko`: why the static candidate space is saturated.
- `evidence_refs`: existing evidence surfaces used to justify creation.
- `risk_grade`: expected to be 2.
- `safety_impact`: expected to be empty.
- `status`: expected to be `new` unless safety text or evidence dependency rules require otherwise.
- `next_action_ko`: SDD-oriented next action for Codex.

Validation:

- Same evidence input must produce the same candidate id and ordering.
- Candidate text must not request orders, capital changes, live strategy replacement, whitelist/caps expansion, secrets, paid services, constitution, or kernel edits.

## SourceDiversificationCompletionMarker

- `completed_candidate_id`: `candidate-evolution-source-diversification`.
- `risk_grade`: 2.
- `safety_boundary`: read-only candidate-generation change.

Validation:

- `released_work_probe.py --repo-root .` must consume the marker after tasks are checked complete.
