# Tasks: Autonomous Promotion Actions

## Phase 1 - Spec and Fixtures

- [x] T001 Create SDD artifacts under `specs/069-autonomous-promotion-actions/`.
- [x] T002 Add promotion action fixtures under `tests/fixtures/promotion_actions/fresh/`.
- [x] T003 Add initial tracked state files in `automation/`.

## Phase 2 - Core Action Engine

- [x] T004 Implement pure promotion action models and validation in `src/auto_invest/analytics/promotion_actions.py`.
- [x] T005 Implement idempotent forward registration derivation.
- [x] T006 Implement idempotent canary submission derivation.
- [x] T007 Implement markdown/JSON artifact rendering.
- [x] T008 Add unit tests in `tests/unit/test_promotion_actions.py`.

## Phase 3 - CLI and Probe

- [x] T009 Add `promotion-actions` CLI command in `src/auto_invest/cli.py`.
- [x] T010 Add safety command registry entry and tests.
- [x] T011 Add `scripts/promotion_action_probe.py`.
- [x] T012 Add integration tests in `tests/integration/test_promotion_action_probe.py`.

## Phase 4 - Workflows and Liveness

- [x] T013 Add `.github/workflows/autonomous-promotion-actions.yml`.
- [x] T014 Add `.github/workflows/promotion-forward-tracks.yml`.
- [x] T015 Add `.github/workflows/promotion-canary-submissions.yml`.
- [x] T016 Add workflow safety regression tests.
- [x] T017 Add new sidecars to `pipeline_liveness.default_specs()`.
- [x] T018 Update liveness tests.

## Phase 5 - Verification and Release

- [x] T019 Run focused pytest and ruff for new surfaces.
- [x] T020 Run full `uv run pytest` and `uv run ruff check src tests`.
- [ ] T021 Push branch and open PR with quality-gate body.
- [ ] T022 Merge when gates pass and verify deployment/sidecar implications.
- [ ] T023 Refresh `HANDOFF.md` and verify handoff facts.
