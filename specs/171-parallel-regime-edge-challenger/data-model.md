# Data Model: Parallel Regime Edge Challenger

## Preregistered Contract

- `schema_version`: `regime-edge-preregistration-v1`
- `family_id`: stable family identifier
- `candidate_grid`: four frozen dimensions whose Cartesian product has 16 rows
- `split`: development end, embargo month, holdout start
- `cost_model`: annual fixed cost and one-way turnover cost
- `gates`: fixed statistical, economic, recent-period, and turnover thresholds
- `safety`: promotion, orders, and capital-change booleans fixed false

## Monthly Observation

- `date`: complete month-end observation
- `asset_factors`: stock, bond, gold, and cash gross return factors for the next period
- `signal_levels`: total-return or price levels known by the preceding month-end
- `incumbent_weights`: stock, bond, gold, cash weights summing to one
- `candidate_weights`: incumbent weights after the registered defensive overlay
- `stress_active`: true only when correlation and joint weakness both pass
- `one_way_turnover`: `0.5 * sum(abs(weight_t - weight_t_minus_1))`
- `net_factor`: gross portfolio factor after fixed and turnover costs

## Candidate Result

- `candidate_id`, `candidate_fingerprint`, and four grid parameters
- development metrics and eight segment scores used for PBO
- untouched holdout factors and metrics at 10bp, 25bp, and 50bp turnover costs
- annualized turnover and stress-month count
- holdout active-return PSR, DSR diagnostic, and raw Bonferroni diagnostic
- recent-three-segment comparisons and latest-60-month comparison

## Report

- exact preregistration identity and input fingerprints
- all 16 candidates and the deterministic development winner
- incumbent and winner holdout metrics under identical costs
- individual gate booleans plus `RESEARCH_EDGE` or `NO_RESEARCH_EDGE`
- `program_research_family_count=18`, budget `0.18`, and completed candidate ID
- `promotion_allowed=false`, `orders_submitted=0`, `capital_changed=false`

## Invariants

1. Every return at t uses weights produced only from information through t-1.
2. All weights are finite, nonnegative, and sum to one within numeric tolerance.
3. Candidate set, dates, and thresholds exactly match the committed contract.
4. Missing required data fails the report rather than shortening a gate silently.
5. Historical success never changes live state.
