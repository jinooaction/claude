# Research: Micro GTAA Intent-Loss Gate

## Decision: Block on latest `INTENT_LOSS` as well as `STRATEGY_REVIEW`

**Rationale**: The operator's concern is not only statistically confirmed strategy decay. The latest real-money intent would have been immediately loss-making at the mark, and the system should not repeat that live attempt just to gather more samples. Blocking on `INTENT_LOSS` is conservative and exposure-reducing.

**Alternatives considered**:

- Wait for `STRATEGY_REVIEW` only: rejected because it would allow at least one more real-money attempt after a known loss-direction signal.
- Block only after two negative streaks: rejected for the same reason; this is appropriate for strategy review classification, not live-money protection.

## Decision: Disarm sentinel immediately

**Rationale**: The next scheduled micro GTAA run can reach the live order path if the sentinel remains armed. Setting `armed:false` is the fastest reversible safety action.

**Alternatives considered**:

- Rely only on the new workflow gate: rejected because a workflow bug or deploy delay would leave the sentinel armed.
- Delete the workflow schedule: rejected because it also removes dry-run observability and is harder to reverse cleanly.

## Decision: Do not append opportunity history when live did not run

**Rationale**: A skipped or blocked run produces no rejected order to value. Appending a zero-valued fallback would make the latest signal look flat and could clear the new live gate accidentally.

**Alternatives considered**:

- Append a `NO_VALUED_REJECTIONS` record for every run: rejected because it changes the semantics from "latest live attempt signal" to "latest workflow signal".
- Store a separate blocked-run history: deferred; the sidecar already records the gate decision in `LAST_RUN.md`.
