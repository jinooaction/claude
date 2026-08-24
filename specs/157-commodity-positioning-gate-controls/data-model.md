# Data Model: Commodity Positioning and Real-World Gate Controls

## RealWorldGateControl

- `control_id`, `provider`, `source_url`, `source_digest`
- `window`, `observations`, `annual_sharpe`, `psr`, `live_passed`
- `demeaned_psr`, `demeaned_rejected`
- Validation: fixed identifiers and start date, sufficient observations, finite returns, immutable source hash.

## CftcPosition

- `contract_code`, `contract_name`, `report_date`, `available_date`
- `open_interest`, `managed_money_net_ratio`, `producer_net_ratio`
- Validation: fixed contract set, positive open interest, finite positions, report plus three-day availability.

## EiaInventory

- `series_id`, `period_end`, `available_date`, `thousand_barrels`
- Validation: exact series, positive finite level, period plus five-day availability.

## CommodityPositioningPolicy

- `family`, `lookback_weeks`, `max_commodity_weight`
- Four families and two values for each numeric choice create exactly 16 immutable policies.

## CommodityPositioningDecision

- Source/control/candidate/split/code fingerprints
- 96-month development selection, one-month embargo, untouched holdout
- DSR/PBO diagnostics, holdout PSR, costs, correlation, blend economics
- 672 prior plus 16 current audit records
- `FACTORY_EDGE`, `PAPER_CHALLENGER`, or `NO_FACTORY_EDGE`

## State Transitions

`PREREGISTERED -> DATA_VALID -> CONTROLS_VALID -> DEVELOPMENT_SELECTED -> HOLDOUT_EVALUATED -> VERDICT`

Any missing source, lag violation, hash mismatch, failed control audit, or incomplete audit count transitions
to `NO_FACTORY_EDGE` for promotion purposes before any broker boundary.
