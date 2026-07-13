# Implementation Plan: Atomic Fill Ledger

**Branch**: `Codex/113-atomic-fill-ledger` | **Date**: 2026-07-13 | **Spec**: `specs/113-atomic-fill-ledger/spec.md`
**Input**: Feature specification from `specs/113-atomic-fill-ledger/spec.md`

## Summary

Make live fill application atomic: a new broker fill must insert into `fills`, append its `FILL` audit event, update `current_positions`, and apply related order transitions in one SQLite transaction. Duplicate `kis_fill_id` rows must be skipped before audit/cache updates so a defensive duplicate plan cannot double-count holdings.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: `sqlite3`, `pydantic`, `pytest`, `respx`, `ruff`
**Storage**: SQLite via `src/auto_invest/persistence/db.py` with autocommit connections and explicit transactions where needed
**Testing**: `uv run pytest`, focused `tests/integration/test_fill_sync.py`, `tests/integration/test_worker_fill_sync.py`, `tests/unit/test_positions.py`
**Target Platform**: local worker and GitHub Actions; no live broker calls during tests
**Project Type**: single Python package with CLI, worker, broker adapter, persistence, analytics
**Performance Goals**: no new broker calls; one local write transaction per fill plan
**Constraints**: append-only audit log, idempotent fills, no secret leakage, no actual orders, no live sentinel/cap changes
**Scope**: `src/auto_invest/execution/fill_sync.py`, focused fill sync tests, SDD docs, handoff

## Constitution Check

Risk grade: **4** — money-path accounting safety behavior. The change is a contraction of live risk and does not authorize live execution.

- Principle I/II/III: position caps, whitelist, and judgment points are untouched.
- Principle IV: append-only audit semantics are preserved; no historical audit or fill row is updated/deleted.
- Principle VII: broker failure handling remains fail-closed for read failures and more consistent for local writes.
- Principle VIII.A/IX/X: no market-hours deploy, constitution, kernel manifest, live sentinels, capital, or strategy authority changes.
- Kernel note: this plan avoids modifying `.specify/memory/constitution.md`, `.specify/memory/kernel.toml`, and audit schema files. `audit.append` is consumed inside a transaction but not changed.

## Project Structure

### Documentation

```text
specs/113-atomic-fill-ledger/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── fill-application-transaction.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Targets

```text
src/auto_invest/execution/fill_sync.py
```

### Test Targets

```text
tests/integration/test_fill_sync.py
tests/integration/test_worker_fill_sync.py
```

## Phase Plan

1. Ground truth: confirm current fill application writes audit, fills, and position cache separately.
2. Baseline tests: add duplicate-plan and rollback-failure tests that fail on current behavior.
3. Atomic apply: wrap `apply_fill_plan` in `BEGIN IMMEDIATE`, count only inserted fill rows, skip audit/cache for duplicates.
4. Error behavior: rollback on any apply failure and leave caller-visible failure for tests.
5. Validation: focused tests, full tests, lint, diff check, handoff/harness, PR gate.
6. Merge and handoff refresh if automatic merge conditions are satisfied.

## Complexity Tracking

No schema migration is required. The existing `fills.kis_fill_id` unique key and append-only triggers are sufficient. The only new coordination is an explicit SQLite write transaction around existing writes.

## Rollback Plan

Rollback is a normal revert of the feature commit. Operationally, rollback would restore the previous risk where duplicate planned fills can move the position cache even when the fill row is ignored, so rollback should be used only if the transaction prevents normal fill sync from applying valid fills.

## Completion Criteria

- Duplicate planned fills do not create `FILL` audit rows and do not move positions.
- Injected apply failure leaves no partial `fills`, `audit_log`, `current_positions`, or order state changes.
- Existing fill sync behavior remains green.
- Full repository gates and handoff checks pass.
