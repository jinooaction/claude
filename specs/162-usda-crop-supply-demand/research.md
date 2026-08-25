# Research: USDA Crop Supply-Demand Factory

## Decision 1: Use archived releases, not a revised history

- **Decision**: Discover monthly XLS releases from USDA ESMIS and parse each report as published.
- **Rationale**: USDA states that the archive reflects estimates as believed at each release and excludes later revisions. This removes the largest look-ahead risk in fundamental backtests.
- **Alternative considered**: Current USDA PS&D history. Rejected because revised history cannot reconstruct what was known at each decision date.

## Decision 2: Keep the existing gate unchanged

- **Decision**: Retain live PSR 0.95, paper PSR 0.80, positive 50bp excess return, correlation, blend Sharpe, and drawdown rules.
- **Rationale**: The real positive control passes all complete gates while the null fails. The standard is conservative but demonstrably passable; lowering it after candidate failures would fit the answer.
- **Alternative considered**: Lower PSR to match the last EIA candidate's 0.705637. Rejected because the calibrated null would be accepted too often.

## Decision 3: Use same-marketing-year stocks-to-use revisions

- **Decision**: Define scarcity as a decline in projected ending-stocks-to-use versus one or three prior releases only when the projected marketing year matches.
- **Rationale**: Revisions carry new supply-demand information. Marketing-year rollovers mechanically change levels and must not be mistaken for a shock.
- **Alternative considered**: Absolute stocks-to-use level. Rejected because crop and marketing-year seasonality would dominate.

## Decision 4: Use already-supported inflation and duration exposures

- **Decision**: During positive scarcity hold GLD up to 50% or 100%, with IEF as the remainder; during no scarcity hold IEF.
- **Rationale**: Crop tightening is an inflation shock hypothesis. GLD and IEF already exist in the live execution map, so no whitelist expansion is hidden in the research.
- **Alternative considered**: DBA, CORN, WEAT, or SOYB. Rejected for this iteration because they are outside the active live whitelist and their free historical adjusted-price sources are weaker than the existing gold/bond proxies.

## Decision 5: Shorter development, unchanged minimum holdout

- **Decision**: Use 60 development months, one embargo month, and at least 120 holdout months.
- **Rationale**: Archived point-in-time XLS coverage begins in July 2010. This split preserves a ten-year confirmation period while leaving five years for frozen selection.

## Known Limitations

- WASDE has no January 2019 report because of the U.S. government shutdown.
- Gold is an imperfect hedge for crop-specific inflation, so economic failure is plausible and meaningful.
- Archived workbook labels can change; schema mismatch must fail closed rather than silently skip.

## Post-Preregistration Data Finding

ESMIS exposes five same-date archive aliases across the retained history. The
factory prefers the unprefixed dated workbook and verifies that every alias has
identical corn, wheat, and soybean market-year, ending-stock, and total-use
inputs. This technical source rule was added after the first live archive replay
failed closed; it does not change any signal, candidate, split, cost, or gate.
