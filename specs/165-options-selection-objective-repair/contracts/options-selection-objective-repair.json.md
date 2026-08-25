# Contract: Options Selection and Objective Repair JSON

The canonical factory JSON retains the specification 164 fields and adds the following diagnostic contract.

```json
{
  "selection_repair": {
    "protocol": {
      "outer_train_months": 84,
      "outer_embargo_months": 1,
      "outer_test_months": 12,
      "inner_train_months": 48,
      "inner_embargo_months": 1,
      "inner_validation_months": 12,
      "independent_index": "WPUT",
      "independent_index_used_for_selection": false
    },
    "chronology": {
      "fold_count": 0,
      "all_folds_valid": false,
      "violations": []
    },
    "portfolio_selection": {
      "outer_folds": [],
      "put_stitched": {},
      "wput_replay": {}
    },
    "timing_selection": {
      "outer_folds": [],
      "put_stitched": {},
      "wput_replay": {}
    }
  },
  "objective_lanes": {
    "premium_existence": {},
    "portfolio_adoption": {},
    "timing_value": {}
  }
}
```

## Required invariants

1. WPUT does not affect any selected candidate ID, selected weight, threshold, or tie-break.
2. Every outer fold contains at least two valid inner folds.
3. Every inner validation interval ends before the outer test interval begins.
4. WPUT replay uses the exact PUT-selected candidate and monthly weights.
5. The candidate count remains 16 and the global unique research configuration count remains 752.
6. The canonical verdict is never `FACTORY_EDGE`; `research_canary_eligible`, `paper_lane_eligible`, and `promotion_eligible` remain false.
7. Missing or stale WPUT evidence fails closed.
