# Tasks: Micro GTAA Live Canary

**Input**: Design documents from `specs/058-micro-gtaa-canary/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included because this feature changes a real-money operating path.

## Phase 1: Setup

- [X] T001 Create `deploy/micro-gtaa-live-portfolio.toml` with micro ETF universe, caps, whitelist, equal-weight portfolio, and trend ensemble.
- [X] T002 Create `automation/rebalance-micro-gtaa.request` defaulted to `armed: false`.
- [X] T003 Create `.github/workflows/rebalance-micro-gtaa-canary.yml` guarded workflow skeleton.

---

## Phase 2: Foundational

- [X] T004 Add micro portfolio invariants to `tests/unit/test_canary_portfolio_config.py`.
- [X] T005 Add sentinel and workflow safety tests in `tests/unit/test_micro_gtaa_canary.py`.

---

## Phase 3: User Story 1 - Same-Day Micro Live Exposure (Priority: P1)

**Goal**: A bounded micro live canary can preview and, when armed, submit real ETF orders without weakening the existing ladder.

**Independent Test**: Run micro canary unit tests and inspect workflow gating.

- [X] T006 [US1] Implement workflow guard parsing and capital checks in `.github/workflows/rebalance-micro-gtaa-canary.yml`.
- [X] T007 [US1] Implement dry-run preview step before the live step in `.github/workflows/rebalance-micro-gtaa-canary.yml`.
- [X] T008 [US1] Implement live step gated by `armed == true` and non-push trigger in `.github/workflows/rebalance-micro-gtaa-canary.yml`.

---

## Phase 4: User Story 2 - Downside-Bounded Growth Attempt (Priority: P2)

**Goal**: The micro canary preserves explicit downside limits and stop guidance.

**Independent Test**: Sentinel tests reject excessive capital or stop thresholds.

- [X] T009 [US2] Add warning and hard-stop fields to `automation/rebalance-micro-gtaa.request`.
- [X] T010 [US2] Add sidecar output describing stop policy and run outcome in `.github/workflows/rebalance-micro-gtaa-canary.yml`.

---

## Phase 5: User Story 3 - Reproducible Operator Forensics (Priority: P3)

**Goal**: Next sessions can reconstruct why the micro canary exists and how to stop it.

**Independent Test**: Read spec, quickstart, sentinel, workflow, and sidecar contract.

- [X] T011 [US3] Ensure `specs/058-micro-gtaa-canary/quickstart.md` documents preview, arming, and disarming.
- [X] T012 [US3] Ensure `specs/058-micro-gtaa-canary/contracts/micro-gtaa-canary.md` matches implemented paths.

---

## Phase N: Polish & Validation

- [X] T013 Run `uv run pytest tests/unit/test_micro_gtaa_canary.py tests/unit/test_canary_portfolio_config.py`.
- [X] T014 Run `python3 scripts/check_pr_quality_gate.py --template .github/pull_request_template.md`.
- [X] T015 Run `uv run pytest`.
- [X] T016 Run `uv run ruff check src tests`.
- [X] T017 Update PR body and handoff if merge completes.

## Dependencies & Execution Order

- Setup tasks T001-T003 first.
- Foundational tests T004-T005 before user-story validation.
- User Story 1 is the MVP and can be validated independently.
- User Story 2 and 3 depend on the core files created in setup.
- Polish validation runs after all implementation tasks.

## Implementation Strategy

Deliver the separate micro canary path first, keep committed state unarmed, prove workflow gates with tests, then run full test and lint before PR.
