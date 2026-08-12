# Quickstart: Validation Failure Promotion Recheck Contract

## Prepare latest sidecars

```bash
mkdir -p /tmp/validation-failure-promotion-recheck
git fetch origin \
  automation/autonomous-evolution-last-run \
  automation/autonomous-promotion-last-run \
  automation/candidate-implementation-results
git show origin/automation/autonomous-evolution-last-run:learning_ledger.json > /tmp/validation-failure-promotion-recheck/learning_ledger.json
git show origin/automation/autonomous-promotion-last-run:promotion_summary.json > /tmp/validation-failure-promotion-recheck/promotion_summary.json
git show origin/automation/candidate-implementation-results:candidate_results.json > /tmp/validation-failure-promotion-recheck/candidate_results.json
```

## Run the contract

```bash
uv run python scripts/validation_failure_promotion_recheck_probe.py \
  --learning-ledger /tmp/validation-failure-promotion-recheck/learning_ledger.json \
  --promotion-summary /tmp/validation-failure-promotion-recheck/promotion_summary.json \
  --result-evidence /tmp/validation-failure-promotion-recheck/candidate_results.json \
  --summary-out /tmp/validation-failure-promotion-recheck/SUMMARY.md \
  --json-out /tmp/validation-failure-promotion-recheck/promotion_recheck.json \
  --json
```

Expected current evidence:

- `overall_status == "CONTRACT_READY"`
- `completed_candidate_id == "candidate-broad-validation-failure-promotion-recheck-contract"`
- `candidate_count == 2`
- `suppressed_count == 2`
- `allowed_recheck_count == 0`
- candidate ids include `candidate-1ed634d8bf6d` and `candidate-cc96b35062da`

## Next autonomous-work state

After this spec is merged and released-work scans the completion marker, autonomous-work should not select this child again:

```text
candidate-broad-validation-failure-promotion-recheck-contract
```
