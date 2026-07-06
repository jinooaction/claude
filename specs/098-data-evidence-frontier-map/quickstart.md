# Quickstart: Data Evidence Frontier Map

## Focused Tests

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py tests/integration/test_autonomous_work_execution_probe.py
```

## Probe Manifest

```bash
uv run python scripts/autonomous_work_execution_probe.py --manifest
```

Expected manifest includes:

- `public-data	automation/public-data	LAST_RUN.md`
- `regime-stratify	automation/regime-stratify-last-run	LAST_RUN.md`

## Local Sidecar Replay

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/autonomous_work_execution_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/${ref}:${file}" > "${tmpdir}/${key}.md" 2>/dev/null || true
done
uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "${tmpdir}" \
  --repo-root . \
  --json \
  | jq '{selected_candidate:.selected_work.candidate_id,data_evidence_frontier_map:.data_evidence_frontier_map}'
```

Before this spec is scanned as released, `selected_candidate` should remain `candidate-data-evidence-frontier-map`. After released-work sees the completion marker, the next regenerated candidate can be selected.

## Released-Work Closure

```bash
uv run python scripts/released_work_probe.py --repo-root . --json \
  | jq '[.released_work[] | select(.candidate_id=="candidate-data-evidence-frontier-map")]'
```

Expected after tasks are complete:

- released-work includes `candidate-data-evidence-frontier-map`.

## Safety

This feature only reads existing sidecar snapshots and emits work packets. It must not submit orders, call broker APIs, allocate capital, change live strategy, widen whitelist/caps, touch secrets, modify constitution/kernel files, or run fresh public-data collection.
