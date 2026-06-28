# Tasks: Candidate Implementation Factory

## Phase 1 - SDD and Fixtures

- [x] T001 Create SDD artifacts under `specs/070-candidate-implementation-factory/`.
- [x] T002 Add candidate factory fixtures under `tests/fixtures/candidate_factory/fresh/`.

## Phase 2 - Core Factory

- [x] T003 Implement package models and deterministic candidate classification.
- [x] T004 Implement result evidence parsing and pass/fail normalization.
- [x] T005 Implement enriched candidate backlog generation.
- [x] T006 Implement markdown/JSON artifact rendering.
- [x] T007 Add unit tests for all current candidate kinds and false-pass prevention.

## Phase 3 - CLI and Probe

- [x] T008 Add `candidate-factory` CLI command.
- [x] T009 Add safety command registry entry and tests.
- [x] T010 Add `scripts/candidate_factory_probe.py`.
- [x] T011 Add integration tests for probe outputs.

## Phase 4 - Workflows and Liveness

- [x] T012 Add `.github/workflows/candidate-implementation-factory.yml`.
- [x] T013 Update `autonomous-promotion-loop.yml` to prefer enriched backlog.
- [x] T014 Add workflow safety/order regression tests.
- [x] T015 Add factory sidecar to `pipeline_liveness.default_specs()`.
- [x] T016 Update liveness tests.

## Phase 5 - Verification and Release

- [x] T017 Run focused pytest and ruff for new surfaces.
- [x] T018 Run full `uv run pytest` and `uv run ruff check src tests`.
- [ ] T019 Push branch and open PR with quality-gate body.
- [ ] T020 Merge when gates pass and verify deployment/sidecar implications.
- [ ] T021 Refresh `HANDOFF.md` and verify handoff facts.
