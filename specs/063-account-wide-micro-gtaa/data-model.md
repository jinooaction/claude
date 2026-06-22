# Data Model: Account-Wide Micro GTAA Autonomous Rebalance

## AccountWideSettings

Represents account-wide behavior configured for the micro live canary.

Fields:
- `enabled`: whether account-wide broker snapshot planning is active.
- `liquidation_symbols`: explicit symbols that may be sold but not bought.
- `cash_buffer_pct`: buffer applied to planned buy notional before buy eligibility.
- `default_side`: execution side mode, one of `both`, `sell`, or `buy`.

Validation:
- `liquidation_symbols` must not overlap the portfolio target universe.
- `liquidation_symbols` must be explicit uppercase symbols.
- `cash_buffer_pct` must be non-negative and defaults to `0.01`.
- A liquidation-only symbol appearing in a buy order is a configuration or planning error.

## BrokerAccountSnapshot

Represents KIS account state read before an account-wide run.

Fields:
- `timestamp_utc`: snapshot time.
- `purchasable_cash_usd`: KIS-confirmed purchasable USD cash.
- `total_equity_usd`: broker account equity when available.
- `positions`: list of broker holdings with symbol, quantity, average price, latest quote, and market.
- `source`: broker/read-only source identifier.

Validation:
- Missing cash or missing position data fails closed before live orders.
- Quantities must be non-negative.
- Every position used for a sell plan must have a current quote.

## HoldingClassification

Represents the role assigned to each broker holding.

Fields:
- `symbol`: holding symbol.
- `role`: `target`, `liquidation_only`, or `unmanaged`.
- `quantity`: broker quantity.
- `quote`: latest quote when needed for planning.
- `reason`: explanation shown in sidecar evidence.

Validation:
- `target` symbols are the only symbols eligible for buys.
- `liquidation_only` symbols are eligible for sells only.
- `unmanaged` symbols cannot generate orders.

## AccountWideRebalancePlan

Represents the plan produced from the snapshot and portfolio target.

Fields:
- `mode`: `account_wide` or `ledger_only`.
- `requested_side`: `both`, `sell`, or `buy`.
- `effective_side`: actual side allowed for this cycle after cash evaluation.
- `planned_sell_notional_usd`: sell candidate notional.
- `planned_buy_notional_usd`: buy candidate notional.
- `required_cash_usd`: planned buys plus buffer.
- `purchasable_cash_usd`: broker-confirmed cash.
- `orders`: routed order candidates with symbol, side, quantity, limit price, and reason.
- `withheld_orders`: orders withheld because of side mode, cash shortfall, unmanaged holding, or safety guard.
- `next_step`: expected next autonomous action.

Validation:
- When `purchasable_cash_usd < required_cash_usd` and sell candidates exist, `effective_side` must be `sell`.
- When `effective_side == sell`, buy orders must be withheld.
- When `effective_side == buy`, sell orders must be withheld.
- When no order is submitted, `next_step` must explain whether the loop is waiting for cash, market session, broker recovery, or target drift.

## ExecutionCycleEvidence

Represents sidecar and Telegram-visible evidence for one run.

Fields:
- `account_wide_enabled`: whether broker snapshot planning was used.
- `broker_snapshot_summary`: cash, total equity, and position summary with no secrets.
- `classification_summary`: target, liquidation-only, and unmanaged symbols.
- `preflight`: cash requirement, available cash, buffer, and ok flag.
- `execution_side`: requested and effective side.
- `live_results`: accepted, filled, rejected, skipped, and withheld counts.
- `next_step`: what the next scheduled or manual run should do.

Validation:
- Evidence must not expose account numbers, tokens, or secret material.
- Evidence is present for preview-only, sell-only, buy-ready, blocked, and broker-error outcomes.
