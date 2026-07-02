# Contract: Agent Ops Liveness Closure

## Input Contract

The autonomous evolution scan may receive:

- `pipeline-liveness.md`: the latest `automation/pipeline-liveness-last-run:LAST_RUN.md`.
- `handoff.md`: the current main-branch `HANDOFF.md`.

## Completion Contract

`candidate-88a7e7f07361` is complete when:

```text
pipeline-liveness contains key autonomous-evolution with status OK
handoff contains the session entrypoint and /sync route
```

When complete:

- The candidate status is `released`.
- The candidate does not appear in `safe_high_leverage_work`.
- The next action explains that liveness registration and handoff entrypoint already exist.

When incomplete:

- The candidate remains actionable.
- The next action continues to point at restoring liveness registration or handoff entrypoint.

## Downstream Race Contract

Promotion and candidate-factory automation may start at the same time as autonomous-evolution and released-work after a push to `main`. They must therefore generate or consume released-work evidence for the current checkout before acting on stale automation sidecar candidates.

When `released-work` contains `candidate-88a7e7f07361`:

- Promotion assessment stage is `DISCARD`.
- Candidate factory emits no package for this candidate.
- Candidate result executor has no new package for this candidate to execute.

## Safety Contract

This contract is read-only. It MUST NOT touch broker APIs, order submission, capital allocation, live strategy changes, whitelist/caps, secrets, paid services, constitution, or kernel manifest.

## Released-work Marker

`released-work` consumes only explicit completion markers from fully checked Speckit work. When this spec is merged and post-merge handoff is refreshed, the completed candidate is:

```text
completed_candidate_id: candidate-88a7e7f07361
```
