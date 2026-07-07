# Requirements Checklist: Execution Cost Basis Contract

**Purpose**: Verify that the specification is clear enough to implement and validate.
**Created**: 2026-07-07
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation-only detail is required for the user stories.
- [x] User value is stated for cost-basis readiness, observation wait, and next-candidate advancement.
- [x] Safety boundary is explicit and excludes broker calls, orders, capital, live settings, secrets, kernel, and paid external services.
- [x] Success criteria are measurable with local tests and probes.

## Requirement Completeness

- [x] Functional requirements cover required inputs, status rules, completion marker, and next candidate.
- [x] Missing cost-basis evidence and incomplete accepted/fill evidence are separate edge cases.
- [x] Money-path `PREVIEW_ONLY` is documented as context, not permission to collect real samples.
- [x] Full validation and handoff gates are included in success criteria.

## Readiness

- [x] Requirements are ready for planning.
- [x] Risk grade is documented as 2 in `plan.md`.
