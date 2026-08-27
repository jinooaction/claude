# Research: Parallel Regime Edge Challenger

## Current Evidence

- The current calibrated entry gate is not the old raw-candidate Bonferroni gate. The program groups
  752 raw rows into 17 economic families and uses selected holdout PSR plus family PBO. Fixed-seed
  calibration admitted at most 1% of null families and detected at least 80% of planted annual
  Sharpe 0.60 signals for family sizes 16 and 64.
- The historical incumbent remains meaningful: over its long holdout it recorded about 8.68% CAGR,
  1.83 Sharpe, and 5.57% maximum drawdown. It is not a current live edge because the anchored recent
  comparison produced zero of three segment Sharpe wins against buy-and-hold.
- Therefore “everything failed” is partly a presentation problem: there is a historically strong
  strategy, but no strategy has yet shown both calibrated statistical evidence and recent regime
  superiority required for current capital.

## Why This Family

Long-horizon time-series momentum has published evidence across equity-index, bond, currency, and
commodity futures and tends to be strongest during extreme markets. AQR's century-scale study also
reports that trend performance is most affected by cross-market correlation and is strongest in
low-correlation environments. These findings support testing a narrow correlation-aware overlay,
but do not justify assuming it works.

- AQR, *A Century of Evidence on Trend-Following Investing*:
  https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing
- Moskowitz, Ooi, Pedersen, *Time Series Momentum*:
  https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2089463_code753937.pdf?abstractid=2089463&mirid=1

## Token Liveness Decision

KIS officially recommends reusing an unexpired access token and renewing it only when needed. The
parity observer's temporary database must therefore not imply a temporary token cache. The CLI has
an explicit token-cache option, but the production helper is synchronized before a market-hours
deferred package deploy. Therefore the observer locates its random ephemeral DB directly under
`data/`; both old and new CLIs resolve the existing `data/kis_token.json` without a new option.

- KIS official API token guidance: https://apiportal.koreainvestment.com/provider-doc4

This is a liveness correction, not a weakening. A missing, expired, malformed, or unrefreshable token
still produces no parity evidence and cannot open capital.

## Frozen Candidate Grid

| Dimension | Values |
|---|---|
| Stock-bond return correlation window | 12, 24 months |
| Correlation threshold | 0.0, 0.2 |
| Joint-weakness lookback | 3, 6 months |
| Defensive action | cash, gold |

The Cartesian product is exactly 16 candidates. The incumbent remains the existing 3/6/9/12-month
per-asset trend ensemble. No volatility target, leverage, shorting, macro release, or optimized asset
weight is added.

## Frozen Validation Design

- development: joint sample start through 2006-12
- embargo: 2007-01
- untouched holdout: 2007-02 through the latest available complete month
- selection: development Sharpe, then CAGR, then lower drawdown, then lexical ID
- principal cost: 50bp/year fixed plus 10bp per one-way turnover, charged to both strategies
- cost diagnostics: 25bp and 50bp per one-way turnover
- statistical entry: family PBO <= 0.25 and holdout active-return PSR >= 0.95
- economic entry: higher holdout CAGR and Sharpe, no worse drawdown, at least two of three recent
  segment Sharpe wins, higher latest-60-month Sharpe, annual turnover <= 4.0
- DSR and raw Bonferroni: visible diagnostics, not threshold blockers under gate version 3.1

## Alternatives Rejected

- **Lowering the gate**: calibration does not show that the current family-level gate is broken.
- **Searching hundreds more horizons**: increases selection bias and overlaps prior factories.
- **LLM choosing monthly weights**: removes determinism and introduces an undeclared per-bar judgment point.
- **Immediate live promotion after a historical pass**: violates the required Backtest -> Canary -> Full path.
