# Tasks: Live Canary Sidecar Gate

**Input**: Design documents from `/specs/123-live-canary-sidecar-gate/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a risk grade 3 live-money workflow boundary change.

**Organization**: Tasks are grouped by independently testable user story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the next actionable blocker and create the traceable SDD surface.

- [x] T001 Verify latest `money-path`, `capital-path-readiness`, `autonomous-work-execution`, and `pipeline-liveness` sidecars.
- [x] T002 Confirm GitHub has no open PR that already owns the next work.
- [x] T003 Diagnose `rebalance-live-canary` as late because scheduled runs are waiting for production approval while the sentinel is unarmed.
- [x] T004 Create SDD artifacts under `specs/123-live-canary-sidecar-gate/` and update `.specify/feature.json`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add workflow boundary tests before relying on the workflow split.

- [x] T005 [P] Add static tests for preview/status and real-order job boundaries in `tests/unit/test_live_canary_workflow.py`.
- [x] T006 [P] Update live NAV capital-basis test in `tests/unit/test_workflow_nav_capital_basis.py` so both allowed live measurement calls must carry `--capital ${CAP}`.

---

## Phase 3: User Story 1 - Keep Unarmed Live Canary Evidence Fresh (Priority: P1)

**Goal**: The live canary workflow can publish a fresh preview/status sidecar while unarmed and without production approval.

**Independent Test**: `tests/unit/test_live_canary_workflow.py` proves the preview job has sidecar publication, has no production environment, and contains no live order command.

- [x] T007 [US1] Split `.github/workflows/rebalance-live-canary.yml` so `live_portfolio_canary_preview` owns sentinel read, dry-run preview, unarmed measurement, and preview sidecar publication.
- [x] T008 [US1] Make the preview sidecar clearly report `preview-job-skipped` and zero real orders.

---

## Phase 4: User Story 2 - Preserve the Real-Order Approval Gate (Priority: P1)

**Goal**: The only live-order command remains behind production approval and existing live gates.

**Independent Test**: `tests/unit/test_live_canary_workflow.py` proves the real-order job needs the preview job, requires armed/not-blocked/non-push conditions, keeps production approval, validates capital, and owns the only `--mode live --confirm-live` command.

- [x] T009 [US2] Add `live_portfolio_canary_real_orders` in `.github/workflows/rebalance-live-canary.yml` with production approval and preview-output gate conditions.
- [x] T010 [US2] Move real-order result publication into the production-gated job.
- [x] T011 [US2] Skip preview live-track measurement when `armed=true` so approval-pending runs do not create pre-order measurements.

---

## Phase 5: User Story 3 - Make the Sidecar Meaning Unambiguous (Priority: P2)

**Goal**: Fresh sidecar status cannot be mistaken for executed trades.

**Independent Test**: Static workflow tests and sidecar text prove preview-only and production execution paths use different live-step wording.

- [x] T012 [US3] Add preview sidecar wording that names the production-gated real-order job.
- [x] T013 [US3] Add production sidecar wording that reports actual real-order job outcome.
- [x] T014 [US3] Detect post-merge `refused command` logs from raw SSH preview/status commands.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate, merge, refresh sidecars, and update handoff truth.

- [x] T015 Add fixed observe gateway/helper commands for live-canary backfill, dry-run preview, and measure.
- [x] T016 Route the preview/status job through fixed observe commands with short gateway-refresh retry.
- [x] T017 Run focused workflow, SSH-boundary, shell syntax, YAML, and liveness tests from `quickstart.md`.
- [x] T018 Run full validation: `uv run pytest`, `uv run ruff check src tests`, `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`, and `git diff --check`.
- [ ] T019 Update PR body with risk grade 3, problem definition, safety boundary, validation, SDD, and handoff facts.
- [ ] T020 Merge after required checks pass and PR is mergeable.
- [ ] T021 Run main-branch `rebalance-live-canary.yml` while `armed=false` and verify the sidecar refreshes without real orders or `refused command`.
- [ ] T022 Refresh `pipeline-liveness` and verify `rebalance-live-canary` is no longer late.
- [ ] T023 Refresh `HANDOFF.md` if the operating truth changes.

## Dependencies & Execution Order

- T001-T004 establish current truth and SDD.
- T005-T006 guard the workflow before relying on T007-T013.
- T007-T016 can be reviewed as one workflow/gateway-boundary change.
- T017-T023 must run in order because merge and sidecar refresh depend on successful local validation.

## Implementation Strategy

1. Restore live-canary sidecar freshness without touching real-order authority.
2. Prove the preview/status path has no real-order command.
3. Prove the real-order path keeps production approval and existing gates.
4. Merge only after full validation and PR quality gate.
5. Verify the actual main-branch sidecar and pipeline liveness, because local tests cannot prove GitHub Actions queue behavior.
