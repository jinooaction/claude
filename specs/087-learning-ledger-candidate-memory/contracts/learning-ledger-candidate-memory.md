# Contract: Learning Ledger Candidate Memory

## Input Contract

The autonomous evolution scan may receive:

- `learning_ledger.json`: latest `automation/autonomous-evolution-last-run:learning_ledger.json`.
- Existing evidence sidecars and `HANDOFF.md`.

## Ledger Decision Contract

When `learning_ledger.json` contains an entry for a generated candidate:

```text
decision=rejected or discard
```

The candidate must be emitted as `rejected` and must not appear in `safe_high_leverage_work`.

```text
decision=evidence_dependent, deferred, or observe
```

The candidate must be emitted as `evidence_dependent` and must not appear in `safe_high_leverage_work`.

```text
decision=operator_review
```

The candidate must be emitted as `operator_review`, must appear in operator review output, and must not appear in `safe_high_leverage_work`.

In all cases, the candidate's next action should include enough ledger reason, evidence package, or recheck-condition context for the next session to understand why the candidate did not auto-start.

## Safety Contract

This contract is read-only. It MUST NOT touch broker APIs, order submission, capital allocation, live strategy changes, whitelist/caps, secrets, paid services, constitution, or kernel manifest.

## Released-work Marker

`released-work` consumes only explicit completion markers from fully checked Speckit work. When this spec is implemented, validated, merged, and post-merge handoff is refreshed, the completed candidate is:

```text
completed_candidate_id: candidate-fa66202bf496
```
