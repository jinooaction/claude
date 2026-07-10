# Contract: Agent Harness Regression Liveness

## CLI

```bash
uv run python scripts/agent_harness_regression_liveness_probe.py \
  --repo-root . \
  --strict-output /tmp/agent-harness-strict.txt \
  --released-work /tmp/released_work.json \
  --format markdown
```

## Inputs

- `--repo-root`: repository root to inspect.
- `--strict-output`: optional output file from `uv run python scripts/agent_harness_probe.py --strict`.
- `--released-work`: optional `released_work.json` evidence.
- `--evidence-dir`: optional directory containing `strict-output.txt` and `released-work.json`.
- `--format`: `markdown` or `json`.
- `--json-out`: optional JSON output path.
- `--summary-out`: optional Markdown output path.
- `--now`: optional deterministic timestamp.
- `--run-id`: optional workflow run id.
- `--commit`: optional commit hash.

## JSON Output

Required top-level keys:

- `schema_version`
- `run_id`
- `commit`
- `timestamp_utc`
- `overall_status`
- `completed_candidate_id`
- `next_candidate_id`
- `evidence_surfaces`
- `harness_suite_summary`
- `strict_observation_summary`
- `quality_gates`
- `released_work_summary`
- `safety_invariants`

## Status Semantics

- `CONTRACT_READY`: suite coverage, strict output, released-work completion, and safety boundary all pass.
- `OBSERVATION_WAIT`: source and suites pass, but strict output or released-work completion evidence is not yet present.
- `BLOCKED`: a source file is missing, a suite fails, strict output is degraded, released-work is malformed, or safety boundary is violated.

## Safety Boundary

The report must not call broker APIs, submit orders, allocate capital, change live strategy, modify whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, call GitHub, call SSH, or invoke paid services.
