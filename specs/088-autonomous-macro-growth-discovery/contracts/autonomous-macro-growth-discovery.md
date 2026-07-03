# Contract: Autonomous Macro Growth Discovery

## Input Contract

The autonomous work execution loop may receive the existing sidecar evidence:

- `capital-path-readiness`
- `evolution-backlog`
- `evolution-ledger`
- `autonomous-promotion`
- `candidate-implementation-factory`
- `candidate-packages`
- `candidate-result-executor`
- `released-work`
- `pipeline-liveness`

No new external service, broker call, paid data source, secret, or database is introduced.

## Closed Queue Contract

The loop may synthesize a macro-growth candidate only when all conditions are true:

1. No regular packet has `status=EXECUTION_READY`.
2. No regular packet has `status=OPERATOR_APPROVAL_REQUIRED`.
3. No regular packet has `status=BLOCKED`.
4. Every remaining regular packet is `RELEASED` or `SUPPRESSED`, or no regular candidate packet exists while liveness evidence is present.
5. The candidate to emit is not already listed as released by released-work.

When a normal execution-ready, approval-required, or blocked packet exists, the macro-growth candidate must not be emitted.

## Output Contract

The first unreleased macro-growth candidate must be emitted as a normal `WorkPacket` with:

```text
status: EXECUTION_READY
autonomy_level: CODEX_AUTONOMOUS_START
risk_grade: 2
domain_key: agent_ops
work_type: agent_operating_system
```

The initial ordered candidates are:

```text
candidate-macro-growth-discovery
candidate-evolution-source-diversification
candidate-autonomous-growth-objective-calibration
```

## Safety Contract

This contract is read-only. It MUST NOT touch broker APIs, order submission, capital allocation, live strategy changes, whitelist/caps, secrets, paid services, constitution, or kernel manifest.

## Released-work Marker

`released-work` consumes only explicit completion markers from fully checked Speckit work. When this spec is implemented, validated, merged, and post-merge handoff is refreshed, the completed bootstrap candidate is:

```text
completed_candidate_id: candidate-macro-growth-discovery
```
