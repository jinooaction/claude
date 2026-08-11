# Contract: Broad NO_EDGE Frontier

## Parent Suppression

completed_candidate_id: candidate-broad-frontier-expansion-no-edge-58298dfc172c
next_candidate_id: candidate-broad-no-edge-asset-universe-rotation-experiment

When all known candidates are closed, no retryable validation package exists, and money/edge evidence still says `PREVIEW_ONLY`, `NO_EDGE_YET`, `NO_EDGE`, `WAIT_EDGE`, or `ACCUMULATING_EDGE`, the report may emit:

```json
{
  "selected_work": {
    "candidate_id": "candidate-broad-frontier-expansion-no-edge-<fingerprint>",
    "status": "EXECUTION_READY",
    "risk_grade": 2
  }
}
```

If released-work later records that exact candidate, the report must not emit another parent broad no-edge candidate solely because released-work changed.

## Follow-Up Map

The report must include:

```json
{
  "broad_no_edge_frontier_map": [
    {
      "frontier_key": "asset_universe_rotation",
      "coverage_status": "open",
      "recommended_candidate_id": "candidate-broad-no-edge-asset-universe-rotation-experiment",
      "review_axes": ["strategy_family", "asset_universe"]
    }
  ]
}
```

The concrete entries may include more fields, but must preserve deterministic ordering and coverage status.

## Follow-Up Packet

After a parent broad no-edge candidate is released and no higher-priority ready, blocked, or approval-required packet exists, the report must emit the first open map entry as `selected_work`.

The packet must remain read-only:

- no broker API call
- no orders
- no capital allocation
- no live strategy change
- no whitelist/caps change
- no secret read/write
- no external paid service
