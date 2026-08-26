# Contract: Family Complete V3 and Fundability

## Factory consumer assessment

```json
{
  "eligible": false,
  "contract_version": "family-complete-v3",
  "candidate_count": 16,
  "complete_trial_count": 16,
  "global_audit_trial_count": 752,
  "program_multiplicity": {
    "method": "bonferroni-global-fwer-v1",
    "selected_psr": null,
    "raw_one_sided_p": null,
    "global_trial_count": 752,
    "adjusted_p": null,
    "threshold": "0.05",
    "recomputed_dsr": null,
    "recomputed_pbo": null,
    "claimed_dsr": null,
    "claimed_pbo": null
  },
  "checks": {},
  "reasons": []
}
```

## Fundability assessment

```json
{
  "fundable": false,
  "capital_usd": "145",
  "investable_usd": "143.55",
  "active_target_count": 2,
  "funded_target_count": 1,
  "funded_target_ratio": "0.5",
  "quote_coverage_ratio": "1",
  "invested_fraction": "0.99",
  "target_weights": {},
  "holdings": {},
  "prices": {},
  "order_prices": {},
  "planned_orders": [],
  "caps": {},
  "effective_side": "both",
  "l1_weight_error": "0.4",
  "max_leg_weight_error": "0.333333",
  "checks": {},
  "reasons": []
}
```

## Required invariants

1. The consumer recomputes row counts, uniqueness, family-tail membership, selection identity,
   selected-row PSR identity, effective trials, DSR, and PBO.
2. A producer gate boolean cannot override a failed consumer check.
3. Global multiplicity uses all unique audited trials, not only the current family.
4. Legacy and v2 assessments are diagnostic-only.
5. Fundability uses mapped execution symbols and the live planner's lot/minimum/cap behavior.
6. Serialized preview inputs are recomputed; missing preview, quotes, inputs, or exact output agreement
   fails upward entry closed.
7. No assessment submits an order or changes capital.
