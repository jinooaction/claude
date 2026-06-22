# Implementation Plan: Micro GTAA Live Canary

**Branch**: `Codex/micro-gtaa-live-canary` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/058-micro-gtaa-canary/spec.md`

## Summary

Add a separate operator-approved micro live-canary path that can start real-money exposure faster than the evidence-gated capital ladder while keeping the blast radius small. The implementation adds a low-unit GTAA portfolio (`SPYM`, `IEF`, `GLDM`), a default-unarmed sentinel, a guarded workflow that previews on push and only places real orders when armed outside push events, and regression tests for the new safety invariants.

## Technical Context

**Language/Version**: Python 3.11 plus GitHub Actions YAML  
**Primary Dependencies**: Existing project code only; no new Python or workflow dependency  
**Storage**: Repository TOML/YAML/sentinel files, existing SQLite audit log on the live instance, sidecar branch for latest run report  
**Testing**: `pytest`, `ruff`, existing PR quality gate  
**Target Platform**: GitHub Actions runner invoking the existing Vultr `/opt/auto-invest` instance over SSH  
**Project Type**: Python CLI + guarded trading workflow + operating configuration  
**Performance Goals**: Workflow should finish within 15 minutes and preview planned orders before any live order path.  
**Constraints**: Default state must be real-order 0; no margin, no options, no shorting, no leverage, no market orders, no secrets in repo/logs, no market-hours deploy changes.  
**Scale/Scope**: One bounded micro canary with capital ≤ 1,000 USD, three ETF legs, and sidecar reporting.

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Position Sizing & Exposure Limits | Existing K1 cap code remains unchanged. New config keeps per-trade, per-symbol, and global caps and caps manual capital at 1,000 USD. |
| II. Deny-by-Default | Safety boundary touched by adding a new live micro whitelist (`SPYM`, `IEF`, `GLDM`). The whitelist is explicit, narrow, ETF-only, regular-session limit-only, and documented as a micro canary. |
| III. Claude Is Invoked Only at Defined Judgment Points | No new LLM call or judgment point. |
| IV. Append-Only Audit Log + Daily Reconciliation | Orders still go through existing `rebalance-once` and `OrderRouter`; no audit mutation or alternate order path. |
| V. Secret Isolation | No secrets added. Existing GitHub secrets and instance `.env` are referenced only at runtime. |
| VI. Staged Rollout | This is a bounded live canary, not full live. The existing capital ladder and larger deployment path remain unchanged. |
| VII. External API Robustness | Uses existing KIS quote/order/backfill path and existing failure behavior; quote/backfill failures do not auto-substitute symbols. |
| VIII.A Change Discipline | Adds workflow/config through PR. Real orders are schedule/manual-dispatch gated, not push-on-merge. No live deploy behavior is changed. |
| IX. Self-Modification Boundary | No constitution or kernel manifest touch. Safety-relevant live universe expansion is called out in spec/PR. |
| X. Measurement-Driven Autonomous Growth | Faster exposure is separated from the evidence-gated ladder. The micro canary is measured and bounded, while larger capital still requires existing evidence gates. |

## Project Structure

### Documentation

```text
specs/058-micro-gtaa-canary/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── micro-gtaa-canary.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source

```text
automation/
└── rebalance-micro-gtaa.request

deploy/
└── micro-gtaa-live-portfolio.toml

.github/workflows/
└── rebalance-micro-gtaa-canary.yml

tests/unit/
├── test_canary_portfolio_config.py
└── test_micro_gtaa_canary.py
```

**Structure Decision**: Use a separate micro-GTAA path instead of modifying `rebalance-live-canary.yml` or `automation/rebalance-live.request`. This avoids weakening the existing evidence-gated ladder and makes rollback a small sentinel/workflow change.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Separate live workflow | Existing live canary is tied to the validated `SPY`/`IEF`/`GLD` ladder path. | Editing the existing path would mix "fast micro experiment" with the evidence-gated capital ladder and make rollback less clear. |
| New live ETF whitelist | Low-unit equity and gold legs are needed for 1,000 USD integer-share diversification. | Keeping `SPY`/`GLD` makes the micro canary mostly one-legged or underinvested at 500-1,000 USD. |

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/micro-gtaa-canary.md](./contracts/micro-gtaa-canary.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

The design remains a grade 4 money-path change because it introduces an operator-approved real-order path and expands the live micro whitelist. It does not change K1/K2 code, the constitution, kernel manifest, secrets, audit storage, or larger capital ladder rules. The maximum manual micro capital is fixed at 1,000 USD, real orders require `armed: true`, and push-triggered runs remain preview-only.
