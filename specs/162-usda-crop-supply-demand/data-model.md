# Data Model: USDA Crop Supply-Demand Factory

## WasdeRelease

- `release_date`: official publication date
- `source_url`, `content_digest`: immutable source lineage
- `crop`: corn, wheat, or soybeans
- `market_year`: rightmost projected marketing year
- `ending_stocks`, `total_use`: positive report values
- `stocks_to_use`: ending stocks divided by total use

Validation: one release/crop identity, finite positive values, projected market year present, official ESMIS URL.

## CropRevisionSnapshot

- `release_date`, `release_month`
- crop observations and one/three-release same-year scarcity revisions
- synchronized revision
- source URLs/digests and completeness

State: discovered -> downloaded -> parsed -> complete. Any missing crop or malformed value transitions to rejected.

## CropSupplyDemandPolicy

- `family`: corn, wheat, soybean, or synchronized tightening
- `revision_horizon`: 1 or 3 releases
- `max_gold_weight`: 0.5 or 1.0
- deterministic candidate and strategy fingerprints

## CropSupplyDemandDecision

- development winner and immutable split
- holdout PSR and post-cost excess return
- incumbent correlation, blend Sharpe, and drawdown
- full and paper gates
- family calibration and actual-holdout power
- audit lineage, latest target weights, and live-parity status

State: `FACTORY_EDGE`, `PAPER_CHALLENGER`, or `NO_FACTORY_EDGE`. Consumer eligibility remains a separate fail-closed assessment.
