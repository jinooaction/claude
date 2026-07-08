# Contract: HANDOFF Truth Liveness Probe

## CLI

```bash
uv run python scripts/handoff_truth_liveness_probe.py \
  --repo-root . \
  --format json \
  --json-out /tmp/handoff_truth_liveness.json \
  --summary-out /tmp/HANDOFF_TRUTH_LIVENESS.md
```

## Inputs

- `--repo-root`: Repository root to inspect. Defaults to `.`.
- `--handoff`: Optional HANDOFF path. Defaults to `<repo-root>/HANDOFF.md`.
- `--expect-pytest`: Optional substring expected in the `main 테스트` row.
- `--expect-ruff`: Optional substring expected in the `main 린트` row.
- `--expect-open-pr`: Optional substring expected in the `열린 PR` row.
- `--format`: `markdown` or `json`.
- `--json-out`: Optional JSON output path.
- `--summary-out`: Optional Markdown output path.
- `--now`, `--run-id`, `--commit`: Deterministic metadata overrides.

## JSON Output

Required top-level fields:

- `schema_version`
- `run_id`
- `commit`
- `timestamp_utc`
- `overall_status`
- `completed_candidate_id`
- `next_candidate_id`
- `evidence_surfaces`
- `allowed_baselines`
- `handoff_summary`
- `quality_gates`
- `released_work_summary`
- `safety_invariants`

## Status Semantics

- `CONTRACT_READY`: HANDOFF is readable, main baseline is current or valid handoff-only first parent, optional expected rows match, and safety boundary is read-only.
- `BLOCKED`: HANDOFF is missing, stale, malformed for required rows, or optional expected rows do not match.

## Safety Boundary

The probe is read-only. It must not create branches, open PRs, merge PRs, deploy, call broker APIs, place orders, allocate capital, read/write secrets, change live settings, or collect fresh external data.
