# Production Result: Calibrated Research Entry

**Measured**: 2026-08-26  
**Pre-release main**: `eed92c6c9be4048e66c8463033729370020935e6`  
**Merged main**: `42f3c54865e989a01912ece56d2eb77f3f1f8ac7`
**Factory run**: `32979548961`
**Factory sidecar**: `763ff4cd079eca4c2c13eae4a82809539dfb2b21`
**Autoarm run**: `32980657704`
**Autoarm sidecar**: `a66e2f65750d88f087108a4e4541349c3d07395d`
**KIS read-only smoke**: `32980668128`
**KIS sidecar**: `efd2ee1c07e00dda796b97560b06878b753f2ad6`

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

- PR #687 merged as `42f3c54865e989a01912ece56d2eb77f3f1f8ac7`.
- Deploy run `32979548873` synchronized and enabled the systemd units, but the worker code swap was
  correctly refused while the US market was open. The next allowed deploy was
  `2026-08-26T20:00:00Z`; `auto-invest-deploy.timer` was scheduled for
  `2026-08-26T21:00:00Z`. Therefore the worker restart is deferred, not verified complete.
- Factory run `32979548961` completed on the merge commit and published gate version `3.1`,
  752/752 unique raw rows, 17/17 reconstructed families, and current-family PBO `0.371429`.
  The consumer independently produced contract `calibrated-family-entry-v3.1`, program false
  admission bound `0.17` within budget `0.20`, and `eligible=false` with no selected candidate.
- Autoarm run `32980657704` completed with `WAIT_EDGE`, rung `0 -> 0`, no sentinel change,
  no pull request, no capital movement, and no order. It consumed the v3.1 contract and recomputed
  the same 17-family count and PBO `0.371429`.
- The same autoarm run measured NAV `$1456.75`, expected research capital `$145`, and
  `fundability_passed=false`. One SPYM share at the preview limit `$90.24` exceeded the 50%
  per-trade cap, so it was withheld as `SKIPPED_PER_TRADE_CAP`.
- KIS read-only smoke run `32980668128` checked the merge commit in an isolated checkout and passed
  5/5 live broker checks: cash `$934.27`, NAV `$1456.75`, existing external ORANY 28 shares,
  recent order/execution rows 0, and open unfilled orders 0.

## Pre-release Verification

- focused calibrated-entry suite: 60 passed
- full repository suite: 3106 passed, 5 skipped
- skipped tests: five `KIS_LIVE_TEST=1` broker integration tests only
- Ruff: all checks passed
- workflow YAML: parsed successfully with Ruby Psych
- strict agent harness: 14/14
- HANDOFF fact check: OK against `origin/main` `eed92c6`
