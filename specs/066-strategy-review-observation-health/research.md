# Research: Strategy Review Observation Health

## Decision: Treat all-pre-minimum lag as progress metadata, not degraded input

**Rationale**: When every known track is still below `min_obs`, no track is comparable yet. A lower `n_obs` on a newly added candidate such as `globalfixed` does not make the current comparison incomplete; the whole tournament is still accumulating observations. Marking this as `DEGRADED` blocks reassignment for the wrong reason and hides the true state: no comparable challenger exists yet.

**Alternatives considered**:

- Keep any 2-observation lag as `DEGRADED`: rejected because it produced the current false blocker while all tracks were premature.
- Remove lag tracking entirely: rejected because operators still need to see late-start or stalled candidates.

## Decision: Degrade when comparable and below-minimum tracks coexist

**Rationale**: Once at least one candidate reaches `COMPARABLE`, a known candidate below minimum observations means the candidate set is partially mature. Strategy reassignment should not treat that as a clean comparison because it can select among an incomplete field.

**Alternatives considered**:

- Always keep known lagging tracks as `OK`: rejected because it can allow window-shopping when some candidates are comparable and others are not.
- Block instead of degrade: rejected because incumbent verdict and some tournament evidence are still readable; this is input-quality degradation, not total inability to compare.

## Decision: Preserve `lagging_keys` under `OK`

**Rationale**: Health status and forensic visibility solve different problems. `observation_health` answers whether the board is usable by the strategy-review loop; `lagging_keys` shows which tracks have fewer observations. Keeping both prevents a binary status from hiding operational drift.

**Alternatives considered**:

- Clear `lagging_keys` when status is `OK`: rejected because it would erase the exact evidence the operator asked to understand.
