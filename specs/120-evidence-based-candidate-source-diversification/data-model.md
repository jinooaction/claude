# Data Model: Evidence-Based Candidate Source Diversification

## EvidenceBasedWorkPacket

- `candidate_id`: stable identifier for the synthesized work candidate.
- `title_ko`: operator-readable Korean title.
- `status`: `EXECUTION_READY`, `OBSERVATION_WAIT`, `BLOCKED`, `RELEASED`, or `SUPPRESSED`.
- `risk_grade`: operating-risk grade; expected value is 2 unless safety surfaces are detected.
- `reason_ko`: why this packet exists now, grounded in current sidecar evidence.
- `next_action_ko`: the next safe Codex action in Korean.
- `required_inputs`: sidecar refs needed to reproduce the decision.
- `source_refs`: sidecar refs cited in the report.
- `safety_boundary`: invariants showing no live-money action is authorized.
- `blocked_package_refs`: package-level validation blockers included in the packet.

Validation:
- Must not be `EXECUTION_READY` if any required input is malformed and no safe fallback exists.
- Must not include account-scale, token, host, or private-key values.
- Must not claim live-money readiness when money-path is `PREVIEW_ONLY` or forward verdict is `NO_EDGE`.

## ValidationFailureGroup

- `reason_code`: normalized diagnostic code such as `execution_failed`.
- `summary_ko`: grouped Korean explanation.
- `package_count`: number of packages with this cause.
- `retryable_count`: number of retryable packages in the group.
- `safe_action_codes`: distinct safe next-action codes.
- `package_refs`: package-level references.

Validation:
- Grouping must not erase candidate ID, package ID, or package kind.
- A group is safe to auto-run only if every included next action is marked safe.

## BlockedPackageRef

- `candidate_id`: source candidate identifier.
- `package_id`: validation package identifier.
- `package_kind`: package kind, such as `strategy_backtest` or `portfolio_backtest`.
- `status`: expected to be `blocked`.
- `retryable`: whether the evidence says the package can be revisited automatically.
- `diagnostic_codes`: normalized diagnostic codes.
- `next_action_codes`: normalized next-action codes.
- `source_key`: sidecar family that produced the evidence.

Validation:
- Missing `candidate_id` or `package_id` excludes the row from grouping.
- Unsupported package kinds remain visible as blockers but do not become live-money instructions.

## SafetyContext

- `live_money_status`: high-level money path state when available.
- `capital_ladder_stage`: capital ladder stage when available.
- `forward_verdict`: forward edge verdict when available.
- `protected_workflow_state`: live workflow pending/waiting state when available.
- `safety_message_ko`: operator-facing explanation of why the packet stays read-only.

Validation:
- `PREVIEW_ONLY`, `NO_EDGE_YET`, `WAIT_EDGE`, `pending`, and `waiting` never authorize real orders.
