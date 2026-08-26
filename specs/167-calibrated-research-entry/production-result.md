# Production Result: Calibrated Research Entry

**Measured**: 2026-08-26  
**Pre-release main**: `eed92c6c9be4048e66c8463033729370020935e6`  
**Factory sidecar**: `f7bbacad925ab5b06c5c4520f7db7164536d877c`  
**Autoarm run**: `32973803207`

## Independent Audit

| Item | Result |
|---|---:|
| Raw cumulative candidates | 752 |
| Classified raw candidates | 752 |
| Unclassified candidates | 0 |
| Reconstructed research families | 17 |
| Current options candidates | 16 |
| Current options PBO | 0.371429 |
| New PBO maximum | 0.25 |
| Current research eligibility | false |
| Orders caused by audit | 0 |
| Capital change caused by audit | 0 |

The 17-family reconstruction is 4 legacy factory batches, 3 exploration batches, macro,
treasury, credit, FX, commodity term structure, commodity positioning, commodity supply-demand,
USDA crop, energy cross-market, and options variance-risk premium.

## Calibration

Frozen seed 60,000 and 500 repetitions:

| Family size | Null admission | Planted Sharpe 0.60 detection | Requirement |
|---:|---:|---:|---|
| 16 | 0.010 | 0.840 | <= 0.01 and >= 0.80 |
| 64 | 0.004 | 0.804 | <= 0.01 and >= 0.80 |

The prior simultaneous DSR/PBO/raw-Bonferroni blockers detected only about 42% and 36% of the same
planted edge for 16 and 64 candidates. The repaired hard gate preserves the measured null ceiling
while recovering the preregistered 80% detection target.

## Current Candidate Verdict

The current options family remains rejected independently of the removed blockers:

- PBO 0.371429 exceeds 0.25.
- No selected promotion candidate or deploy configuration exists.
- Historical samples are reused and public history is not point-in-time promotion evidence.
- Benchmark execution and research-live execution are not equivalent.
- Exact 10% current-NAV fundability fails.

This proves the threshold repair is not fitted to make the current family pass.

## Separate Operational Constraint

The successful read-only autoarm run measured account NAV `$1456.75`, so rung 1 is about `$145`.
At current SPYM/GLDM prices near `$90`, whole-share routing plus the 50% per-trade cap cannot fund
even one share without violating the cap, and the two-leg target cannot meet weight-error limits.
This is not a statistical failure. It is a small-account execution-design constraint and should be
the next independent priority after the calibrated gate is deployed.

## Post-release Evidence

To be filled after merge and deployment:

- merged main commit
- deployment run and worker restart
- new factory sidecar v3.1 family count and PBO
- new autoarm sidecar action/rung/fundability
- broker smoke order count and open-order count

## Pre-release Verification

- focused calibrated-entry suite: 60 passed
- full repository suite: 3106 passed, 5 skipped
- skipped tests: five `KIS_LIVE_TEST=1` broker integration tests only
- Ruff: all checks passed
- workflow YAML: parsed successfully with Ruby Psych
- strict agent harness: 14/14
- HANDOFF fact check: OK against `origin/main` `eed92c6`
