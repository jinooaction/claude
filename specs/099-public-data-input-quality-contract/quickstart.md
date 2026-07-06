# Quickstart: Public Data Input Quality Contract

## Focused Tests

```bash
uv run pytest tests/unit/test_public_data_input_quality.py tests/integration/test_public_data_input_quality_probe.py tests/unit/test_autonomous_work_execution.py
```

## Probe Manifest

```bash
uv run python scripts/public_data_input_quality_probe.py --manifest
```

Expected manifest includes:

- `public-data-last-run	automation/public-data	LAST_RUN.md`
- `public-data-summary	automation/public-data	summary.json`
- `public-data-regime	automation/public-data	regime.json`
- `public-data-regime-timeline	automation/public-data	regime_timeline.csv`
- `regime-stratify	automation/regime-stratify-last-run	LAST_RUN.md`
- `pipeline-liveness	automation/pipeline-liveness-last-run	LAST_RUN.md`
- `released-work	automation/released-work-last-run	released_work.json`
- `capital-path-readiness	automation/capital-path-readiness-last-run	capital_path_readiness.json`

## Local Sidecar Replay

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/public_data_input_quality_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/${ref}:${file}" > "${tmpdir}/${key}.txt" 2>/dev/null || true
done
uv run python scripts/public_data_input_quality_probe.py \
  --sidecar-dir "${tmpdir}" \
  --repo-root . \
  --json \
  | jq '{overall_status, completed_candidate_id, gates:[.validation_gates[] | {id:.gate_id,status:.status}]}'
```

Expected with current sidecars:

- `completed_candidate_id` is `candidate-public-data-input-quality-contract`.
- Core public-data evidence parses successfully.
- No broker, order, capital, live strategy, secret, or external collection side effects occur.

## Released-Work Closure

```bash
uv run python scripts/released_work_probe.py --repo-root . --json \
  | jq '[.released_work[] | select(.candidate_id=="candidate-public-data-input-quality-contract")]'
```

Expected after tasks are complete:

- released-work includes `candidate-public-data-input-quality-contract`.

## Autonomous-Work Advancement

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/autonomous_work_execution_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/${ref}:${file}" > "${tmpdir}/${key}.md" 2>/dev/null || true
done
uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "${tmpdir}" \
  --repo-root . \
  --json \
  | jq '.selected_work.candidate_id'
```

Expected after released-work sees the completion marker:

- selected candidate advances to `candidate-regime-timeline-coverage-contract`.

## Safety

This feature only reads existing sidecar snapshots and emits a contract report. It must not submit orders, call broker APIs, allocate capital, change live strategy, widen whitelist/caps, touch secrets, modify constitution/kernel files, or run fresh public-data collection.
