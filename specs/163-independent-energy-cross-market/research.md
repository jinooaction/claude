# Research: Independent Energy Cross-Market Factory

## Decision 1: Diagnose objective mismatch, not an impossible threshold

- **Decision**: Keep the existing five-gate incumbent-diversifier lane unchanged and add a separate standalone energy-timing lane.
- **Rationale**: The prior gate asks whether a candidate improves an already high-Sharpe SPY/IEF/GLD portfolio at a fixed 20% blend. That is appropriate for a diversifier but does not answer whether a directly traded sleeve beats cash and passive energy exposure. AQR diversified trend passes the old complete gate, so the old gate is demonstrably passable; it is incomplete as a universal objective classifier.
- **Evidence before this feature**: Of the latest independent batches, FX, commodity carry, positioning, and USDA failed both statistical/economic gates; EIA supply-demand passed all economics but had PSR 0.705637; no released frozen winner was rejected only because it was correlated with the incumbent. The immediate problem was mostly weak frozen winners, while the universal gate taxonomy was still conceptually too narrow.
- **Alternative considered**: Lower the existing PSR or blend-improvement thresholds. Rejected because that would fit prior failures and increase false acceptance.

## Decision 2: Judge energy timing against energy buy-and-hold

- **Decision**: The standalone live lane requires PSR at least 0.95, annual cash excess after 50bp at least 2%, Sharpe improvement over passive energy of at least 0.10, and no worse maximum drawdown.
- **Rationale**: This blocks trivial always-invested energy beta while allowing a profitable timing sleeve even if it is not a strong diversifier for the current incumbent.
- **Alternative considered**: Cash-only comparison. Rejected because passive XLE or an energy index is the simplest investable alternative.

## Decision 3: Use official cross-market prices with a conservative lag

- **Decision**: Use EIA monthly WTI, Gulf Coast gasoline, New York heating oil, and Henry Hub natural gas series. Month `t` data first affects month `t+2` returns.
- **Rationale**: EIA publishes spot-price histories and explains that crack spreads estimate refinery margins by comparing product and crude prices. The extra full-month lag avoids pretending a monthly average was known at that month's start or exactly at month end.
- **Alternatives considered**: Futures curves and vendor forecasts. Rejected because free point-in-time histories are weaker or require paid services and hidden revisions.
- **Primary sources**:
  - https://www.eia.gov/dnav/pet/pet_pri_spt_s1_m.htm
  - https://www.eia.gov/finance/markets/products/prices.php
  - https://www.eia.gov/todayinenergy/includes/crackspread_explain.php
  - https://www.eia.gov/dnav/ng/hist/rngwhhda.htm

## Decision 4: Use a long energy-equity research proxy

- **Decision**: Use the Kenneth French 49-industry value-weighted `Oil` return as the research target and XLE as the intended future live expression.
- **Rationale**: The French series supplies a long, dividend-inclusive energy-equity history. State Street states that XLE tracks the Energy Select Sector Index and began in December 1998, which is too short for the desired early development plus long holdout if used alone.
- **Limitation**: French reconstructs its full industry history when CRSP data change. The source hash is therefore pinned, and this target is not described as a point-in-time fundamental series or exact XLE parity.
- **Primary sources**:
  - https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
  - https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_49_ind_port.html
  - https://www.ssga.com/us/en/institutional/etfs/state-street-energy-select-sector-spdr-etf-xle

## Decision 5: Freeze three rules and one adaptive model

- **Decision**: Four families are WTI trend, 3:2:1 refining-margin regime, cross-market breadth, and expanding ridge forecast. Each uses a 6- or 12-month horizon and 50% or 100% maximum energy weight.
- **Rationale**: The rules test known economic relationships. Ridge adds adaptive weighting without a large hyperparameter search, and the rules reveal whether the model actually adds value.
- **Model contract**: Fixed `alpha=10`, four 6/12-month market returns plus a crack margin standardized over that same feature window, deterministic solver, 60 past labels minimum, expanding training, and training targets strictly before the prediction month.
- **Alternative considered**: Gradient boosting, neural networks, and model ensembles. Rejected because about 40 years of monthly data cannot support their flexibility without severe overfit risk.

## Decision 6: Keep the search budget exact

- **Decision**: Exactly 16 current candidates, 120 development months, one embargo month, at least 180 holdout months, and 10/25/50bp turnover costs.
- **Rationale**: A small frozen grammar, a long holdout, and the existing cumulative ledger make selection bias visible. No feature, threshold, or model can be changed after candidate results.

## Known Limitations

- Spot-price files are current histories rather than revision-vintage archives.
- WTI, Gulf Coast gasoline, and New York heating oil are not a location-matched refinery slate.
- The heating-oil contract specification changed in 2013.
- The French `Oil` industry portfolio is not XLE and cannot establish executable return parity.
- Even a research pass cannot trade until XLE history parity, live policy implementation, whitelist authorization, hardened canary, and exact fingerprint checks exist.

## Preregistration Marker

This document, `spec.md`, and the requirement checklist were written before the first
candidate-data download or candidate-return inspection for spec 163. Later source-schema
discoveries may repair parsing only; they may not change economic rules, model settings,
candidate count, costs, split, or thresholds.
