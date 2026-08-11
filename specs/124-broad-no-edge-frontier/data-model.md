# Data Model: Broad NO_EDGE Frontier

## BroadNoEdgeFrontierMapEntry

- `frontier_key`: deterministic short key for the unexplored area.
- `label_ko`: Korean operator-facing label.
- `work_domain_key`: target work domain such as `strategy_design` or `data_quality`.
- `coverage_status`: `open` or `released` based on released-work.
- `priority_score`: deterministic ranking score.
- `recommended_candidate_id`: candidate ID emitted when the entry is next.
- `title_ko`: Korean packet title.
- `reason_ko`: why this broad area matters after `NO_EDGE_YET`.
- `next_action_ko`: no-live next action.
- `review_axes`: explicit axes covered by the row.
- `required_inputs`: sidecar and data refs that must be read before doing the candidate.

## StableNoEdgeFingerprint

- Inputs: live money status, ladder stage, edge-autoarm status, forward verdict, and released-work candidates outside broad no-edge parent/follow-up IDs.
- Output: `candidate-broad-frontier-expansion-no-edge-<12-char-fingerprint>`.
- Invariant: adding the exact broad no-edge parent or its follow-up candidates to released-work must not change the parent fingerprint.

## BroadNoEdgeFollowUpPacket

- Derived from the first open `BroadNoEdgeFrontierMapEntry`.
- Status: `EXECUTION_READY`.
- Risk grade: `2`.
- Safety impact: empty.
- Safety boundary: existing safety invariants plus explicit no broker call, no order, no live rearm, and no capital allocation.
