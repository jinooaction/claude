# Contract: PR/Merge Evidence Liveness Probe

## CLI

```bash
uv run python scripts/pr_merge_evidence_liveness_probe.py \
  --repo-root . \
  --pr-body /tmp/pr_body.md \
  --released-work /tmp/released_work.json \
  --deploy-status /tmp/deploy_status.md \
  --format json \
  --json-out /tmp/pr_merge_evidence_liveness.json \
  --summary-out /tmp/pr_merge_evidence_liveness.md
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
- `merge_summary`
- `deploy_summary`
- `quality_gates`
- `released_work_summary`
- `safety_invariants`

## Gate Semantics

- PR body missing: `WAIT`.
- PR body present and quality-gate fields valid: `PASS`.
- PR body present but required grade 2 fields missing: `FAIL`.
- Latest main merge missing: `WAIT`.
- Latest main merge present but not a merge PR subject: `FAIL`.
- released-work missing: `WAIT`.
- released-work malformed: `FAIL`.
- completed candidate released: `PASS`; parseable but not released yet: `WAIT`.
- deploy-status missing: `WAIT`.
- deploy-status success or intentional docs/spec skip: `PASS`.
- deploy-status failure, rollback, or blocked: `FAIL`.

## Safety Contract

The probe is read-only. It must not call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist or caps, read or write secrets, modify constitution or kernel files, run fresh external collection, query GitHub, SSH to the server, or invoke paid external services.

completed_candidate_id: candidate-pr-merge-evidence-liveness-contract
next_candidate_id: candidate-worktree-concurrency-liveness-contract
