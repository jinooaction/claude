# Quickstart: Forward Paper Ledger Integrity

## Local validation

```bash
uv run pytest tests/integration/test_forward_verdict_cli.py tests/unit/test_candidate_history_support.py tests/integration/test_candidate_result_executor_probe.py tests/unit/test_security_workflow_hardening.py tests/unit/test_forward_workflow_leaderboard_json.py -q
uv run ruff check src tests
ruby -e 'require "yaml"; Dir[".github/workflows/*.yml"].each { |f| YAML.load_file(f) }; puts "yaml-ok"'
bash -n deploy/observe-on-instance.sh
```

## Production acceptance

1. Merge and confirm deployment of the exact main commit.
2. Dispatch `rebalance-paper-forward.yml` with capital 12000.
3. Verify each prep log uses `data/forward_v2_<track>.db` and reports nonnegative cash.
4. Verify all verdicts start from only the clean epoch and do not inherit legacy counts or PSR.
5. Refresh profit evidence and capital ladder. They must remain fail closed while clean observations are insufficient.
6. Confirm KIS smoke 5/5 and zero recent/open orders.

## Rollback

Revert the code mapping in a normal PR. Do not delete either legacy or clean database files and do not rewrite audit logs.
