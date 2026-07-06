# Data Model: Data Evidence Frontier Map

## DataEvidenceFrontierMapEntry

Represents one data input-quality work area.

- `frontier_key`: Stable machine key for the data evidence area.
- `label_ko`: Korean label shown in Markdown.
- `coverage_status`: One of `open` or `released`.
- `priority_score`: Deterministic priority for the generated candidate.
- `recommended_candidate_id`: Candidate to generate when this entry is the highest-priority unreleased entry.
- `title_ko`: Title for the generated work packet.
- `reason_ko`: Why this input-quality area is next.
- `next_action_ko`: What the next Codex work should implement or validate.
- `required_inputs`: Evidence refs required before implementing the input-quality candidate.

## Data Evidence Candidate

Generated `WorkPacket` derived from the selected `DataEvidenceFrontierMapEntry`.

- Always risk grade 2.
- Always no safety impact.
- Always read-only and SDD-gated through existing completion gates.
- Required inputs include public-data, regime-stratify, pipeline liveness, released-work, and capital-path readiness.

## Completed Candidate Marker

The contract marker consumed by released-work:

- `completed_candidate_id: candidate-data-evidence-frontier-map`

This closes the implementation of the data evidence frontier map itself. It must not close `candidate-public-data-input-quality-contract`.

## State Transitions

- Investment-edge frontier not released -> `candidate-investment-edge-frontier-map` or its nested experiment candidate remains selected.
- All investment-edge frontier experiment candidates released and data evidence frontier not released -> `candidate-data-evidence-frontier-map` remains selected.
- Data evidence frontier released -> first unreleased data evidence input-quality candidate is selected.
- All data evidence candidates released -> next unreleased macro-domain frontier candidate is selected.
- Higher-priority repair, regular, operator-approval, or blocked packets still win.
