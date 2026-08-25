# Spec 163 First Frozen Current-Data Result

## Verdict

- Run timestamp: `2026-08-25T00:00:00Z`
- Batch ID: `energy-cross-market-99632bcc8d67`
- Verdict: `NO_FACTORY_EDGE`
- Criterion diagnosis: `OBJECTIVE_GATE_PASSABLE_CANDIDATE_UNCONFIRMED`
- Current family trials: 16 complete and unique
- Cumulative audit: 736 complete and unique
- Orders, capital, caps, arming, whitelist, constitution, and kernel changes: 0

This is the first frozen local replay against the preregistered spec-163 grammar. The
production workflow must reproduce it from the merge commit before its sidecar is the
authoritative current result.

Post-analysis consistency note: FR-014 was corrected after this replay to describe the
already frozen control design accurately. The real positive/null pair tests the unchanged
diversifier lane, while the seeded synthetic family calibration tests the new standalone
lane. No threshold, feature, model, candidate, split, metric, or result changed.

## Authoritative Production Reproduction

- Workflow run: `32861194112`, success
- Main commit: `08970e7b2dbb065eda824a7d3de5485b876865d4`
- Production timestamp: `2026-08-25T14:49:16Z`
- Production batch ID: `energy-cross-market-a69882576424`
- Reproduced verdict: `NO_FACTORY_EDGE`
- Reproduced criterion diagnosis: `OBJECTIVE_GATE_PASSABLE_CANDIDATE_UNCONFIRMED`
- Reproduced audit: 16/16 current candidates, 736/736 global unique fingerprints
- Reproduced selected candidate and metrics: exact match with the frozen local replay
- Publication: success; incomplete or stale runs cannot overwrite this evidence sidecar

The post-merge KIS read-only smoke run `32861858561` also passed 5/5 against the same
commit. It observed zero recent orders and zero open unfilled orders. Deploy workflow
`32861194460` completed safely, but the server refused the code swap during the US regular
session and deferred it to `auto-invest-deploy.timer` after `2026-08-25T21:00:00Z`.
Production research evidence is therefore current, while server code deployment remains a
time-gated follow-up rather than a completed claim.

## Data And Chronology

- Factor window: March 1998 through June 2026, 340 months
- Development: 120 months, March 1998 through February 2008
- Embargo: March 2008
- Untouched holdout: 219 months, April 2008 through June 2026
- EIA publication rule: month `t` first affects target return month `t+2`
- Data fingerprint: `sha256:0fc82fe19e9f8035dc93b2b306a3fc2bd1aa30ac1a31b1b7f474a92b3677a627`
- Split fingerprint: `sha256:409896a22a165efe891bb148d422837523d6ecfedd965a03df0e98c94375e267`
- Model fingerprint: `sha256:2ad683ff9e964d563e543aa8b7a70ae6ac784dd7363ca01df09cf222731106e3`
- Current-history limitation: the source hashes are fixed, but EIA spot histories and
  the reconstructed French industry series are not vintage point-in-time archives.

## Frozen Development Winner

- Candidate: `energy-cross-ridge_forecast-d869beb7c67e`
- Policy: 12-month cross-market features, expanding `Ridge(alpha=10)`, at least 60
  earlier labels, and maximum energy weight 50%
- Holdout cash-excess PSR: `0.822115` versus required `0.95`
- Annual cash excess after 50bp: `1.912757%` versus required `2.0%`
- Sharpe change versus passive energy: `-0.002315` versus required `+0.10`
- Maximum drawdown: `35.632935%` versus passive energy `64.750875%`, passed
- Active energy fraction: `95.8904%` versus required range `10%-90%`
- DSR diagnostic: `0.895135`
- PBO diagnostic: `0.746032`

The winner reduced drawdown and earned a positive cash premium, but it behaved almost
like permanent energy exposure and did not improve risk-adjusted performance over the
passive energy proxy. It therefore failed both live and paper selection.

## Criterion Audit

- The existing diversifier lane was not lowered or reclassified.
- The new standalone lane asks a different question: whether timed energy exposure
  beats both cash and passive energy.
- A 500-repetition, 16-candidate selection simulation produced a `4.4%` null false
  acceptance rate and `84.0%` planted-edge detection rate.
- Existing real positive and null controls also remained valid.

The evidence therefore rejects the claim that the gate is mathematically impossible.
The earlier universal use of the diversifier lane was incomplete, but this result fails
because the frozen candidate lacks enough independent timing value, not because the
threshold was silently moved.

## Prohibited Post-Hoc Result

The best holdout-ranked candidate was
`energy-cross-market_breadth-cba7b5d25d94`: PSR `0.861771`, annual cash excess
`1.657890%`, Sharpe improvement `+0.073612`, and active fraction `47.4886%`. It passed
the paper lane only. Because it was identified after holdout inspection,
`promotion_allowed=false`; it cannot replace the development winner.

## Money Boundary And Next Priority

`XLE` is only the intended expression. Exact policy code, historical live parity,
whitelist authorization, deploy configuration, hardened canary evidence, and exact
fingerprint identity do not exist. The result therefore cannot arm a live order path.
The next independent preregistration priority is options variance-risk premium, while
this post-hoc breadth candidate may enter a new forward paper experiment only under a
new identity and without reusing this holdout as confirmation.
