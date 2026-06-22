# Data Model: Money Path State Guard

## LiveMoneyState

Represents the top-level real-money status that appears before the older ladder readiness section.

Fields:
- `status`: `REAL_ORDER_PATH_ARMED`, `PREVIEW_ONLY`, `BLOCKED`, or `UNKNOWN`.
- `can_submit_real_orders`: boolean. True only when a non-push workflow execution can reach live order submission after preflight and safety gates.
- `path`: human-readable path name, currently `micro-gtaa-live-canary`.
- `capital_usd`: declared capital from the sentinel, if valid.
- `max_capital_usd`: fixed micro authority limit, currently 1,000.
- `next_scheduled_live_utc`: next weekday 15:00 UTC candidate, or null if not armed.
- `required_gates`: stable list of gates that still must pass before live order submission.
- `last_run`: optional `MicroGtaaRunEvidence`.

Validation:
- `armed:true` plus `1 <= capital_usd <= 1000` maps to `REAL_ORDER_PATH_ARMED`.
- `armed:false` maps to `PREVIEW_ONLY`.
- invalid capital maps to `BLOCKED`.
- missing or unparsable sentinel maps to `UNKNOWN`.

## MicroGtaaRequest

Parsed from `automation/rebalance-micro-gtaa.request`.

Fields:
- `armed`
- `capital_usd`
- `stage`
- `run_seq`
- `warning_drawdown_pct`
- `hard_stop_drawdown_pct`
- `note`

## MicroGtaaRunEvidence

Parsed from `automation/rebalance-micro-gtaa-last-run`.

Fields:
- `run_id`
- `timestamp_utc`
- `event`
- `live_step`
- `preflight_ok`
- `preflight_reason`
- `breaker_reason`
- `order_states`
- `accepted_or_filled_count`
- `broker_rejected_count`

Validation:
- Missing preflight evidence is allowed for older sidecars and must be explicit as unknown.
- Job success does not imply accepted orders; order states decide accepted/fill evidence.

## MoneyPathReport Extension

Adds `live_money_state` to the existing report JSON and a first text section named `실제 돈 최상위 상태`.
