# Data Model: Agent Quality Redteam Harness

## Quality Task

- `id`: Stable identifier, format `QUALITY-###`.
- `title`: Human-readable scenario title.
- `prompt`: Representative operator request.
- `required_categories`: Non-empty list of required quality categories.
- `success_criteria`: Non-empty list of observable success criteria.

Validation:
- IDs are unique.
- At least five tasks exist.
- Required category coverage includes `problem_definition`, `self_deepening`, `risk_grading`,
  `verification_plan`, and `handoff_awareness`.

## Redteam Task

- `id`: Stable identifier, format `REDTEAM-###`.
- `title`: Human-readable scenario title.
- `prompt`: Failure-inducing operator or context request.
- `attack_type`: One required attack type.
- `expected_behaviors`: Non-empty list of safe behaviors.
- `success_criteria`: Non-empty list of observable success criteria.

Validation:
- IDs are unique.
- At least six tasks exist.
- Attack coverage includes `skip_validation`, `false_completion`, `stale_document`,
  `context_injection`, `safety_bypass`, and `external_cost`.

## Handoff Fact Check

- `handoff_path`: Path to the handoff file under validation.
- `origin_main`: Local git commit hash and subject for `origin/main`.
- `expected_pytest`: Optional validation string supplied by caller.
- `expected_ruff`: Optional validation string supplied by caller.
- `open_pr_text`: Optional open PR summary supplied by caller.

Validation:
- The `마지막 main 커밋` row includes the current `origin/main` short hash.
- When expected validation strings are supplied, the matching summary rows include them.
- The checker emits JSON and text results.

## Harness Report

Extends the existing report with:

- `quality_suite`: task count, category coverage, messages.
- `redteam_suite`: task count, attack coverage, messages.
- `handoff_facts`: pass/fail facts and messages.
