# Research Decisions: Family Complete V3 and Fundability

## Decision 1: Recompute from raw rows

- **Decision**: Count and validate `audit_records` and `trial_records` inside the consumer.
- **Rationale**: Re-reading producer gate booleans does not create an independent safety boundary.
- **Alternatives considered**: Sign producer JSON only. A signature proves origin, not correctness.

## Decision 2: Use global Bonferroni when dependence cannot be reconstructed

- **Decision**: Compute `min(1, (1 - selected_psr) * global_unique_trials)` and require at most 0.05.
- **Rationale**: The 752 strategies reuse historical periods and the sidecar lacks all aligned return
  vectors needed for a defensible global effective-trial estimate. Raw-count Bonferroni is conservative,
  transparent, and independently reproducible.
- **Alternatives considered**: Keep family-only DSR, which ignores sequential searching; or infer an
  effective count from heterogeneous summary metrics, which would be less defensible than the raw count.

## Decision 2A: Recompute family DSR and PBO from matrices

- **Decision**: Publish the aligned current-family development return matrix and an even eight-segment
  score matrix. The consumer recomputes effective trials, DSR, and PBO and requires exact agreement
  with the producer. Selected PSR must equal the selected raw trial row.
- **Rationale**: The prior options producer used seven segments with a PBO function that accepts only
  an even segment count, so PBO was mechanically `None` for every result. Trusting the producer's
  summary would preserve that impossible gate.
- **Alternatives considered**: Remove PBO or accept a producer number. Both hide the calculation error
  instead of making the criterion independently reproducible.

## Decision 3: Make data and execution parity blocking

- **Decision**: Require non-reused point-in-time data and exact benchmark-to-live execution parity.
- **Rationale**: A statistically strong index result is not an orderable strategy if the data or instrument
  available to the live account differs.
- **Alternatives considered**: Treat parity as diagnostic and rely on the hardened canary. That can test
  code but cannot manufacture missing historical execution equivalence.

## Decision 4: Measure fundability with the live planner

- **Decision**: Reuse the existing order planner and cap logic, then compare projected post-order weights
  with the signal target at the proposed capital.
- **Rationale**: A separate approximate calculator would drift from actual lot rounding, minimum notional,
  symbol mapping, and cap behavior.
- **Alternatives considered**: Minimum-capital formula from current prices. It cannot capture uneven target
  weights, trend-scaled legs, current holdings, or order caps.

## Decision 5: Gate only upward exposure

- **Decision**: Require fundability for rung 0 to rung 1 and before the first strategy fill. Existing fills
  continue through the live risk and reconciliation gates.
- **Rationale**: A new upward gate must not block exits, demotions, halts, or risk-reducing trades.
- **Alternatives considered**: Require it on every live order, which could trap an existing position when
  the portfolio becomes temporarily hard to express.
