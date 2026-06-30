# Quickstart: Candidate Pending Next Actions

## Prepare support inputs locally

```bash
rm -rf /tmp/candidate_result_sidecars /tmp/candidate_result_public_data
mkdir -p /tmp/candidate_result_sidecars /tmp/candidate_result_public_data

uv run python scripts/pipeline_liveness_probe.py --manifest > /tmp/candidate_result_manifest.tsv
while IFS=$'\t' read -r key ref file; do
  [ -n "$key" ] || continue
  git show "origin/${ref}:${file}" > "/tmp/candidate_result_sidecars/${key}.md" 2>/dev/null || true
done < /tmp/candidate_result_manifest.tsv

git ls-tree -r --name-only origin/automation/public-data > /tmp/candidate_result_public_data_files.txt
while IFS= read -r file; do
  [ -n "$file" ] || continue
  mkdir -p "/tmp/candidate_result_public_data/$(dirname "$file")"
  git show "origin/automation/public-data:${file}" > "/tmp/candidate_result_public_data/${file}"
done < /tmp/candidate_result_public_data_files.txt
```

## Generate and execute current packages

```bash
uv run python scripts/candidate_factory_probe.py \
  --package-plan-out /tmp/candidate_packages_073.json \
  --json-out /tmp/candidate_factory_073.json

uv run python scripts/candidate_result_executor_probe.py \
  --package-plan /tmp/candidate_packages_073.json \
  --json-out /tmp/candidate_result_executor_073.json \
  --results-out /tmp/candidate_results_073.json \
  --summary-out /tmp/LAST_RUN_073.md \
  --timeout-seconds 60
```

Expected shape with current sidecars:

- `command_contract_error`: 0
- `execution_failed`: 0
- strategy/portfolio price-history candidates remain `pending` with `data_history_missing`
- no broker, order, capital, live config, whitelist/caps, sentinel, or secret writes
