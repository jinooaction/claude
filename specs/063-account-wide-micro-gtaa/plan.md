# Implementation Plan: Account-Wide Micro GTAA Autonomous Rebalance

**Branch**: `Codex/account-wide-micro-gtaa` | **Date**: 2026-06-23 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/063-account-wide-micro-gtaa/spec.md`

## Summary

Extend the existing micro GTAA live canary so it plans from the actual KIS account snapshot, not only the local filled-order ledger. Existing holdings can be classified as strategy targets, liquidation-only holdings, or unmanaged holdings. Liquidation-only holdings may be sold to free strategy capital, but they must never become buy candidates. When current purchasable cash cannot cover planned buys plus the 1% buffer, the live loop runs a sell-only cycle and waits for KIS-confirmed purchasable cash before buying in a later cycle.

## Technical Context

**Language/Version**: Python 3.11 plus GitHub Actions YAML  
**Primary Dependencies**: Existing project code only; no new Python or workflow dependency  
**Storage**: Repository TOML/YAML config, existing SQLite audit log on the live instance, sidecar branch for latest run report  
**Testing**: `pytest`, `ruff`, PR quality gate script  
**Target Platform**: GitHub Actions runner invoking the existing Vultr `/opt/auto-invest` instance over SSH  
**Project Type**: Python CLI + guarded trading workflow + operating configuration  
**Performance Goals**: Account-wide preview and live gate should finish within the existing 15 minute workflow budget.  
**Constraints**: Grade 4 money path. No margin, no shorting, no leverage, no market orders, no secrets in repo/logs, no push-triggered real orders, no safety gate weakening.  
**Scale/Scope**: One micro GTAA live canary account with `capital_usd <= 1000`, target universe `SPYM`, `IEF`, `GLDM`, and initial liquidation-only legacy holdings discovered from current broker evidence.

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Position Sizing & Exposure Limits | Existing K1 cap code remains the enforcement path. Account-wide planning still routes through `OrderRouter` and configured caps. |
| II. Deny-by-Default | Target buys remain limited to `SPYM`, `IEF`, `GLDM`. Legacy holdings are explicit liquidation-only inputs and must be rejected if they appear as buys. |
| III. Claude Is Invoked Only at Defined Judgment Points | No runtime LLM call or discretionary per-tick judgment is added. |
| IV. Append-Only Audit Log + Daily Reconciliation | Orders still use the existing router and audit path. Broker-vs-ledger differences are reported, not silently rewritten. |
| V. Secret Isolation | No new secrets. KIS read-only calls use existing runtime environment variables and must not print account credentials. |
| VI. Staged Rollout | This modifies only the already armed micro live canary path and keeps the capital cap at 1,000 USD. It is not a full-live promotion. |
| VII. External API Robustness | Position, cash, and quote failures fail closed with zero live orders. Same-run buys require KIS-confirmed purchasable cash. |
| VIII.A Change Discipline | Changes land through PR. Push-triggered workflow events remain preview-only, and real orders remain schedule/manual-dispatch gated. |
| IX. Self-Modification Boundary | No constitution or kernel manifest edit is planned. The design avoids changing K1/K2 gate code unless implementation proves unavoidable. |
| X. Measurement-Driven Autonomous Growth | The loop records account-wide evidence and next expected stage so future capital changes remain evidence-based. |

## Project Structure

### Documentation

```text
specs/063-account-wide-micro-gtaa/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── account-wide-micro-gtaa.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source

```text
deploy/
└── micro-gtaa-live-portfolio.toml

src/auto_invest/
├── cli.py
├── execution/
│   └── rebalancer.py
└── portfolio/
    └── nav.py

.github/workflows/
└── rebalance-micro-gtaa-canary.yml

tests/
├── integration/
│   └── test_spec_032_live_rebalancer.py
└── unit/
    ├── test_canary_portfolio_config.py
    └── test_micro_gtaa_canary.py
```

**Structure Decision**: Extend the existing micro canary path rather than introducing a second live workflow. The workflow already owns the armed sentinel, preflight, breaker, sidecar, and Telegram reporting; the missing piece is account-wide planning and sell-first execution.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Account-wide broker snapshot in preview | The real account has legacy holdings and low cash; local ledger alone cannot decide sell vs buy. | Treating the run as cash-only repeats broker cash rejections and ignores deployable capital. |
| Liquidation-only legacy symbols | Existing holdings may need to be sold, but should not become future buy targets. | Adding them to the strategy universe would accidentally authorize buys and change the GTAA strategy. |
| Sell-only cycle before buy cycle | Same-run sale proceeds may not be purchasable immediately. | Assuming proceeds are usable in the same run risks repeated broker rejections. |

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/account-wide-micro-gtaa.md](./contracts/account-wide-micro-gtaa.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

The design remains a grade 4 money-path change because it can cause automated real sell orders for explicitly listed legacy holdings and later buys for the micro GTAA target universe. It does not change K1/K2 gate code, the constitution, kernel manifest, secrets, or the larger capital ladder. The safety boundary is preserved by keeping target buys restricted to `SPYM`, `IEF`, `GLDM`, making legacy holdings liquidation-only, failing closed on missing broker evidence, and requiring KIS-confirmed purchasable cash before any buy cycle.
