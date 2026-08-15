# Contract: Broad No-Edge Vol-Target Drawdown

## Probe

Path: `scripts/broad_no_edge_vol_target_drawdown_probe.py`

Required behavior:

- `--manifest` prints `key<TAB>branch<TAB>filename`.
- `--json` emits deterministic JSON.
- `--summary-out` writes Markdown.
- `--json-out` writes JSON.
- `--repo-root` overrides the released-work sidecar by scanning local specs.

## Report Contract

- `completed_candidate_id` is `candidate-broad-no-edge-vol-target-drawdown-experiment`.
- `next_candidate_id` is `wait-for-fresh-evidence`.
- `drawdown_lanes` contains volatility target, drawdown deleveraging, PSR sensitivity, live drawdown exclusion, and broad no-edge context lanes.
- `validation_gates` contains input evidence, forward no-edge context, PSR sensitivity, drawdown lane coverage, drawdown risk, execution cost awareness, money gate alignment, pipeline liveness, and released-work closure.

## Safety

The probe and core module are read-only:

- no broker API call
- no orders
- no capital allocation
- no live strategy change
- no whitelist/caps change
- no secret read/write
- no external paid service
- no constitution/kernel change
