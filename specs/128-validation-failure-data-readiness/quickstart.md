# Quickstart: Validation Failure Data Readiness Contract

## Prepare latest sidecars

```bash
mkdir -p /tmp/validation-failure-data-readiness
git fetch origin \
  automation/candidate-implementation-factory-last-run \
  automation/candidate-implementation-results \
  automation/public-data \
  automation/regime-stratify-last-run
git show origin/automation/candidate-implementation-factory-last-run:candidate_packages.json > /tmp/validation-failure-data-readiness/candidate_packages.json
git show origin/automation/candidate-implementation-results:candidate_results.json > /tmp/validation-failure-data-readiness/candidate_results.json
git show origin/automation/public-data:LAST_RUN.md > /tmp/validation-failure-data-readiness/public-data-LAST_RUN.md
git show origin/automation/regime-stratify-last-run:LAST_RUN.md > /tmp/validation-failure-data-readiness/regime-stratify-LAST_RUN.md
```

## Run the contract

```bash
uv run python scripts/validation_failure_data_readiness_probe.py \
  --package-plan /tmp/validation-failure-data-readiness/candidate_packages.json \
  --result-evidence /tmp/validation-failure-data-readiness/candidate_results.json \
  --public-data /tmp/validation-failure-data-readiness/public-data-LAST_RUN.md \
  --regime-stratify /tmp/validation-failure-data-readiness/regime-stratify-LAST_RUN.md \
  --summary-out /tmp/validation-failure-data-readiness/SUMMARY.md \
  --json-out /tmp/validation-failure-data-readiness/data_readiness.json \
  --json
```

Expected current evidence:

- `overall_status == "CONTRACT_READY"`
- `completed_candidate_id == "candidate-broad-validation-failure-data-readiness-contract"`
- `package_count == 2`
- `surface_count == 3`
- `data_ready_count == 2`

## Next autonomous-work state

After this spec is merged and released-work scans the completion marker, autonomous-work should advance from data readiness to:

```text
candidate-broad-validation-failure-package-kind-expansion-contract
```
