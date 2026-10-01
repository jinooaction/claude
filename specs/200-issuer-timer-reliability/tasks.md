# Tasks: 발행사 관측의 서버 정기 실행

## Phase 1: Setup and evidence

- [x] T001 Record the 13 scheduled run intervals, source file growth, and exact baseline SHA in `specs/200-issuer-timer-reliability/results.md`.
- [x] T002 Define server command, immutable selection, status, and backup contracts in `specs/200-issuer-timer-reliability/contracts/`.

## Phase 2: Foundational contracts

- [x] T003 Extend legacy-compatible `selection` validation for explicit unchanged skips in `src/auto_invest/analytics/filing_observations.py` and `tests/unit/test_filing_observations.py`.
- [x] T004 Prove the fixed issuer collector cannot read broker secrets or submit orders in `tests/unit/test_issuer_filing_collector.py` and `tests/integration/test_filing_observations_cli.py`.

## Phase 3: User Story 1 — server schedule (P1)

- [x] T005 [US1] Add a fixed server-only collection command and read-only freshness status in `scripts/filing_observations.py`.
- [x] T006 [US1] Add a no-broker-environment systemd service and 15-minute timer in `deploy/auto-invest-issuer-observations.service` and `deploy/auto-invest-issuer-observations.timer`.
- [x] T007 [US1] Install only the new issuer units after source compatibility checks in `deploy/sync-units.sh`.
- [ ] T008 [US1] Verify missed schedule slots, restart behavior, and service isolation in `tests/unit/test_issuer_timer.py`.

## Phase 4: User Story 2 — bounded unchanged handling (P1)

- [x] T009 [US2] Add unchanged-list/24-hour-complete-primary decision to `src/auto_invest/market_data/issuer_filings.py`.
- [x] T010 [US2] Exercise unchanged, changed, prior failure, stale primary, and capacity refusal in `tests/unit/test_issuer_filing_collector.py` and `tests/integration/test_filing_observations_cli.py`.
- [x] T011 [US2] Calculate the 60-day normal-size upper bound from verified actual files in `specs/200-issuer-timer-reliability/results.md`.

## Phase 5: User Story 3 — separate durable copy (P2)

- [x] T012 [US3] Add a fixed read-only server export/status command to `deploy/observe-on-instance.sh` with no caller-provided path.
- [x] T013 [US3] Add append-only remote backup and digest comparison to `.github/workflows/server-issuer-observations-backup.yml`.
- [x] T014 [US3] Verify two incremental copies, corruption refusal, no overwrite, and recovery fingerprint in `tests/integration/test_server_issuer_backup.py`.

## Phase 6: Release evidence

- [ ] T015 Run targeted local checks, remote full `uv run pytest` and `uv run ruff check src tests`, strict harness, HANDOFF facts, and PR body gate; record results in `specs/200-issuer-timer-reliability/results.md`.
- [ ] T016 Merge a reviewable PR only after gates pass; verify source deployment, two real server collections, one off-server backup, and source fingerprints in `specs/200-issuer-timer-reliability/results.md`.
- [ ] T017 Observe 24 actual server hours and compare 96 scheduled slots with real receipts; only then mark SC-001 and the feature complete in `specs/200-issuer-timer-reliability/results.md`.

The release cannot mark T016 or T017 complete using simulated clock data. The
original GitHub schedule remains a separate source and is never backdated.
