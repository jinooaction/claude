# Production Result: USDA Crop Supply-Demand Factory

## Immutable Run Identity

- Timestamp: `2026-08-25T13:00:00Z`
- Code commit: `7a19b87da1cadfc3bbf1cf7e393f650e92ba0c7a`
- Batch: `usda-crop-supply-demand-edf386282a3b`
- Data fingerprint: `sha256:14bfdf9097470985450b39b0fc3542ac947bef27fab69e7523734e949378c760`
- Split fingerprint: `sha256:b2b94fa36e037f260e083e88d5c5459318aaa2aaae99f992e6839e3ce1cff402`
- Audit: 16 current candidates, 704 prior trials, 720 unique total trials

## Point-In-Time Data

- 192 official archived releases from `2010-07-09` through `2026-08-12`
- 193 aligned calendar months; 60 development, one embargo, 131 holdout months
- Five same-date archive aliases verified to have identical preregistered crop inputs
- Missing report months carried forward without invented releases: `2013-10`, `2019-01`, `2025-10`
- Source completeness: passed; latest release age 13 days and cash-series age four days

## Frozen Selection Result

- Development winner: `usda-crop-synchronized_tightening-02b25b9d8d4c`
- Policy: one-release synchronized tightening, maximum GLD weight 100%
- Development excess Sharpe after 25bp: `1.358138`
- Holdout excess Sharpe after 25bp: `-0.251817`
- Holdout PSR versus cash: `0.204521`
- Annual holdout excess return after 50bp: `-1.710304%`
- Incumbent correlation: `0.452343`
- 80/20 blend Sharpe change: `-0.117035`
- Incumbent/blend maximum drawdown: `14.842601%` / `15.316546%`

Verdict: `NO_FACTORY_EDGE`. Failed live gates were holdout PSR, positive
50bp excess return, blend Sharpe improvement, and non-worsening drawdown. It
also failed the paper PSR, return, and non-declining blend Sharpe gates.

## Selection Sanity

The best holdout result was the preregistered three-release soybean-tightening
candidate with 100% maximum GLD weight:

- Candidate: `usda-crop-soybean_tightening-779466b9e83d`
- Development excess Sharpe after 25bp: `0.110106`
- Holdout excess Sharpe and PSR after 25bp: `0.522314` / `0.965194`
- Annual holdout excess return after 50bp: `+3.078124%`
- Incumbent correlation: `0.615174`
- 80/20 blend Sharpe change: `-0.049875`
- Holdout maximum drawdown: `11.899728%`

This is descriptive only. It was not selected in development, the holdout is
now inspected, and it failed both live and paper blend-Sharpe gates. Zero of the
16 candidates passed every live gate and zero passed every paper gate, even in
the prohibited post-hoc scan. No candidate is promotable.

## Criterion Diagnosis

Verdict: `PASSABLE_BUT_CANDIDATE_UNCONFIRMED`, not a criterion failure.

- The complete known positive control passed with PSR `0.962691`; the null failed with PSR `0.434559`.
- For a 16-candidate family, calibrated live false acceptance was `5.0%`.
- A planted annual Sharpe `0.60` edge was detected `84.8%` of the time.
- Paper admission accepted nulls `21.6%` of the time, so the paper threshold is relatively permissive.
- With the actual 131-month holdout, approximate 80% detection requires annual Sharpe `0.753`; a true Sharpe `0.8` is detected about `84.1%` of the time.
- The frozen winner had negative net economics, so lowering only PSR cannot rescue it.

## Safety And Next Decision

- Broker calls, orders, fills, capital, caps, arming, and whitelist changes: zero.
- Research/live parity: failed closed because the monthly USDA policy is not implemented in the live engine.
- No live implementation should be built for this rejected family.
- The next independent preregistered family is `independent_energy_cross_market`.
