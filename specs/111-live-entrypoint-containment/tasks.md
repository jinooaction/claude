# Tasks: Live Entrypoint Containment

**Input**: Design documents from `specs/111-live-entrypoint-containment/`  
**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`  
**Risk grade**: 4 — money-path capability contraction; no live execution authorized  
**Tests**: Required. No KIS, Anthropic, SSH, or paid external call is allowed in tests.

## Phase 1: Setup and Ground Truth

- [x] T001 Create `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md` with the full program, evidence map, implementation order, and authorization boundary
- [x] T002 [P] Create the complete SDD package under `specs/111-live-entrypoint-containment/`
- [x] T003 Update `.specify/feature.json` to point to `specs/111-live-entrypoint-containment`
- [x] T004 Confirm branch, HEAD, clean worktree, `origin/main` relationship, and open PR state using repository sync rules
- [x] T005 Read `AGENTS.md`, the handoff, all spec 111 artifacts, and current implementation files before editing
- [x] T006 Run `rg` across workflow, scripts, source, tests, and docs for `AUTO_OK`, `auto_ok`, `start_live_worker`, `prompt_operator_ok`, `verify_rules`, and `RULE_DESIGN_DEPLOYED`
- [x] T007 Record all current production call sites and existing tests in the PR body `## 탐색 근거`
- [x] T008 Capture hashes of live sentinels, constitution, kernel manifest, caps, and whitelist for post-change comparison

---

## Phase 2: Baseline and Failing Contract Tests

**Purpose**: Prove the current unsafe chain and lock the desired boundary before implementation.

- [x] T009 [P] Add workflow source tests proving `operator-design.yml` has no schedule, no live-default input, no automatic confirmation, and no raw intent interpolation
- [x] T010 [P] Add shell helper tests proving no `AUTO_OK` branch, no automatic `OK`, no live subcommand, and safe multiline/special-character intent transport
- [x] T011 [P] Add verifier tests for unavailable, skipped, stubbed, exception, stale, malformed, and fingerprint-mismatched dynamic evidence
- [x] T012 [P] Add verifier all-pass test requiring actual static, backtest, and paper stage evidence for the same candidate fingerprint
- [x] T013 [P] Update design CLI integration tests so candidate generation succeeds but live worker startup and broker order calls remain zero
- [x] T014 [P] Add command registry tests requiring `design` to be A2 proposal-only with all live/order/capital/reassignment flags false
- [x] T015 Add a static production-call-path regression test that fails if `design` regains a direct live worker or broker order caller
- [x] T016 Run the focused tests against the baseline and confirm they fail for the expected reasons before implementation

---

## Phase 3: User Story 1 — Remove Workflow and Shell Live Authority (Priority: P1)

**Goal**: Manual design produces a candidate only; no scheduled or auto-confirmed live startup remains.

**Independent Test**: Workflow and shell tests pass while design output remains available.

- [x] T017 [US1] Remove the weekly `schedule` trigger from `.github/workflows/operator-design.yml`
- [x] T018 [US1] Remove `auto_ok` live semantics and any default-true behavior from the workflow
- [x] T019 [US1] Replace raw SSH command interpolation of intent with stdin, file, Base64, or JSON data transport
- [x] T020 [US1] Make remote and workflow exit-code propagation explicit and truthful
- [x] T021 [US1] Update workflow comments and Summary to state proposal-only behavior and zero live activation
- [x] T022 [US1] Remove `AUTO_OK` parsing and automatic `OK` injection from `scripts/operator_design.sh`
- [x] T023 [US1] Make the shell helper read intent as opaque data and preserve quotes, metacharacters, Unicode, and newlines
- [x] T024 [US1] Remove live worker status checks and live-start success wording from the shell helper

---

## Phase 4: User Story 2 — Make Verification Fail Closed (Priority: P1)

**Goal**: `ok=True` means all required validation actually ran and passed for the same candidate.

**Independent Test**: Every missing/stubbed/mismatched case is false; only all-pass actual evidence is true.

- [x] T025 [US2] Define `VerificationStageResult` and aggregate `DesignVerificationResult` or an equivalent typed structure
- [x] T026 [US2] Generate a deterministic candidate fingerprint before dynamic validation
- [x] T027 [US2] Refactor static validation into an explicit stage result
- [x] T028 [US2] Inject or call an actual backtest validator and bind its evidence to the candidate fingerprint
- [x] T029 [US2] Inject or call an actual paper/simulation validator and bind its evidence to the candidate fingerprint
- [x] T030 [US2] Return `WAIT_DYNAMIC_VALIDATION` with `ok=False` when either dynamic integration cannot be completed safely in this PR
- [x] T031 [US2] Return `BLOCKED` with structured reasons on exceptions, malformed evidence, stale evidence, or fingerprint mismatch
- [x] T032 [US2] Remove any logic where module import availability or skipped flags can contribute to aggregate success
- [x] T033 [US2] Ensure output contains per-stage status, reason, fingerprint, and evidence reference

---

## Phase 5: User Story 3 — Remove Direct CLI Live Startup (Priority: P1)

**Goal**: `auto-invest design` cannot launch a live process or submit an order.

**Independent Test**: CLI integration tests generate a proposal and show zero live/order calls.

- [x] T034 [US3] Inspect every production caller of `start_live_worker`
- [x] T035 [US3] Remove `start_live_worker` invocation from the `design` CLI path
- [x] T036 [US3] Change design completion output to candidate path, proposal authority, verification status, and next validation action
- [x] T037 [US3] Stop emitting new `RULE_DESIGN_DEPLOYED` events from design completion while preserving historical event parsing
- [x] T038 [US3] Delete `start_live_worker` if unused, or replace it with a compatibility function that raises a clear live-boundary error
- [x] T039 [US3] Update or remove old tests that require design-driven live startup; preserve tests for candidate file creation
- [x] T040 [US3] Prove no production design call graph reaches `auto-invest run`, `rebalance-once --mode live`, or broker order submission

---

## Phase 6: User Story 4 — Preserve Proposal Capability and Align Policy (Priority: P2)

**Goal**: Design remains useful as a candidate producer and executable policy tells the truth.

**Independent Test**: Candidate output is usable and command policy is proposal-only.

- [x] T041 [US4] Preserve generated candidate TOML output without applying it to live config
- [x] T042 [US4] Add or preserve structured JSON/Markdown proposal and verification output
- [x] T043 [US4] Mark all design output `PROPOSAL_ONLY` until the separate promotion path acts
- [x] T044 [US4] Update `src/auto_invest/safety/command_registry.py` so `design` is `AutonomyLevel.PROPOSAL`
- [x] T045 [US4] Set `can_place_order`, `can_change_live_config`, `can_scale_capital`, and `can_reassign_strategy` to false
- [x] T046 [US4] Keep `uses_broker=true` only if account context is read; document it as read-only
- [x] T047 [US4] Point documentation to the supported candidate → backtest → paper/forward → canary → live path

---

## Phase 7: Focused Validation and Adversarial Review

- [x] T048 Run focused verifier, deploy-helper, CLI, workflow/shell, and command-registry tests
- [x] T049 Run the special-character intent fixture and prove no command-shaped text executes
- [x] T050 Run static search for `AUTO_OK`, `auto_ok`, `start_live_worker`, automatic `OK`, raw SSH intent interpolation, and `schedule`
- [x] T051 Explain every remaining search hit; production unsafe hits must be zero
- [x] T052 Compare protected-file hashes and prove live sentinels, caps, whitelist, constitution, and kernel are unchanged
- [x] T053 Review the diff as implementer, reviewer, safety owner, and handoff owner
- [x] T054 Verify rollback documentation restores proposal generation only and never restores direct live authority

---

## Phase 8: Full Repository Gates

- [x] T055 Run `uv run pytest`
- [x] T056 Run `uv run ruff check src tests`
- [x] T057 Run `git diff --check`
- [x] T058 Run `uv run python scripts/check_handoff_facts.py`
- [x] T059 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T060 Prepare the PR body and run `python3 scripts/check_pr_quality_gate.py /tmp/pr-body-111.md`
- [x] T061 Confirm the PR is mergeable, not draft when complete, and has no hold marker
- [x] T062 Confirm no actual KIS, Anthropic, SSH, live workflow dispatch, or server command was executed during validation

---

## Phase 9: Merge and Handoff

- [x] T063 Update `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md` with actual code paths removed, test evidence, and unresolved risks
- [x] T064 Mark this task file complete only after all required gates pass
- [x] T065 Merge using repository `merge` policy when automatic merge conditions are satisfied
- [x] T066 Verify the `main` merge commit and relevant post-merge workflows
- [x] T067 Refresh root `HANDOFF.md` in the repository-standard follow-up PR
- [x] T068 Name `112-order-submission-uncertainty-recovery` as the next execution-safety work item unless new evidence changes priority

## Dependencies & Execution Order

1. Phase 1 establishes truth and protected-state snapshots.
2. Phase 2 creates failing boundary tests.
3. Phase 3 removes workflow and shell authority.
4. Phase 4 fixes verification truthfulness.
5. Phase 5 removes direct CLI live startup.
6. Phase 6 preserves proposal value and aligns policy metadata.
7. Phases 7–9 validate, merge, observe, and hand off.

Phase 3 and Phase 4 can be implemented in separate commits but must land together because either one alone leaves an incomplete safety story.

## Parallel Opportunities

- T009–T014 can be drafted independently after call-site inspection.
- Workflow/shell changes and verifier model changes can proceed in parallel if they do not edit the same test fixtures.
- Command registry changes can proceed after the final intended CLI behavior is fixed.

## Completion Rule

This feature is not complete merely because the scheduled workflow is removed. Completion requires all three boundaries:

```text
no automatic trigger
AND no direct live caller
AND no false verification success
```

## Explicitly Forbidden During This Task

- Setting any live sentinel to true
- Triggering go-live or live-rebalance workflows
- Running a real live worker
- Placing or cancelling a real order
- Changing capital, whitelist, caps, or loss budget
- Restoring direct live startup as a compatibility shortcut
