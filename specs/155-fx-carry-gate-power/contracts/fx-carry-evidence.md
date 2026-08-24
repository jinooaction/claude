# Contract: FX Carry Evidence

## Required identity

- Gate schema and calibration version.
- Code commit and timestamp.
- Batch, candidate, policy, strategy, data, split, and target-weight fingerprints.
- Exactly 16 complete current records and 656 unique global audit records.

## Data contract

- Spot: DEXUSAL, DEXCAUS, DEXJPUS, DEXUSUK.
- Rates: IRSTCI01AUM156N, IRSTCI01CAM156N, IRSTCI01JPM156N,
  IRSTCI01GBM156N, IRSTCI01USM156N.
- Spot age <=14 days, monthly rate age <=100 days.
- Every historical decision uses observations no later than its allowed prior-month cutoff.

## Verdict contract

- `FACTORY_EDGE`: every blocking live gate passes; one research-canary candidate may be emitted.
- `PAPER_CHALLENGER`: live gate fails only at live-grade strength, paper gates pass, capital and orders remain zero.
- `NO_FACTORY_EDGE`: no candidate is emitted.

## Broker boundary

Evidence validation rejects `PAPER_CHALLENGER`, stale or mismatched evidence, and every result without an
explicit live whitelist authorization. Rejection occurs before any broker access.

## Safety contract

This evidence cannot modify capital, sentinel arming, whitelist, caps, secrets, constitution, kernel,
orders, cancellations, or positions.
