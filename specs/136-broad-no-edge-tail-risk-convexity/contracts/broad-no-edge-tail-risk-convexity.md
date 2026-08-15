# Contract: Broad No-Edge Tail-Risk Convexity

## Probe

Path: `scripts/broad_no_edge_tail_risk_convexity_probe.py`

Required behavior:

- `--manifest` prints `key<TAB>branch<TAB>filename`.
- `--json` emits deterministic JSON.
- `--summary-out` writes Markdown.
- `--json-out` writes JSON.
- `--repo-root` overrides the released-work sidecar by scanning local specs.

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
