# Tasks: Small-Account Execution Parity

**Tests**: Required because this changes the K2 whitelist and first-capital money path.

## Phase 1: Frozen Contract

- [x] T001 Record root cause, fixed proxy pairs, thresholds, non-goals, and rollback in `specs/170-small-account-execution-parity/spec.md`
- [x] T002 Record official product/API basis before implementation in `specs/170-small-account-execution-parity/research.md`

## Phase 2: Test-First Contracts

- [x] T003 [US1] Add delayed-latest-session and interior-hole tests in `tests/integration/test_canary_portfolio_cli.py`
- [x] T004 [US2] Add parity metric, evidence mutation, mapping, and stale-data tests in `tests/unit/test_execution_proxy_parity.py`
- [x] T005 [US2] Add KIS read-only proxy quote/history smoke coverage in `tests/integration/test_live_broker.py`
- [x] T006 [US3] Add every-entry-path parity/fundability tests in `tests/unit/test_capital_ladder.py` and `tests/unit/test_live_entry_revalidation.py`

## Phase 3: Implementation

- [x] T007 [US1] Implement latest complete session resolution and hole diagnostics in `src/auto_invest/canary/portfolio_harness.py` and `src/auto_invest/cli.py`
- [x] T008 [US2] Implement frozen proxy parity evidence and validation in `src/auto_invest/portfolio/execution_proxy_parity.py`
- [x] T009 [US2] Add parity CLI and guarded instance observer routes in `src/auto_invest/cli.py`, `deploy/observe-on-instance.sh`, and `deploy/repair-ssh-boundary.sh`
- [x] T010 [US2] Replace the live execution mapping and synchronize the minimum notional in `deploy/canary-live-portfolio.toml` and `deploy/global-trend-fixed-portfolio.toml`
- [x] T011 [US3] Require shared execution readiness in `src/auto_invest/portfolio/capital_ladder.py`, `src/auto_invest/portfolio/live_entry_revalidation.py`, and `scripts/live_entry_revalidation_probe.py`
- [x] T012 [US3] Wire fresh parity evidence into `.github/workflows/forward-edge-autoarm.yml` and `.github/workflows/rebalance-live-canary.yml`

## Phase 4: Verification and Release

- [ ] T013 Run focused tests and a branch KIS read-only smoke; record actual parity and affordability evidence
- [ ] T014 Run full pytest, Ruff, YAML, strict harness, HANDOFF facts, and PR quality checks
- [ ] T015 Create and merge the grade-4 PR, verify guarded deploy, rerun no-order parity/canary/fundability sidecars, and confirm capital/orders remain zero
- [ ] T016 Refresh `HANDOFF.md` with the current strategy verdict, execution readiness, and remaining first-capital blockers through the normal merge path

## Dependencies

- T001-T002 block implementation.
- T003-T006 block T007-T012.
- T007-T012 block production verification.
- T013-T014 block merge; T015 blocks handoff.
