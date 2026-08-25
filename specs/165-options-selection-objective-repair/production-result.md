# Production Result: Options Selection and Objective Repair

## Frozen Local Replay

- Code commit: `90bc4477a567c8fcf88aef3e25c3fa06eb6b08f7`
- Replay timestamp: `2026-08-26T00:00:00Z`
- Source window: 2007-03 through 2026-06, 232 aligned months
- Freshness: PUT 1 day, WPUT 1 day, VIX 2 days, French factors 57 days, FRED cash 2 days
- Trials: 16 current, 736 prior, 752 cumulative unique fingerprints
- Nested evaluation: 12 outer 12-month folds; at least two inner folds per outer fold; chronology violations 0
- Independent source: WPUT was never used for selection, thresholds, or tie-breaking
- Verdict: `NO_CROSS_INDEX_PREMIUM`
- Diagnosis: `CROSS_INDEX_PREMIUM_NOT_CONFIRMED`
- Exact replay SHA-256: `5b95166184a6ca4f61a8d5fb8f830f3f2d5de38feda5381061d748f1a50d9c0d`
  for both independent executions

## Separated Objectives

| Objective | PUT | WPUT | Cross-index result |
|---|---:|---:|:---:|
| Premium existence: annual cash excess | 4.812579% | 0.536821% | FAIL |
| Premium existence: PSR vs cash | 0.954087 | 0.638860 | FAIL |
| Portfolio adoption: annual cash excess | 2.312035% | 0.476446% | FAIL |
| Portfolio adoption: Sharpe improvement | +0.036908 | -0.322830 | FAIL |
| Timing: annual excess vs passive | -1.199857% | -0.193512% | FAIL |
| Timing: Sharpe improvement vs passive | -0.173479 | +0.047806 | FAIL |

Monthly PUT therefore confirms a cash premium on its own. The weekly WPUT construction does
not confirm the preregistered 2% annual premium or 0.95 PSR thresholds, and the timing layer
loses to matching passive exposure on both constructions.

## Selection Stability

- Portfolio selector: passive PUT in the first seven outer folds, then fixed ridge in five.
- Timing selector: positive-VRP policy in eight outer folds, then fixed ridge in four.
- The same candidate IDs and monthly weights were replayed on WPUT.
- Mutating the complete WPUT path in tests did not change any PUT-selected ID or weight.
- The released spec-164 winner and verdict remain under `legacy_selection`; no prior result was rewritten.

## Safety

- `research_canary_eligible=false`
- `paper_forward_eligible=false`
- `promotion_allowed=false`
- Broker calls, orders, capital, margin, caps, arming, whitelist, constitution, and kernel changes: 0
- PUT/WPUT are hypothetical benchmark indexes; exact option execution parity remains false.

## Evidence Files

- Canonical JSON: `/tmp/spec165-production-90bc447/strategy_factory.json`
- Human summary: `/tmp/spec165-production-90bc447/LAST_RUN.md`
- Full 752-trial replay inputs and intermediate outputs: `/tmp/spec165-production-90bc447/`
