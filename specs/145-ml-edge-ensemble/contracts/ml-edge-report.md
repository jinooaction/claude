# Contract: ML Edge Report

The probe writes one JSON object with these required top-level fields:

```json
{
  "schema_version": "1.0",
  "experiment_id": "ml-edge-ensemble-v1",
  "verdict": "ML_EDGE_CANDIDATE_READY|NO_EDGE|BLOCKED_DATA|BLOCKED_MODEL",
  "data_fingerprint": "sha256:...",
  "model_fingerprint": "sha256:...",
  "feature_fingerprint": "sha256:...",
  "folds": [],
  "model_metrics": {},
  "cost_scenarios": [],
  "benchmarks": {},
  "regime_slices": [],
  "significance": {},
  "gates": [],
  "candidate_package": {},
  "safety": {
    "orders_submitted": 0,
    "live_strategy_changed": false,
    "capital_changed": false
  }
}
```

`ML_EDGE_CANDIDATE_READY` is valid only when every gate has `passed=true`. The candidate package must contain the exact replay command and all three fingerprints. Any missing required field is invalid and fails closed.
