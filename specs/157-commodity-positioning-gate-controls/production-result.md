# Binding Result: Commodity Positioning and Real-World Gate Controls

**Binding replay time**: `2026-08-25T00:00:00Z`  
**Code binding token**: `spec157-preregistered-v1`  
**Candidate changes after seeing results**: none  

## Invalidated Plumbing Run

The first invocation stopped before candidate evaluation because the official AQR workbook contains
fully blank, formatted tail rows. It emitted no strategy JSON and produced no candidate verdict. The
parser was changed only to ignore rows where all six expected cells are blank; partially populated rows
still fail closed. A regression test was added before the binding replay was restarted from source input.

## Empirical Gate Audit

- Verdict: `REAL_WORLD_CONTROLS_VALID`
- Fama-French U.S. market excess return, `2007-01` through `2026-06`: 234 observations,
  annualized Sharpe `0.648641`, PSR `0.996536`, live control passed.
- AQR diversified time-series momentum, `2007-01` through `2026-05`: 233 observations,
  annualized Sharpe `0.440025`, PSR `0.974381`, live control passed.
- Demeaned copy of each control: PSR `0.500000`, live control failed.
- Controls added zero candidate trials and were ineligible for promotion.

## Commodity Positioning Result

- Verdict: `NO_FACTORY_EDGE`; paper-forward eligibility is also false.
- Audit: 16 complete new candidates plus 672 prior records equals 688 unique records.
- Development winner: `commodity-positioning-managed_money_trend-9480c3c1956f`.
- Development: 96 months; embargo: one month; untouched holdout: 131 months.
- Holdout excess PSR after 25 basis points: `0.525291` versus live `0.95` and paper `0.80`.
- Holdout annual excess return after 50 basis points: `-0.01769314`.
- Incumbent correlation: `0.088256`; blend Sharpe change: `-0.194567`.
- Failed blocking gates: `holdout_excess_psr`, `holdout_excess_50bps_positive`, and
  `blend_sharpe_improvement`.
- Data completeness, calibration, empirical controls, split, parity, uniqueness, correlation, and
  blend drawdown gates passed.

## Interpretation and Safety

The live PSR threshold is not structurally impossible: two preregistered real historical effects passed
the exact same threshold while their zero-mean controls failed. The current commodity positioning family
failed because its untouched holdout economics were weak, not because a near-pass was rejected by an
arbitrary cutoff. This result does not prove that every gate dimension is optimal or that historical
controls will persist.

No candidate was selected, no deployment configuration was emitted, GSG remains outside the live
whitelist, and broker calls, capital changes, and orders were all zero.
