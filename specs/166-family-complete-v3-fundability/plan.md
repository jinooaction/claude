# Implementation Plan: Family Complete V3 and Fundability

**Branch**: `Codex/166-family-complete-v3-fundability` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/166-family-complete-v3-fundability/spec.md`

## Summary

Replace the capital consumer's producer-trusting factory check with an independently recomputed
`family-complete-v3` assessment, charge every selected candidate for all globally audited trials,
and add an exact small-capital fundability assessment to both rung-1 arming and first-fill
revalidation. The change only narrows upward capital entry and leaves all downward risk actions,
orders, whitelists, caps, and the 20% drawdown budget unchanged.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Python standard library, Pydantic configuration models, existing order planner  
**Storage**: JSON sidecars, TOML portfolio configuration, append-only JSONL research ledger  
**Testing**: pytest, Ruff, YAML parsing, workflow text contracts, production sidecar replay  
**Target Platform**: GitHub Actions and the Linux dry-run/live worker  
**Project Type**: Python research, portfolio planning, and automated-trading control plane  
**Performance Goals**: Pure assessments under 100 ms for 1,000 audit rows; no extra order submission  
**Constraints**: Fail closed; no whitelist/cap/budget relaxation; no order in backtest or assessment  
**Scale/Scope**: 752 current audit rows, 16 current family rows, up to five ladder rungs

## Constitution Check

*GATE: Passed before Phase 0 and must be re-checked after Phase 1.*

- **Rung 0 research entry**: CHANGED, stricter. It now requires independently recomputed v3 evidence, program-wide multiplicity, and exact fundability.
- **EDGE_CONFIRMED above 20%**: PASS and unchanged.
- **Exact fingerprint identity**: PASS and strengthened through current-family row and deploy-config cross-checks.
- **Missing evidence**: PASS. Missing audit rows, standardized statistics, parity, preview, quotes, or fundability stays at 0%.
- **Backtest -> Canary -> Full**: PASS. A backtest cannot order; v3 can only qualify the existing bounded research canary.
- **Risk controls**: PASS. K1/K2, 20% drawdown budget, circuit breaker, regular-hours, signing, nonce, reconciliation, and audit are unchanged.
- **Kernel impact**: K-meta because constitution X.4 changes from producer-declared v2 acceptance to consumer-recomputed v3. A dedicated forensic constitution commit is required.
- **Rollback**: Revert the feature and constitution commits together. Existing rung 0 remains rung 0; no capital migration occurs.

## Project Structure

### Documentation

```text
specs/166-family-complete-v3-fundability/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── production-result.md
├── contracts/family-complete-v3.json.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/portfolio/
├── factory_evidence.py
├── fundability.py
├── capital_ladder.py
└── live_entry_revalidation.py

src/auto_invest/
└── cli.py

.github/workflows/
├── autonomous-strategy-factory.yml
├── forward-edge-autoarm.yml
└── rebalance-live-canary.yml

tests/unit/
├── test_factory_evidence.py
├── test_fundability.py
├── test_capital_ladder.py
├── test_live_entry_revalidation.py
├── test_forward_edge_autoarm_workflow.py
└── test_live_entry_revalidation_workflow.py
```

**Structure Decision**: Keep research proof and execution feasibility as separate pure modules, then
compose them only at the two existing upward money gates. This preserves the order planner as the
single source of quantity rounding and keeps the backtest workflow broker-free.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Constitution X.4 major amendment | Old v2 can authorize capital from producer self-report without global multiplicity or fundability | A documentation warning cannot stop an automated rung-1 promotion |
