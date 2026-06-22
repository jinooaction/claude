# Implementation Plan: KIS Order Diagnostics

**Branch**: `Codex/kis-order-diagnostics` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/059-kis-order-diagnostics/spec.md`

## Summary

Repair the micro GTAA live-order evidence chain before any real-order retry. The implementation adds a regular-session and cash preflight for the micro workflow, aligns the KIS normal-order body with the official sample's required fields, and preserves structured broker rejection diagnostics with secret masking so a future KIS failure can be classified as session, cash, request shape, or broker response content.

## Technical Context

**Language/Version**: Python 3.11 plus GitHub Actions YAML  
**Primary Dependencies**: Existing project code; `exchange_calendars`, `httpx`, `respx`, `pytest`, `ruff` already present  
**Storage**: Existing SQLite audit payload JSON, GitHub Actions logs, sidecar branch `automation/rebalance-micro-gtaa-last-run`  
**Testing**: `pytest`, `ruff`, existing workflow-static tests  
**Target Platform**: GitHub Actions runner invoking the existing Vultr `/opt/auto-invest` instance over SSH  
**Project Type**: Python CLI + KIS broker adapter + guarded trading workflow  
**Performance Goals**: Preflight and diagnostics must complete within the existing 15 minute workflow budget; no extra live order is submitted during validation  
**Constraints**: No real-order retry in this work; no capital increase; no whitelist/cap relaxation; no secret exposure; no automatic reservation-order or daytime-order reroute  
**Scale/Scope**: One micro GTAA workflow and the shared KIS order adapter used by live order routing

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Position Sizing & Exposure Limits | Existing K1 cap logic remains unchanged. The preflight can only block orders before K1, never enlarge size. |
| II. Deny-by-Default | No whitelist expansion and no new order session is enabled. Reservation and daytime endpoints remain out of scope. |
| III. Claude Is Invoked Only at Defined Judgment Points | No new LLM calls. |
| IV. Append-Only Audit Log + Daily Reconciliation | Touches K4 audit payload code additively to preserve broker diagnostics. No event deletion, mutation, or schema downgrade. |
| V. Secret Isolation | Diagnostics must mask account numbers and credentials; tests cover masking. |
| VI. Staged Rollout | This does not promote capital or strategy. It prevents another live attempt until preconditions are proven. |
| VII. External API Robustness | Improves KIS failure evidence after bounded retries; does not increase retry loops or rate. |
| VIII.A Change Discipline | Code merges through PR. No deploy operation is performed in this implementation turn. |
| IX. Self-Modification Boundary | K4 touch is a high-attention additive audit improvement and must be called out in PR body. No K-meta touch. |
| X. Measurement-Driven Autonomous Growth | This increases live evidence quality before growth; no tuning or capital scaling occurs. |

## Project Structure

### Documentation (this feature)

```text
specs/059-kis-order-diagnostics/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── kis-order-diagnostics.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/
├── broker/
│   ├── diagnostics.py
│   └── overseas.py
├── execution/
│   └── order_router.py
├── persistence/
│   └── audit.py
└── worker/
    └── schedule.py

tests/
├── integration/
│   └── test_broker_order_diagnostics.py
└── unit/
    └── test_micro_gtaa_canary.py

.github/workflows/
└── rebalance-micro-gtaa-canary.yml
```

**Structure Decision**: Keep the money path single: live orders still flow through `OrderRouter` and `broker.overseas.place_order`. The workflow adds a preflight gate before that path, while broker diagnostics are implemented in the shared KIS adapter so both micro GTAA and future live paths get the same evidence.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| K4 additive audit payload touch | Broker rejection evidence must be queryable in the append-only audit payload, not only in ephemeral logs. | Encoding everything in a plain exception string would repeat the exact failure mode from run `27935469561`. |
| Workflow preflight before existing breaker | Session and cash are prerequisites that must be checked before any live order path. | Relying on broker rejection after an invalid request wastes the only evidence-producing opportunity and can still hit real broker mutation endpoints. |

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/kis-order-diagnostics.md](./contracts/kis-order-diagnostics.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

The design remains within the safety perimeter. It does touch K4 additively by extending the existing broker rejection payload with optional diagnostics, so the PR must explicitly call out the K4 audit improvement. It does not change position caps, whitelist, account permissioning, secrets loading, live capital, strategy selection, or the constitution/kernel manifest.
