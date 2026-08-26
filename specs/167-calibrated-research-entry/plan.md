# Implementation Plan: Calibrated Research Entry

**Branch**: `codex/167-calibrated-research-entry` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

## Summary

Replace the low-power `DSR >= 0.95 AND PBO <= 0.20 AND raw-752 Bonferroni` research-entry
combination with a preregistered, simulation-calibrated `holdout PSR >= 0.95 AND family PBO <=
0.25` contract. Reconstruct a deterministic 17-family ledger from all 752 raw audit rows, cap the
program at 20 families under a 1% per-family null-admission ceiling, and retain DSR and raw
Bonferroni as integrity-checked diagnostics.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Python standard library, NumPy, existing backtest-overfitting analytics  
**Storage**: JSON sidecars and append-only JSONL research ledger  
**Testing**: pytest, Ruff, YAML parse, workflow contracts, production sidecar replay  
**Performance**: Consumer assessment under 100 ms for 1,000 rows; calibration remains offline  
**Constraints**: Fail closed; no orders; no cap, whitelist, loss-budget, or 20%+ gate changes

## Constitution Check

- **Research rung 0 -> 1**: CHANGED. Overlapping low-power statistical blockers are replaced by a frozen calibrated contract.
- **Independent evidence**: PASS and strengthened with a consumer-recomputed research-family ledger.
- **Current candidate**: PASS. It remains ineligible under the new PBO 0.25 threshold and unchanged evidence/parity/fundability gates.
- **Backtest -> Canary -> Full**: PASS. Only eligibility for the existing 10% research rung changes.
- **20%+ gates**: PASS and unchanged.
- **Risk controls**: PASS. Drawdown, caps, whitelist, market hours, signatures, nonce, audit, and secrets are unchanged.
- **Kernel impact**: K-meta constitution change; dedicated forensic commit required with `this changes the safety perimeter`.
- **Rollback**: Revert constitution and implementation commits together. v3.1 becomes diagnostic-only and rung 0 remains unchanged.

## Project Structure

```text
src/auto_invest/analytics/
├── edge_gate_calibration.py
├── research_family_audit.py
└── options_variance_risk_premium_factory.py

src/auto_invest/portfolio/
└── factory_evidence.py

tests/unit/
├── test_edge_gate_calibration.py
├── test_research_family_audit.py
└── test_factory_evidence.py

tests/integration/
└── test_factory_evidence_gate.py
```

## Design Decisions

1. The shared analytics module owns deterministic family classification so producer and consumer use the same vocabulary, while the consumer still recomputes every row and compares the claimed value.
2. PBO is recomputed even when there is no selected candidate; DSR necessarily remains selected-candidate dependent.
3. The program budget uses `family_count * calibrated_null_ceiling <= 0.20`, not observed outcomes, so adding a 21st family fails before results unless a new calibration contract is preregistered.
4. Raw candidate Bonferroni stays visible in `raw_multiplicity_diagnostic` to preserve audit history without double-counting within-family selection.

## Complexity Tracking

| Change | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Constitution v10.1 amendment | Changes a 10% capital-entry safety contract | Code-only change would leave policy and runtime inconsistent |
| Family classifier | Historical ledger lacks an explicit family field on every row | Treating 752 rows as independent caused the present power failure |
| Frozen simulation calibration | Threshold quality must be reproducible before outcomes | Choosing a threshold from the current failed option result would be outcome fitting |
