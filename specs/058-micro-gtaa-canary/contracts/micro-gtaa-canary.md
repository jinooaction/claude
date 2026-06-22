# Contract: Micro GTAA Live Canary

## Sentinel Contract

Path: `automation/rebalance-micro-gtaa.request`

Required fields:

```yaml
armed: false
capital_usd: 1000
requested_by: mason
stage: micro-gtaa-live-canary
run_seq: 1
warning_drawdown_pct: 3
hard_stop_drawdown_pct: 5
note: "..."
```

Rules:
- `armed` must be `true` or `false`.
- Committed default must be `armed: false`.
- `capital_usd` must be an integer no greater than `1000`.
- `warning_drawdown_pct` must be below `hard_stop_drawdown_pct`.
- `hard_stop_drawdown_pct` must be no greater than `5`.

## Workflow Contract

Path: `.github/workflows/rebalance-micro-gtaa-canary.yml`

Triggers:
- `schedule`: US regular-session window.
- `workflow_dispatch`: explicit operator/manual run.
- `push` on `automation/rebalance-micro-gtaa.request`: preview-only.

Required behavior:
- Reads sentinel before touching broker runtime.
- Blocks if manual capital exceeds 1,000 USD.
- Installs SSH key only after guard passes.
- Backfills micro universe bars.
- Runs `rebalance-once --dry-run` before any live step.
- Evaluates the existing audit-log circuit breaker before any live step and sets
  `data/halt.flag` if the 3% daily loss or 5% total drawdown policy is breached.
- Runs live step only when:
  - `armed == true`
  - guard is not blocked
  - pre-live circuit breaker gate succeeded
  - event is not `push`
- Publishes a sidecar `automation/rebalance-micro-gtaa-last-run`.

## Portfolio Contract

Path: `deploy/micro-gtaa-live-portfolio.toml`

Required invariants:
- Whitelist symbols are exactly `SPYM`, `IEF`, `GLDM`.
- Portfolio universe is exactly `SPYM`, `IEF`, `GLDM`.
- Order types are exactly `LIMIT`.
- Sessions are exactly `REGULAR`.
- `weight_scheme = "equal"`.
- `top_n = 3`.
- `rebalance_mode = "hold_replace"`.
- Trend filter uses `method = "sma"`, `on_insufficient = "cash"`, and `ensemble_windows = [63, 126, 189, 252]`.

## Test Contract

Required automated checks:
- Sentinel default is unarmed and under capital/stop limits.
- Micro portfolio loads through the existing portfolio loader and respects whitelist invariants.
- Workflow live step is gated by `armed == true` and `github.event_name != 'push'`.
- Workflow contains a dry-run preview step before the live step.
- Workflow contains an audit-log circuit breaker check before the live step.
