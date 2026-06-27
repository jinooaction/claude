# Data Model: Micro GTAA Intent-Loss Gate

## Micro GTAA Arming Sentinel

- `armed`: whether the micro workflow may reach live order submission.
- `capital_usd`: maximum capital for the micro canary.
- `requested_by`: operator identity recorded for audit.
- `stage`: live canary stage label.
- `run_seq`: monotonically updated operational sequence.
- `warning_drawdown_pct`, `hard_stop_drawdown_pct`: existing drawdown thresholds.
- `note`: human-readable reason for the current state.

Validation:

- `armed:false` means live order submission must not occur.
- `capital_usd` must remain between 1 and 1000.
- `hard_stop_drawdown_pct` must remain at or below 5.

## Opportunity Monitor Summary

- `verdict`: cumulative classification such as `INSUFFICIENT_DATA`, `STRATEGY_REVIEW`, or `EXECUTION_REVIEW`.
- `latest_signal`: latest valued attempt signal such as `INTENT_LOSS`, `INTENT_GAIN`, or `FLAT_OR_UNVALUED`.
- `cumulative.total_intended_order_mark_pnl_usd`: cumulative diagnostic mark PnL.
- `streaks.intent_loss`: consecutive negative valued run count.
- `latest.run_id`: latest valued or recorded run identifier.

Validation:

- `latest_signal=INTENT_LOSS` blocks live orders.
- `verdict=STRATEGY_REVIEW` blocks live orders.
- Missing monitor data is not positive approval.

## Intent-Loss Gate Decision

- `ok`: whether this gate allows the workflow to continue toward live submission.
- `reason`: concise machine-readable reason.
- `blocking_reasons`: list of blocking conditions.
- `verdict`, `latest_signal`, `cumulative_pnl_usd`, `latest_run_id`: copied evidence fields.
- `next_action_ko`: operator-readable next action.
- `safety_note_ko`: operator-readable note that the gate only blocks orders.

Validation:

- `ok:false` must prevent preflight, circuit breaker, and live order submission.
- The decision must be publishable without secrets.

## Micro GTAA Sidecar

- `LAST_RUN.md`: human-readable latest run evidence.
- `opportunity_history.json`: bounded rejected-order opportunity history.
- `opportunity_monitor.json`: latest cumulative monitor summary.

Validation:

- If live did not produce a result JSON, history is summarized but not appended.
- `LAST_RUN.md` includes the intent-loss gate decision.
