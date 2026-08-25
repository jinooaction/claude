# Implementation Plan: Independent Energy Cross-Market Factory

**Branch**: `codex/163-independent-energy-cross-market` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)
**Input**: Frozen grade-4 strategy-family and objective-gate audit in `spec.md`

## Summary

Add a broker-free strategy factory that uses official EIA monthly crude, gasoline,
heating-oil, and natural-gas prices to time a long energy-equity/cash sleeve. Generate
exactly 16 transparent and adaptive candidates, select one on an early 120-month
development period, and evaluate it once on an embargoed holdout of at least 180
months. Report a new standalone timing lane beside the unchanged incumbent-diversifier
lane so profitability and portfolio diversification are no longer conflated.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: standard library, `xlrd`, `numpy`, `scikit-learn`, existing analytics helpers
**Storage**: JSON/Markdown sidecar evidence and append-only JSONL trial ledger
**Testing**: pytest unit and integration tests; ruff; YAML parse; strict repository harness
**Target Platform**: Linux GitHub Actions production research worker
**Project Type**: analytics library plus command-line probe and scheduled workflow
**Performance Goals**: complete four official data downloads, 16 candidate replays, controls, and evidence publication inside the existing 25-minute workflow budget
**Constraints**: deterministic output; no broker/order imports; one-month publication lag; no result-driven tuning; exact 16/16 and 736/736 audit contract; fail closed on missing or stale inputs
**Scale/Scope**: roughly 40 years of monthly data, four source series, one energy target, 16 candidates, and one canonical production sidecar

## Constitution Check

*GATE: Passed before research and rechecked after design.*

- **Principles I/II**: No position cap or whitelist changes. XLE remains an unimplemented intended expression and cannot be selected for live execution.
- **Principle IV**: Preserve 720 prior unique records and append 16 immutable strategy fingerprints. No audit deletion or replacement.
- **Principle V**: Public sources only; no KIS or paid secret in the research workflow.
- **Principle VI**: This is backtest evidence only. Even `FACTORY_EDGE` cannot skip exact live implementation, hardened canary, forward evidence, or later capital rungs.
- **Principle VIII.A**: Research workflow does not deploy or order during market hours.
- **Principle X.4**: `research_canary_eligible` remains false without executable config, whitelist authorization, hardened-canary evidence, and exact fingerprint identity. Rung 0 and capital 0 remain unchanged.
- **Gate interpretation**: The standalone lane changes how a new direct timing objective is classified; it does not lower or replace the existing diversifier, exploration, 20%+, forward, or live gates.
- **Rollback**: Revert the feature merge. The prior USDA canonical sidecar and 720-record contract remain reproducible from the preceding main commit.

## Project Structure

### Documentation

```text
specs/163-independent-energy-cross-market/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── production-result.md
├── contracts/
│   └── energy-cross-market-evidence.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/
└── energy_cross_market_factory.py

scripts/
└── energy_cross_market_factory_probe.py

tests/unit/
└── test_energy_cross_market_factory.py

tests/integration/
└── test_energy_cross_market_factory_probe.py

.github/workflows/
└── autonomous-strategy-factory.yml
```

**Structure Decision**: Extend the existing analytics/probe/workflow pattern used by
specs 155-162. Keep all new code research-only and publish through the existing
canonical factory sidecar rather than creating another capital consumer.

## Design Phases

### Phase 0 - Source and Criterion Research

1. Confirm official source identities, units, date coverage, release cadence, and known revision limitations.
2. Freeze the target proxy, publication lag, feature grammar, model settings, costs, split, and objective lanes before reading candidate returns.
3. Define empirical positive/null controls and synthetic family-size power checks.
4. Audit the conceptual mismatch between standalone timing and incumbent diversification without retroactively reclassifying prior trials.

### Phase 1 - Evidence Contract and Data Model

1. Parse source workbooks and ZIP data with strict series/header/date/value checks.
2. Build a lagged monthly panel and assert every feature month precedes the target return month.
3. Generate 16 deterministic candidates and expanding ridge predictions.
4. Emit both objective lanes, all-candidate descriptive metrics, controls, power, fingerprints, and live-parity blockers.

### Phase 2 - Implementation and Production

1. Implement tests before source behavior, then run focused replays.
2. Download current official data only after preregistration and produce the first result.
3. Integrate exact counts into the scheduled factory workflow and append the ledger.
4. Run full validation, merge, deploy, replay production, verify KIS read-only health, and refresh the handoff.

## Post-Design Constitution Re-check

Passed. The design adds research evidence and a correctly scoped classification lane only.
It neither creates an executable XLE config nor sets `research_canary_eligible=true`
without all existing X.4 requirements. No kernel or constitution file changes are planned.

## Complexity Tracking

No constitutional violation. The fourth candidate family uses a fixed ridge model because
the user explicitly requested meaningful use of AI; it is bounded by the same 16-candidate
count and is compared with three simpler rules to reveal whether it adds value.
