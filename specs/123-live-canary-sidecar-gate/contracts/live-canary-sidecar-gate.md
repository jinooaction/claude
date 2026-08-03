# Contract: Live Canary Sidecar Gate

## Workflow Boundary

Path: `.github/workflows/rebalance-live-canary.yml`

The workflow must expose two distinct jobs:

1. Preview/status job
   - Reads the live sentinel and capital guard.
   - Calls only fixed observe commands for preview/status server work.
   - Runs dry-run preview only.
   - Publishes `automation/rebalance-live-canary-last-run`.
   - Has no production environment approval.
   - Must not contain `--mode live --confirm-live`.

2. Real-order job
   - Depends on the preview/status job.
   - Runs only when:
     - preview output `armed` is `true`;
     - preview output `blocked` is not `true`;
     - event is not `push`;
     - production approval is granted.
   - Is the only job allowed to contain `--mode live --confirm-live`.
   - Publishes the production result to the same sidecar branch after execution.

## Sidecar Contract

Branch: `automation/rebalance-live-canary-last-run`

The sidecar must include:

- run id;
- timestamp;
- armed state;
- capital;
- blocked state;
- event;
- live step;
- dry-run preview section;
- live rebalance result section;
- live-track measurement section.

Preview/status sidecars must say real orders are skipped in the preview job and owned by the production-gated job. Production sidecars must report the actual live rebalance result or the actual production failure.

## Forced-Command Gateway Contract

The gateway may expose these preview/status commands:

```text
observe live-canary-backfill
observe live-canary-preview <capital>
observe live-canary-measure <capital>
```

`<capital>` must be a decimal number. These commands must map to fixed helper functions; no caller-controlled portfolio path, DB path, mode, order flag, or shell fragment is allowed.

## Safety Contract

This feature must not:

- Submit real orders from the preview/status job.
- Remove production approval from real orders.
- Change capital ladder authority or drawdown budget.
- Change whitelist, caps, account allowlist, strategy fingerprint gates, or broker order code.
- Approve a production environment job.
- Arm live trading.
- Commit or print secrets.
- Reopen arbitrary SSH command execution.
