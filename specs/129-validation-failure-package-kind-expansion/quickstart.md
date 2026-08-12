# Quickstart: Validation Failure Package-Kind Expansion Contract

## Prepare latest sidecars

```bash
mkdir -p /tmp/validation-failure-package-kind
git fetch origin \
  automation/candidate-implementation-factory-last-run \
  automation/candidate-implementation-results
git show origin/automation/candidate-implementation-factory-last-run:candidate_packages.json > /tmp/validation-failure-package-kind/candidate_packages.json
git show origin/automation/candidate-implementation-results:candidate_results.json > /tmp/validation-failure-package-kind/candidate_results.json
```

## Run the contract

```bash
uv run python scripts/validation_failure_package_kind_expansion_probe.py \
  --package-plan /tmp/validation-failure-package-kind/candidate_packages.json \
  --result-evidence /tmp/validation-failure-package-kind/candidate_results.json \
  --summary-out /tmp/validation-failure-package-kind/SUMMARY.md \
  --json-out /tmp/validation-failure-package-kind/package_kind_expansion.json \
  --json
```

Expected current evidence:

- `overall_status == "CONTRACT_READY"`
- `completed_candidate_id == "candidate-broad-validation-failure-package-kind-expansion-contract"`
- `package_count == 2`
- `bucket_count == 2`
- `retryable_count == 2`
- package kinds include `strategy_backtest` and `portfolio_backtest`

## Next autonomous-work state

After this spec is merged and released-work scans the completion marker, autonomous-work should advance from package-kind expansion to:

```text
candidate-broad-validation-failure-promotion-recheck-contract
```
