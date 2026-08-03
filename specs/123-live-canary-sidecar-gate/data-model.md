# Data Model: Live Canary Sidecar Gate

## Entity: LiveCanaryWorkflowRun

- **run_id**: GitHub Actions run identifier.
- **event_name**: Schedule, manual dispatch, sentinel push, or other workflow event.
- **armed**: Whether the sentinel authorizes live canary orders.
- **capital**: Capital value read from the sentinel and validated by the workflow.
- **blocked**: Whether the capital guard rejects the run.

## Entity: PreviewStatusJob

- **authority**: May read sentinel state, call fixed live-canary observe commands, run dry-run preview, run unarmed live-track measurement, and publish the sidecar.
- **forbidden_actions**: Must not run live order commands or report real-order execution.
- **sidecar_status**: Publishes `preview-job-skipped` as the live step.

## Entity: LiveCanaryObserveCommand

- **verbs**: `live-canary-backfill`, `live-canary-preview <capital>`, `live-canary-measure <capital>`.
- **allowed_actions**: Live universe backfill, dry-run preview, NAV snapshot, and forward verdict.
- **forbidden_actions**: Live order submission, live arming, capital ladder mutation, whitelist/caps mutation, arbitrary shell evaluation, and service control.

## Entity: RealOrderJob

- **authority**: May run the live order command only after production approval and only when the preview job reported `armed=true`, capital not blocked, and event not push.
- **post_order_measurement**: Writes live-track measurement after the live order command completes.
- **sidecar_status**: Publishes the production live result and overwrites the preview sidecar for the same workflow run.

## Entity: LiveCanarySidecar

- **branch**: `automation/rebalance-live-canary-last-run`.
- **fields**: run id, timestamp, armed state, capital, blocked state, event, live step, dry-run preview, live rebalance result, live-track measurement.
- **reader_contract**: A reader must be able to tell preview-only status from real-order execution without reading workflow logs.

## State Transitions

1. Workflow starts and reads the sentinel.
2. Preview/status job calls fixed observe commands through the SSH gateway.
3. Preview/status job publishes dry-run status and sidecar evidence.
4. If `armed=false`, `blocked=true`, or event is `push`, the real-order job does not start.
5. If `armed=true`, `blocked=false`, and event is not `push`, the real-order job waits for production approval.
6. If approved, the real-order job runs the live command, measures after orders, and publishes the production sidecar.
7. Pipeline liveness consumes the sidecar timestamp and status.

## Explicit Non-Entities

- Capital ladder rules and drawdown budget are not part of this feature.
- Whitelist, caps, broker order code, and strategy fingerprint logic are not part of this feature.
- Production approval policy itself is not removed or weakened for real orders.
