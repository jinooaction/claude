# Quickstart: Micro GTAA Intent-Loss Gate

## 1. Confirm Immediate Disarm

```bash
sed -n '1,80p' automation/rebalance-micro-gtaa.request
```

Expected: `armed: false` and a note explaining the 2026-06-27 intent-loss stop.

## 2. Evaluate a Blocking Monitor

```bash
tmp="$(mktemp -d)"
cat > "$tmp/monitor.json" <<'JSON'
{"schema_version":1,"verdict":"INSUFFICIENT_DATA","latest_signal":"INTENT_LOSS","cumulative":{"total_intended_order_mark_pnl_usd":"-1.14"},"latest":{"run_id":"28253047287"}}
JSON
python3 scripts/opportunity_live_gate.py --monitor-json "$tmp/monitor.json" --format text
```

Expected: `ok=false`, with a reason mentioning latest `INTENT_LOSS`.

## 3. Run Focused Tests

```bash
uv run pytest tests/unit/test_opportunity_monitor.py tests/unit/test_micro_gtaa_canary.py tests/unit/test_micro_gtaa_telegram_alerts.py tests/integration/test_opportunity_monitor_cli.py
uv run ruff check src tests scripts/opportunity_live_gate.py scripts/opportunity_monitor_sidecar.py
```

## 4. Inspect Latest Sidecar After Next Run

```bash
git fetch origin automation/rebalance-micro-gtaa-last-run
git show origin/automation/rebalance-micro-gtaa-last-run:LAST_RUN.md
git show origin/automation/rebalance-micro-gtaa-last-run:opportunity_monitor.json
```

Expected after a blocked run: live result is not present, intent-loss gate section explains the block, and the prior monitor remains visible.
