# Data Model: Investment Edge Frontier Map

## InvestmentEdgeFrontierMapEntry

Represents one no-live investment-edge experiment area.

- `frontier_key`: Stable machine key for the experiment area.
- `label_ko`: Korean label shown in Markdown.
- `coverage_status`: One of `open` or `released`.
- `priority_score`: Deterministic priority for the generated candidate.
- `recommended_candidate_id`: Candidate to generate when this entry is the highest-priority unreleased entry.
- `title_ko`: Title for the generated work packet.
- `reason_ko`: Why this experiment area is next.
- `next_action_ko`: What the next Codex work should implement or validate.
- `required_inputs`: Evidence refs required before implementing the experiment candidate.

## Investment Edge Experiment Candidate

Generated `WorkPacket` derived from the selected `InvestmentEdgeFrontierMapEntry`.

- Always risk grade 2.
- Always no safety impact.
- Always read-only and SDD-gated through existing completion gates.
- Required inputs include forward paper, money-path, released-work, learning ledger, and pipeline liveness.

## Completed Candidate Marker

The contract marker consumed by released-work:

- `completed_candidate_id: candidate-investment-edge-frontier-map`

This closes the implementation of the investment-edge frontier map itself. It must not close `candidate-forward-regime-edge-experiment`.

## State Transitions

- Regenerator not released -> `candidate-macro-candidate-map-regenerator` remains selected.
- Regenerator released, investment-edge frontier not released -> `candidate-investment-edge-frontier-map` remains selected.
- Investment-edge frontier released -> first unreleased investment-edge experiment candidate is selected.
- All investment-edge experiment candidates released -> next unreleased macro-domain frontier candidate is selected.
- Higher-priority repair, regular, operator-approval, or blocked packets still win.
