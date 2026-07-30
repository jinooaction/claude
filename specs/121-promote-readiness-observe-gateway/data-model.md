# Data Model: Promote Readiness Observe Gateway

## Promotion Readiness Report

- **Represents**: The sidecar record showing whether the VI live track-record gate is ready.
- **Fields**:
  - `run_id`: GitHub Actions run id.
  - `commit`: Commit evaluated by the workflow.
  - `trigger`: Schedule or manual dispatch.
  - `timestamp_utc`: Publication time.
  - `ready`: Boolean readiness decision derived from the command exit code.
  - `ssh_exit`: Raw SSH/helper exit code.
  - `stdout_json`: JSON emitted by promotion readiness evaluation.
  - `stderr`: Diagnostic text, redacted before publication.
- **State rules**:
  - Exit 0 means READY true.
  - Exit 1 means READY false and is a normal reportable state.
  - Exit codes other than 0 or 1 mean setup or infrastructure error.

## Gateway Command

- **Represents**: A single fixed SSH command accepted by the server forced-command gateway.
- **Fields**:
  - `command`: Must be exactly `observe promote-readiness`.
  - `arguments`: Must be empty.
  - `target_helper`: The installed observation helper.
- **Validation rules**:
  - Unknown commands are refused with exit 126.
  - Any argument-bearing variant is refused with exit 126.
  - The command must not pass caller-controlled paths, capital, mode, or flags.

## Observation Helper Command

- **Represents**: The server-side action that evaluates readiness using fixed production evidence.
- **Fields**:
  - `db_path`: Fixed production audit database path.
  - `rules_path`: Fixed production canary rules path.
  - `capital`: Fixed existing readiness capital value.
  - `output_format`: JSON.
- **Validation rules**:
  - The helper does not submit orders.
  - The helper does not arm live trading.
  - The helper does not change capital or configuration.
  - The helper does not control system services.
  - The helper does not print secret values.

## Safety Boundary

- **Represents**: The unchanged protections around real money.
- **Fields**:
  - `orders`: unchanged and unavailable through this path.
  - `live_arming`: unchanged and unavailable through this path.
  - `capital_allocation`: unchanged and unavailable through this path.
  - `whitelist_caps`: unchanged and unavailable through this path.
  - `secrets`: unchanged and never printed.
