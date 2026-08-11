# Data Model: Broad Validation Failure Frontier

## BroadValidationFailureFrontierMap

- `entries`: deterministic list of frontier entries sorted by priority score then key.
- Exists on every autonomous-work report, but only emits a work packet after a broad validation-failure parent is released and retryable blocked packages remain.

## BroadValidationFailureFrontierMapEntry

- `frontier_key`: stable key such as `command_replay_contract`.
- `label_ko`: operator-readable Korean label.
- `work_domain_key`: work domain used by the emitted packet.
- `coverage_status`: `open` or `released` based on released-work.
- `priority_score`: deterministic ordering score.
- `recommended_candidate_id`: next candidate id.
- `title_ko`, `reason_ko`, `next_action_ko`: report text.
- `failure_codes`: diagnostic codes this row covers.
- `package_kinds`: package kinds this row covers.
- `review_axes`: breadth dimensions this row forces the next worker to inspect.
- `package_count`: matching blocked package count.
- `retryable_count`: matching retryable blocked package count.
- `required_inputs`: sidecar and repo inputs needed to act safely.

## Work Packet Transition

- Input parent marker: `candidate-broad-frontier-expansion-validation-failures-22f38b8629eb`.
- First child: `candidate-broad-validation-failure-command-replay-contract`.
- Second child after first child is released: `candidate-broad-validation-failure-data-readiness-contract`.
- Work packet keeps `blocked_package_refs` and `validation_failure_groups`.

## Completed Candidate Marker

`completed_candidate_id: candidate-broad-frontier-expansion-validation-failures-22f38b8629eb`
