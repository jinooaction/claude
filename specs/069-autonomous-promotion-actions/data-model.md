# Data Model: Autonomous Promotion Actions

## PromotionActionRun

- `schema_version`: string, currently `1.0`
- `run_id`: workflow or local run identifier
- `commit`: git commit used for the run
- `timestamp_utc`: ISO-8601 UTC timestamp
- `overall_status`: `ok` or `degraded`
- `actions`: list of `PromotionAction`
- `blocked`: list of `ActionBlock`
- `forward_registry_next`: next tracked registry state
- `canary_submissions_next`: next tracked submission state

## PromotionAction

- `kind`: `forward_registration`, `canary_submission`, or `existing_gate_report`
- `candidate_id`: source candidate
- `title_ko`: human title
- `status`: `registered`, `already_registered`, `submitted`, `already_submitted`, or `reported`
- `reason_ko`: Korean reason
- `payload`: action-specific machine data

## ForwardTrackRegistration

- `candidate_id`
- `track_key`: lowercase safe identifier
- `portfolio_path`: must be `deploy/*.toml`
- `db_path`: must be under `data/promotion_*.db`
- `halt_path`: must be under `data/promotion_*.halt.flag`
- `capital_usd`: positive bounded paper capital
- `max_symbols`: positive integer
- `min_bars`: positive integer
- `registered_at_utc`

## CanarySubmission

- `candidate_id`
- `portfolio_path`: must be `deploy/*.toml`
- `db_path`: must be under `data/promotion_canary_*.db`
- `halt_path`: must be under `data/promotion_canary_*.halt.flag`
- `bands_toml`: must be `config/*.toml`
- `status`: `pending`, `passed`, `failed`, or `blocked`
- `submitted_at_utc`

## ActionBlock

- `candidate_id`
- `stage`
- `field`
- `reason`
- `reason_ko`

## State Transitions

```text
FORWARD_REGISTRATION_READY + valid forward_track
  -> ForwardTrackRegistration(status registered)

FORWARD_REGISTRATION_READY + missing/unsafe forward_track
  -> ActionBlock

CANARY_CANDIDATE + valid canary_track
  -> CanarySubmission(status pending)

CANARY_CANDIDATE + missing/unsafe canary_track
  -> ActionBlock

EXISTING_GATE_READY
  -> PromotionAction(kind existing_gate_report)
```
