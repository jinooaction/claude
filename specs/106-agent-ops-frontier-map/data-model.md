# Data Model: Agent Ops Frontier Map

## AgentOpsFrontierTemplate

- `frontier_key`: Stable machine key for the operating-system area.
- `label_ko`: Human-readable Korean label.
- `recommended_candidate_id`: Candidate id generated from this frontier row.
- `title_ko`: Work packet title.
- `priority_score`: Deterministic priority within the operating-system map.
- `reason_ko`: Why this operating area matters.
- `next_action_ko`: What the next Codex task should do.
- `required_inputs`: Evidence refs and repo-local controls the generated candidate must inspect.

## AgentOpsFrontierMapEntry

- `frontier_key`
- `label_ko`
- `coverage_status`: `open` when the candidate has not been released; `released` when released-work already closes it.
- `priority_score`
- `recommended_candidate_id`
- `title_ko`
- `reason_ko`
- `next_action_ko`
- `required_inputs`

## Generated Agent Ops Candidate

- A `WorkPacket` generated from the first unreleased `AgentOpsFrontierMapEntry`.
- `domain_key=agent_ops`
- `work_type=agent_operating_system`
- `risk_grade=2`
- `safety_impact=()`
- `status=EXECUTION_READY`
- `safety_boundary=SAFETY_INVARIANTS`

## Completed Candidate Marker

`completed_candidate_id: candidate-agent-ops-frontier-map`

This closes the implementation of the map itself. It must not close the map-derived next operating-system candidate.

## State Transitions

- Broker diagnostic liveness not released -> `candidate-broker-diagnostic-liveness-contract` remains selected.
- Broker diagnostic liveness released, agent ops frontier map not released -> `candidate-agent-ops-frontier-map` selected.
- Agent ops frontier map released -> first unreleased agent-ops map candidate selected.
- Handoff truth liveness released -> next unreleased agent-ops candidate selected.
- All agent-ops map candidates released -> no repeated agent-ops candidate; normal closed-state ordering applies.
