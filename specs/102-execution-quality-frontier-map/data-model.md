# Data Model: Execution Quality Frontier Map

## ExecutionQualityFrontierTemplate

- `frontier_key`: Stable internal key for the execution-quality area.
- `label_ko`: Korean label shown in Markdown.
- `recommended_candidate_id`: Stable candidate id emitted as a work packet when unreleased.
- `title_ko`: Korean title for the generated work packet.
- `priority_score`: Ordering score inside the execution-quality frontier.
- `reason_ko`: Why this frontier exists.
- `next_action_ko`: Concrete next action for the later SDD task.

## ExecutionQualityFrontierMapEntry

- `frontier_key`: Copied from the template.
- `label_ko`: Copied from the template.
- `coverage_status`: `released` when released-work contains `recommended_candidate_id`; otherwise `open`.
- `priority_score`: Copied from the template.
- `recommended_candidate_id`: Copied from the template.
- `title_ko`: Copied from the template.
- `reason_ko`: Copied from the template.
- `next_action_ko`: Copied from the template.
- `required_inputs`: Read-only sidecar refs needed by the generated candidate.

## Generated Execution Quality WorkPacket

- `candidate_id`: Highest-priority unreleased execution-quality entry.
- `domain_key`: `execution_quality`.
- `work_type`: Existing execution-quality work type.
- `risk_grade`: `2`.
- `safety_impact`: Empty.
- `required_inputs`: Execution-quality, KIS smoke, micro GTAA, money-path, pipeline-liveness, released-work, and capital-path readiness refs.
- `safety_boundary`: Existing autonomous-work safety invariants.

## Completed Candidate Marker

The released-work-readable completion field is:

```text
completed_candidate_id: candidate-execution-quality-frontier-map
```

