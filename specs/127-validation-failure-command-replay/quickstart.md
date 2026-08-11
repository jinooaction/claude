# Quickstart: Validation Failure Command Replay Contract

## 1. Fetch current sidecar files

```bash
tmpdir="$(mktemp -d)"
git show origin/automation/candidate-implementation-factory-last-run:candidate_packages.json > "$tmpdir/candidate_packages.json"
git show origin/automation/candidate-implementation-results:candidate_results.json > "$tmpdir/candidate_results.json"
```

## 2. Build the contract

```bash
uv run python scripts/validation_failure_command_replay_probe.py \
  --package-plan "$tmpdir/candidate_packages.json" \
  --result-evidence "$tmpdir/candidate_results.json" \
  --json
```

Expected current result:

- `overall_status == "CONTRACT_READY"`
- `completed_candidate_id == "candidate-broad-validation-failure-command-replay-contract"`
- `package_count == 2`
- `command_count == 4`
- `replay_safe_count == 4`
- `missing_execution_count == 4`

## 3. Confirm autonomous-work next child after release marker

After this spec is merged and released-work scans the completion marker, autonomous-work should advance from command replay to:

```text
candidate-broad-validation-failure-data-readiness-contract
```

This is still no-live. It does not place orders, rearm live trading, allocate capital, change whitelist/caps, or read/write secrets.
