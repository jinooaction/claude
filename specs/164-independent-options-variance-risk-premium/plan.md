# Implementation Plan: Independent Options Variance Risk Premium

**Branch**: `Codex/164-independent-options-variance-risk-premium` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)
**Input**: Frozen grade-4 options-premium and prior-adoption audit in `spec.md`

## Summary

Add a broker-free strategy factory that uses Cboe's cash-secured SPX put-writing index,
VIX, daily broad-market returns, and Treasury cash to test a recognized variance risk
premium directly. Generate exactly 16 passive, transparent, tail-guarded, and expanding
ridge candidates; select one on 84 early months; evaluate it once after a one-month
embargo; and report standalone premium harvesting separately from timing enhancement.
Audit the prior 736 strategy identities and released family decisions without retroactive
promotion.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: standard library, `numpy`, `scikit-learn`, existing analytics and significance helpers
**Storage**: JSON/Markdown sidecar evidence and append-only JSONL trial ledger
**Testing**: pytest unit and integration tests; ruff; YAML parse; strict repository harness
**Target Platform**: Linux GitHub Actions production research worker
**Project Type**: analytics library plus command-line probe and scheduled workflow
**Performance Goals**: complete official downloads, 16 candidates, real/synthetic controls, prior-adoption audit, and publication inside the existing 25-minute workflow budget
**Constraints**: deterministic output; no broker/order imports; strict month-end chronology; no result-driven tuning; exact 16/16 and 752/752 audit contract; fail closed on missing or stale inputs
**Scale/Scope**: about 19 years of continuous PUT history, four source surfaces, 16 candidates, nine released family decision files, and one canonical production sidecar

## Constitution Check

*GATE: Passed before research and rechecked after design.*

- **Principles I/II**: No position-cap, margin, or whitelist changes. PUTW and SPX options remain unimplemented intended expressions.
- **Principle IV**: Preserve 736 prior unique records and append 16 immutable fingerprints. No audit deletion or replacement.
- **Principle V**: Public sources only; no KIS or paid-data secret in the research workflow.
- **Principle VI**: This is backtest evidence only. A pass cannot skip executable parity, assignment/tax/margin design, hardened canary, forward evidence, or later capital rungs.
- **Principle VIII.A**: The research workflow does not deploy or order during market hours.
- **Principle X.4**: Rung 0, capital 0, and `research_canary_eligible=false` remain until exact strategy and consumer fingerprints, whitelist authorization, hardened-canary evidence, and all current gates exist.
- **Gate interpretation**: Standalone premium harvesting and timing enhancement are separate objectives. The new routing does not lower prior thresholds or reclassify holdout-inspected candidates.
- **Rollback**: Revert the feature merge. The energy sidecar and 736-record contract remain reproducible from preceding `main`.

## Project Structure

### Documentation

```text
specs/164-independent-options-variance-risk-premium/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── production-result.md
├── contracts/
│   └── options-variance-risk-premium-evidence.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/
└── options_variance_risk_premium_factory.py

scripts/
└── options_variance_risk_premium_factory_probe.py

tests/unit/
└── test_options_variance_risk_premium_factory.py

tests/integration/
└── test_options_variance_risk_premium_factory_probe.py

.github/workflows/
└── autonomous-strategy-factory.yml
```

**Structure Decision**: Extend the existing analytics/probe/workflow pattern used by
specs 155-163. The prior-adoption audit consumes existing family JSON evidence supplied
by the workflow; it does not create a second source of verdict truth.

## Design Phases

### Phase 0 - Source, Objective, and Tail-Risk Research

1. Confirm Cboe PUT and VIX source identities, methodology, date coverage, sparse pre-2007 rows, and benchmark limitations.
2. Freeze candidate grammar, chronology, costs, split, standalone and timing lanes before candidate return inspection.
3. Define PUT reference/null controls and 16-candidate selection-power simulation.
4. Define prior-family classifications that explain non-adoption without changing verdicts.

### Phase 1 - Evidence Contract and Data Model

1. Parse official CSV and ZIP data with strict headers, dates, values, and source hashes.
2. Build a monthly panel where all features through month `t` target month `t+1`.
3. Generate 16 deterministic candidates and expanding ridge predictions.
4. Emit standalone, timing, tail, control, power, prior-adoption, post-hoc, fingerprint, and live-parity evidence.

### Phase 2 - Implementation and Production

1. Write chronology, cost, tail, gate-routing, prior-audit, and fail-closed tests first.
2. Download current official data only after preregistration and record the first frozen result.
3. Integrate exact counts and evidence checks into the scheduled factory workflow.
4. Run full validation, merge, deploy or verify safe deferral, replay production, run KIS read-only smoke, and refresh handoff.

## Post-Design Constitution Re-check

Passed. The design adds research evidence only. It cannot create an options order,
margin use, capital allocation, whitelist entry, or executable policy. The live parity
block is mandatory even if the historical reference or selected candidate passes.

## Complexity Tracking

No constitutional violation. The expanding ridge family is bounded to four candidates,
fixed features, fixed regularization, and expanding chronology. Three simpler policy
families expose whether it adds value.
