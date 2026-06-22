# Tasks: Telegram Order Alerts

**Input**: Design documents from `specs/060-telegram-order-alerts/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included because this feature adds external notification, runtime secrets, and money-path observability.

## Phase 1: Setup

- [X] T001 [P] Create unit tests for Telegram formatting, masking, send retry, and cursor behavior in `tests/unit/test_telegram_alerts.py`.
- [X] T002 [P] Create CLI integration tests for dry-run, missing secrets, and once-mode cursor advancement in `tests/integration/test_telegram_alerts_cli.py`.
- [X] T003 [P] Create workflow static tests for micro GTAA Telegram notification best-effort behavior in `tests/unit/test_micro_gtaa_telegram_alerts.py`.

---

## Phase 2: Foundational

- [X] T004 Implement Telegram config, sanitization, truncation, and bounded send helper in `src/auto_invest/notifications/telegram.py`.
- [X] T005 Implement audit cursor, event selection, row formatting, and polling batch logic in `src/auto_invest/notifications/audit_tail.py`.
- [X] T006 Add package marker in `src/auto_invest/notifications/__init__.py`.

---

## Phase 3: User Story 1 - Receive Micro GTAA Run Alerts on Mobile (Priority: P1)

**Goal**: micro GTAA workflow sends a best-effort Telegram summary after each run.

**Independent Test**: `uv run pytest tests/unit/test_micro_gtaa_telegram_alerts.py`

- [X] T007 [US1] Add best-effort Telegram notification step to `.github/workflows/rebalance-micro-gtaa-canary.yml`.
- [X] T008 [US1] Ensure missing Telegram secrets and send failures do not fail `.github/workflows/rebalance-micro-gtaa-canary.yml`.

---

## Phase 4: User Story 2 - Receive General Live Order Event Alerts (Priority: P2)

**Goal**: server-side audit_log tailer emits mobile alerts for live order and fill events.

**Independent Test**: `uv run pytest tests/unit/test_telegram_alerts.py tests/integration/test_telegram_alerts_cli.py`

- [X] T009 [US2] Add `auto-invest telegram-alerts` CLI command in `src/auto_invest/cli.py`.
- [X] T010 [US2] Add optional `deploy/auto-invest-telegram-alerts.service` systemd unit.
- [X] T011 [US2] Update `deploy/sync-units.sh` to install but not auto-enable the Telegram alerts service.

---

## Phase 5: User Story 3 - Enable Alerts Without Widening the Trading Safety Perimeter (Priority: P3)

**Goal**: operator can configure Telegram safely while preserving order-path independence.

**Independent Test**: docs plus automated checks prove secrets are optional and no order code path is modified.

- [X] T012 [US3] Document Telegram bot setup, GitHub secrets, server `.env`, test message, enable/disable commands in `deploy/README.md`.
- [X] T013 [US3] Verify no order router, broker submission, caps, whitelist, or circuit breaker behavior changes are required.

---

## Phase N: Polish & Validation

- [X] T014 Run targeted Telegram tests.
- [X] T015 Run `uv run pytest -q`.
- [X] T016 Run `uv run ruff check src tests`.
- [X] T017 Run `uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md`.
- [X] T018 Prepare PR body with risk grade 3, secret/external API safety notes, and validation evidence.

## Dependencies & Execution Order

- T001-T003 define tests first.
- T004-T006 are shared notification foundation.
- T007-T008 can proceed after T004.
- T009 depends on T004-T006.
- T010-T012 depend on T009.
- Validation runs after all user stories are complete.

## Parallel Opportunities

- T001-T003 can be written independently.
- T007-T008 can proceed in parallel with T010-T012 after the core notification modules exist.

## Implementation Strategy

Deliver the safe observer first: message formatting and dry-run must work without secrets. Then add GitHub Actions micro alerts, then the optional server tailer service. Do not enable the service automatically and do not modify order-routing behavior.
