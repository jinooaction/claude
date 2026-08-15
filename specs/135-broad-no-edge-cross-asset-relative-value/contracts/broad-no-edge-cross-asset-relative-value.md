# Contract: Broad No-Edge Cross-Asset Relative Value

The probe must emit a deterministic JSON object:

```json
{
  "schema_version": "1.0",
  "contract_id": "broad-no-edge-cross-asset-relative-value",
  "completed_candidate_id": "candidate-broad-no-edge-cross-asset-relative-value-experiment",
  "next_candidate_id": "candidate-broad-no-edge-tail-risk-convexity-experiment",
  "overall_status": "CONTRACT_READY",
  "relative_value_lanes": [
    {
      "lane_id": "equity_duration_spread",
      "asset_pair": "equity/duration",
      "status": "PROPOSED",
      "candidate_rule_ko": "주식과 중기채 상대 강도 spread를 absolute momentum 후보와 별도로 검증한다.",
      "required_inputs": ["rebalance-paper-forward", "public-data-summary"],
      "exclusion_reason_ko": null
    }
  ],
  "safety_boundary": ["no broker API call", "no orders"]
}
```

## Required Behavior

- Missing or malformed required sidecars produce `BLOCKED`.
- Missing cash proxy inputs produce `OBSERVATION_WAIT`, not a false success.
- Live-capable money-path input produces `OBSERVATION_WAIT`.
- `--manifest` prints consumed sidecars in stable order.
- `--repo-root` overrides the released-work sidecar by scanning local completed specs.

## Completion Marker

```text
completed_candidate_id: candidate-broad-no-edge-cross-asset-relative-value-experiment
```
