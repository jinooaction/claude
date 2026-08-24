# Contract: Commodity Term Structure Evidence

## Identity

The payload must bind gate/calibration version, code commit, candidate, strategy, source, data, split, target
weights, family objective, 16 complete current records, and 672 unique global audit records.

## Data

BlackRock must identify portfolio 239757, ticker GSG, 240 monthly fund and benchmark points, benchmark
S&P GSCI Total Return, and a common last month no older than 62 days. World Bank must identify the Monthly
Indices sheet, Total Index column, August 2026 update, and the same last common month.

## Verdict

`FACTORY_EDGE` requires every live blocking gate. `PAPER_CHALLENGER` requires every paper gate but cannot
cross the broker boundary. Every other result is `NO_FACTORY_EDGE`.

## Safety

The probe cannot import or call broker clients. Evidence cannot modify capital, orders, cancellations,
positions, whitelist, caps, secrets, live arming, constitution, or kernel.

