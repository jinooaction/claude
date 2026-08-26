# Implementation Plan: Small-Account Execution Parity

**Branch**: `codex/170-small-account-execution-parity` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)

## Summary

Fix the hardened-canary window to end on the latest session shared by every signal asset. Add a
frozen execution-proxy parity audit for `SPY/SCHX`, `IEF/SPTI`, and `GLD/IAUM`, run it through KIS
read-only history and quote paths, and require both parity and exact whole-share fundability before
any rung-0 capital entry or first live fill.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: standard library, existing KIS adapter, exchange-calendars, SQLite  
**Storage**: existing `price_bars` SQLite; ephemeral JSON evidence  
**Testing**: pytest, live KIS branch smoke, Ruff, YAML, workflow text contracts  
**Constraints**: fail closed; no orders; unchanged caps, drawdown budget, rung percentages, and market-hours gate

## Constitution Check

- **Principle II whitelist**: CHANGED by explicit operator direction. The old three execution ETFs are replaced, not added alongside the new set.
- **Capital ladder**: STRENGTHENED. Every first-capital route gains shared parity and fundability requirements.
- **Backtest -> Canary -> Full**: PASS. Historical edge criteria are unchanged; execution evidence is added after them.
- **Risk controls**: PASS. Per-trade 50%, per-symbol 60%, total 100%, 10%/20% rung sizing, drawdown budget, kill switch, and regular-session-only routing remain unchanged.
- **Kernel impact**: K2 whitelist surface; forensic commit must contain `this changes the safety perimeter`.
- **Rollback**: revert the live mapping/config and parity-gate commits together. A rollback leaves rung 0 or existing-fill risk management; it must not silently restore an unvalidated mapping.

## Project Structure

```text
src/auto_invest/portfolio/
├── execution_proxy_parity.py
├── capital_ladder.py
└── live_entry_revalidation.py

src/auto_invest/canary/portfolio_harness.py
src/auto_invest/cli.py
deploy/observe-on-instance.sh
deploy/repair-ssh-boundary.sh
deploy/canary-live-portfolio.toml
deploy/global-trend-fixed-portfolio.toml
tests/unit/
tests/integration/
.github/workflows/
```

## Design Decisions

1. Common-session intersection chooses the endpoint; XNYS coverage inside that endpoint range still detects real holes.
2. Proxy criteria and pairs are code-level frozen constants so a runtime config edit cannot lower the bar.
3. The proxy audit uses adjusted closes and execution-ETF dollar volume from the same KIS adapter used by production.
4. The evidence validator recomputes every threshold check and expected mapping instead of trusting `passed=true`.
5. Entry readiness is one shared boolean consumed by every rung-0 branch; existing fills bypass only this first-entry gate so exits and risk reduction remain available.
6. Minimum notional is lowered in both validated and live configs. It is an execution control excluded from the strategy fingerprint; large-capital historical orders are unaffected, and exact parity is asserted in tests.

## Complexity Tracking

| Change | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Historical parity audit | A cheap ETF can track the wrong economic exposure | Current-price checks prove affordability, not strategy equivalence |
| Shared entry-readiness gate | Three entry paths currently apply different execution checks | Patching only the factory path leaves direct forward promotion open |
| Common-window helper | Latest-session lag is normal across ingestion calls | Ignoring integrity failures would hide real mid-window data holes |

