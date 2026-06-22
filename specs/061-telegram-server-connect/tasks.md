# Tasks: Telegram Server Connection Workflow

**Input**: `spec.md`, `plan.md`

## Phase 1: Tests

- [X] T001 Add workflow static tests in `tests/unit/test_configure_telegram_alerts_workflow.py`.

## Phase 2: Implementation

- [X] T002 Add `.github/workflows/configure-telegram-alerts.yml`.
- [X] T003 Update `deploy/README.md` with the easier workflow path.
- [X] T004 Update `.specify/feature.json` to point at this feature.

## Phase 3: Validation

- [X] T005 Run targeted workflow tests.
- [X] T006 Run `uv run pytest -q`.
- [X] T007 Run `uv run ruff check src tests`.
- [X] T008 Run PR quality gate, handoff fact check, and strict harness.
- [X] T009 Prepare PR body and post-merge workflow dispatch command.
