# Production Result: Independent Options Variance Risk Premium

## Frozen Local Replay

- Source window: 2007-03 through 2026-06, 232 aligned months
- Split: 84 development, one embargo, 147 untouched holdout months
- Trials: 16 current, 736 prior, 752 cumulative unique fingerprints
- Frozen winner: `options-vrp-tail_guarded-7a1729980754`
- Verdict: `GATE_OR_REFERENCE_SUSPECT`
- Diagnosis: `ECONOMIC_PREMIUM_EXISTS_BUT_ADOPTION_GATE_OVERCONSTRAINED`

## Selected Candidate

- Cash-excess PSR: 0.803758
- Annual cash excess after middle costs: 0.662141%
- Sharpe improvement versus broad equities: 0.039261
- Maximum drawdown: 6.427959% versus 24.899519%
- Monthly 95% expected shortfall: -2.166609% versus -8.950168%
- Paper gate: pass
- Live gate: fail on PSR, annual cash excess, and Sharpe improvement
- Timing enhancement versus matching passive PUT: fail

## Gate Audit

- Full PUT annual cash excess: 5.177143%
- Full PUT cash-excess PSR: 0.964744
- Full PUT drawdown and expected shortfall: both better than broad equities
- Full PUT adoption failure: Sharpe improvement -0.124261
- Mean-zero null: rejected
- Synthetic null false acceptance: 2.4%
- Synthetic planted-edge detection: 81.6%
- Synthetic correct selection: 83.8%

The statistics machinery is passable, but the reference test mixes premium existence with
portfolio adoption. The system now reports both diagnoses while preserving the original
gate result. Post-hoc live passes remain non-promotable.

## Safety

`research_canary_eligible=false`. No broker, order, capital, margin, cap, arming,
whitelist, constitution, or kernel change was made.

## Main Production Closure

- Merge: PR #682, main `2141a7c972cf3a125a3b7bd0801d73b5d76ce4ed`
- Strategy factory: run `32897412078`, success, 16/16 current and 752/752 unique
- Production verdict: `GATE_OR_REFERENCE_SUSPECT`
- Production diagnosis: `ECONOMIC_PREMIUM_EXISTS_BUT_ADOPTION_GATE_OVERCONSTRAINED`
- Deploy: run `32897412147`, success
- KIS read-only smoke: run `32898262246`, 5/5 success on main `2141a7c`
- KIS state: cash $934.27, NAV $1454.23, external ORANY 28 shares, recent/open orders 0
- Money path: `PREVIEW_ONLY`, `ACCUMULATING_EDGE`, rung 0/5, capital $0,
  forward evidence 0/20, real-order submission false
