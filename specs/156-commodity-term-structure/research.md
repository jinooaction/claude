# Research: Independent Commodity Term Structure

## Decision: Use a realized broad-curve proxy

The signal is S&P GSCI Total Return growth minus the World Bank Total Index spot return and prior-known
three-month Treasury cash return. Positive values mean the futures implementation outperformed broad spot
movement plus collateral over the same month. Composition and collateral-benchmark differences remain, so
this is still a proxy rather than an exact contract roll yield.

### Methodology correction before the binding run

The first local plumbing replay subtracted spot but not cash. It produced PSR 0.757994, but the replay is
invalidated and is not eligible for the audit catalog or any verdict because it mixed collateral interest
with curve return. The v2 definition above was frozen before observing any v2 result; candidate count,
grammars, costs, split, and thresholds are unchanged.

Direct continuous futures downloads from Nasdaq Data Link were rejected because the current worker receives
HTTP 403. Yahoo and other unofficial mirrors were also rejected for rate limits, access failure, or unclear
licensing. A keyless official iShares endpoint and the World Bank's current workbook are reproducible here.

## Decision: Use GSG NAV for earned returns

Signals use the gross S&P GSCI benchmark, but candidate returns use monthly GSG fund NAV growth. This keeps
fees and tracking difference in the backtest rather than assuming frictionless index execution.

## Decision: Freeze a small 16-candidate family

Four economic grammars x 3/12-month carry lookback x 50/100% maximum allocation produce exactly 16 trials.
The fixed confirmation windows are 12 months for momentum/volatility and 36 months for rank/volatility regime.

## Decision: Use 96 development months and at least 120 holdout months

GSG begins in August 2006. A 12/36-month signal warm-up prevents a 120/120 split. We prioritize more than ten
years of untouched holdout: 96 usable development months, one embargo month, and the remainder as holdout.

## Decision: Keep existing gate calibration and tier meanings

The family has the already calibrated size 16. Live evidence retains PSR 0.95 and all economic gates. The
paper tier uses PSR 0.80 but remains capital-free. No gate is relaxed because prior families failed.

## Sources and Licensing

- iShares GSG product page and BlackRock product-data performance component: monthly fund and benchmark growth.
- S&P Dow Jones Indices S&P GSCI page: benchmark identity and commodity-futures methodology.
- World Bank Pink Sheet August 2026 workbook: monthly Total Index, updated 2026-08-04 through 2026-07.
- Federal Reserve FRED `DGS3MO`: prior-observation three-month Treasury cash yield.
- CME education: contango, backwardation, and roll-cost interpretation.

Raw BlackRock values are used for computation only. Artifacts retain counts, date range, hashes, metrics, and
citations, not the complete licensed series.
