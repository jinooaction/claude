# Contract: Worktree Concurrency Liveness Probe

## CLI

```bash
uv run python scripts/worktree_concurrency_liveness_probe.py \
  --repo-root . \
  --guard-check /tmp/local_concurrency_guard_check.txt \
  --released-work /tmp/released_work.json \
  --format json \
  --json-out /tmp/worktree_concurrency_liveness.json \
  --summary-out /tmp/worktree_concurrency_liveness.md
```

## Required Output Fields

- `schema_version`
- `run_id`
- `commit`
- `timestamp_utc`
- `overall_status`
- `completed_candidate_id`
- `next_candidate_id`
- `evidence_surfaces`
- `guard_behavior_summary`
- `runtime_state_summary`
- `quality_gates`
- `released_work_summary`
- `safety_invariants`

## Gate Semantics

- Required guard script or hook files missing: `FAIL`.
- Session-start hook missing guard call or ordered after git ground truth: `FAIL`.
- pre-commit/pre-push hook missing matching guard mode: `FAIL`.
- Synthetic clean check is not `OK`: `FAIL`.
- Synthetic conflict check is not `WARN`: `FAIL`.
- Synthetic conflict pre-commit or pre-push is not `BLOCK`: `FAIL`.
- Synthetic main branch commit or direct main push is not `BLOCK`: `FAIL`.
- Snapshot source surface missing required outputs: `FAIL`.
- Runtime guard output missing: `WAIT`.
- Runtime guard output present with guard failure text: `FAIL`.
- Runtime guard output present with `OK`, `WARN`, or `BLOCK`: `PASS`.
- released-work missing: `WAIT`.
- released-work malformed: `FAIL`.
- completed candidate released: `PASS`; parseable but not released yet: `WAIT`.

## Safety Contract

The probe is read-only. It must not call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist or caps, read or write secrets, modify constitution or kernel files, create worktrees, write leases, write snapshots, run fresh external collection, query GitHub, SSH to the server, or invoke paid external services.

completed_candidate_id: candidate-worktree-concurrency-liveness-contract
next_candidate_id: candidate-agent-harness-regression-liveness-contract
