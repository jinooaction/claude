# Quickstart: Rejected Opportunity Feedback Loop

## Local Monitor Reproduction

```bash
tmpdir=$(mktemp -d)
printf '{"schema_version":1,"records":[]}\n' > "$tmpdir/history.json"
uv run auto-invest opportunity-monitor \
  --history-json "$tmpdir/history.json" \
  --opportunity-json /tmp/micro_opportunity.json \
  --history-out "$tmpdir/opportunity_history.json" \
  --format json
```

Expected:
- `opportunity_history.json` contains the appended run record.
- stdout contains `verdict`, `latest_signal`, cumulative intended-order mark PnL, and safety notes.
- The command does not contact the broker and does not place orders.

## Workflow Sidecar State

```bash
git fetch origin automation/rebalance-micro-gtaa-last-run
git show origin/automation/rebalance-micro-gtaa-last-run:opportunity_monitor.json
git show origin/automation/rebalance-micro-gtaa-last-run:opportunity_history.json
```

Expected:
- `opportunity_monitor.json` is the latest cumulative verdict.
- `opportunity_history.json` is bounded rolling evidence for recent micro GTAA executions.

## Reassignment Feedback Evidence

```bash
git fetch origin automation/reassign-last-run
git show origin/automation/reassign-last-run:LAST_RUN.md
```

Expected:
- The reassignment sidecar includes the latest live execution feedback.
- A `STRATEGY_REVIEW` feedback verdict does not bypass the 5-gate reassignment decision.

## Validation Before Merge

```bash
uv run pytest tests/unit/test_opportunity_monitor.py tests/integration/test_opportunity_monitor_cli.py tests/unit/test_micro_gtaa_canary.py tests/unit/test_auto_reassign.py tests/unit/test_reassign_decide_cli.py tests/unit/test_reassign_workflow_leaderboard_json.py tests/unit/test_safety_command_registry.py
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
