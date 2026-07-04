# Data Model: Macro Candidate Map Regenerator

## MacroCandidateMapEntry

Represents one high-level exploration domain in the regenerated candidate map.

- `domain_key`: Stable machine key for the frontier domain.
- `label_ko`: Korean label shown in Markdown.
- `coverage_status`: One of `active`, `operator_or_blocked`, `exhausted`, or `underexplored`.
- `ready_count`: Number of execution-ready packets already present for the domain.
- `closed_count`: Number of released or suppressed packets in the domain.
- `released_count`: Number of released packets in the domain.
- `suppressed_count`: Number of suppressed packets in the domain.
- `priority_score`: Deterministic priority for the recommended frontier.
- `recommended_candidate_id`: Candidate to generate when this entry is the highest-priority unreleased frontier.
- `title_ko`: Title for the generated work packet.
- `reason_ko`: Why this domain should be explored.
- `next_action_ko`: What the next Codex work should do.

## Regenerated Candidate

Generated `WorkPacket` derived from the selected `MacroCandidateMapEntry`.

- Always risk grade 2.
- Always no safety impact.
- Always read-only and SDD-gated through existing completion gates.
- Required inputs are the existing macro growth source refs.

## Completed Candidate Marker

The contract marker consumed by released-work:

- `completed_candidate_id: candidate-macro-candidate-map-regenerator`

This closes the implementation of the map/regenerator itself. It must not close the map-derived next frontier candidate.

## State Transitions

- Existing regular candidate exists -> regular candidate remains selected.
- Operator approval or blocked candidate exists -> that candidate remains selected.
- Macro queue not exhausted -> existing macro sequence remains selected.
- Frontier discovery not released -> frontier discovery remains selected.
- Regenerator not released -> `candidate-macro-candidate-map-regenerator` is selected.
- Regenerator released -> first unreleased map-derived frontier candidate is selected.
