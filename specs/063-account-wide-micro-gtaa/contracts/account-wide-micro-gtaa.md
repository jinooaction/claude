# Contract: Account-Wide Micro GTAA Autonomous Rebalance

## Portfolio Config Contract

Path: `deploy/micro-gtaa-live-portfolio.toml`

Required behavior:
- Portfolio target universe remains exactly `SPYM`, `IEF`, `GLDM`.
- Target buys are allowed only for target universe symbols.
- Account-wide settings declare liquidation-only legacy symbols separately from the target universe.
- Liquidation-only symbols may be routed only as sell orders.
- The config is invalid if target symbols and liquidation-only symbols overlap.
- The capital cap remains no greater than `1000` USD.
- Order types remain `LIMIT` and sessions remain `REGULAR`.

## CLI Contract

Command shape:

```bash
auto-invest rebalance-once \
  --portfolio deploy/micro-gtaa-live-portfolio.toml \
  --capital 1000 \
  --account-wide \
  --side both \
  --dry-run
```

Rules:
- `--account-wide` makes the command read KIS positions and purchasable cash before planning, including in dry-run mode.
- Dry-run with `--account-wide` may perform read-only broker calls but must not submit orders.
- `--side both` allows the planner to choose sell-only when cash is insufficient.
- `--side sell` submits or previews only eligible sell orders.
- `--side buy` submits or previews only eligible target-universe buy orders and only after the cash preflight passes.
- Any buy for a liquidation-only symbol fails closed before broker submission.
- Output `effective_side` may be `both`, `sell`, `buy`, or `none`; `none` means all orders were withheld before broker submission.

## Workflow Contract

Path: `.github/workflows/rebalance-micro-gtaa-canary.yml`

Required behavior:
- Push-triggered runs remain preview-only.
- The preview step uses account-wide dry-run so legacy holdings and current cash appear in the plan.
- The preflight step computes planned buys, planned sells, required cash, current KIS purchasable cash, and selected effective side.
- If planned buys exceed current cash plus the 1% buffer and eligible sells exist, the live step runs sell-only.
- If planned buys exceed current cash plus the 1% buffer and no eligible sells exist, the live step is blocked.
- If cash is sufficient and safety gates are clear, the live step may run buys for target universe symbols.
- The existing circuit breaker remains before any live mutating step.
- Live order submission still requires `armed == true`, non-push event, US regular session, successful preflight, breaker clear, caps, and whitelist.

## Sidecar Contract

Path: `automation/rebalance-micro-gtaa-last-run` branch, `LAST_RUN.md`

Required fields or sections:
- `account_wide_enabled`
- `execution_side_requested`
- `execution_side_effective`
- `purchasable_cash_usd`
- `required_cash_usd`
- `planned_buy_notional_usd`
- `planned_sell_notional_usd`
- `classification_summary`
- `withheld_orders`
- `next_step`

Rules:
- Sidecar must distinguish workflow-step success from broker acceptance or fill.
- Sidecar must report when a run is sell-only and why buys were withheld.
- Sidecar must report `execution_side_effective=none` when preflight blocks all orders.
- Sidecar must report unmanaged holdings without placing orders for them.
- Sidecar must avoid credentials and raw account numbers.

## Test Contract

Required automated checks:
- Account-wide planner sells liquidation-only holdings when cash is insufficient and withholds buys.
- Planner refuses to buy liquidation-only symbols.
- Portfolio config keeps target universe separate from liquidation-only settings.
- Workflow preview uses `--account-wide`.
- Workflow live step can run `--side sell` when preflight selects sell-only.
- Workflow push events remain preview-only.
- Existing full test and lint gates pass.
