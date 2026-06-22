# Quickstart: Account-Wide Micro GTAA Autonomous Rebalance

## 1. Validate Account-Wide Planning

```bash
uv run pytest tests/integration/test_spec_032_live_rebalancer.py tests/unit/test_canary_portfolio_config.py
```

Expected:
- The micro GTAA target universe remains `SPYM`, `IEF`, `GLDM`.
- Liquidation-only legacy symbols are separate from target buys.
- Low cash with liquidation-only holdings produces sell-only behavior.
- A liquidation-only symbol cannot become a buy order.

## 2. Validate Workflow Safety

```bash
uv run pytest tests/unit/test_micro_gtaa_canary.py
```

Expected:
- The account-wide preview uses read-only broker evidence.
- Push-triggered runs still skip live orders.
- Preflight can choose sell-only when cash is insufficient.
- The live step still requires sentinel arming, regular session, preflight, breaker, caps, and whitelist.

## 3. Manual Read-Only Preview

Use this only in an environment with KIS read secrets available:

```bash
auto-invest rebalance-once \
  --portfolio deploy/micro-gtaa-live-portfolio.toml \
  --capital 1000 \
  --account-wide \
  --side both \
  --dry-run
```

Expected:
- The command may read KIS positions and cash.
- It must not submit orders.
- If current cash cannot fund buys and liquidation-only holdings exist, the effective action is sell-first.

## 4. Stop Further Real Orders

Set `automation/rebalance-micro-gtaa.request`:

```yaml
armed: false
```

Expected:
- Future scheduled and manual runs become preview-only.
- Existing audit history and sidecar records remain intact.

## 5. Full Validation Before Merge

```bash
uv run pytest
uv run ruff check src tests
python3 scripts/check_pr_quality_gate.py --template .github/pull_request_template.md
```
