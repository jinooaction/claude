# Implementation Plan: Uncertainty-Aware ML Edge Ensemble

**Branch**: `Codex/145-ml-edge-ensemble` | **Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/145-ml-edge-ensemble/spec.md`

## Summary

Add a deterministic, uncertainty-aware machine-learning challenger for monthly stock/bond/gold allocation. It learns from lagged price and asset-specific macro interaction features with expanding walk-forward evaluation, blends regularized linear and shallow boosted-tree predictions, and uses forecast confidence to tilt a capped incumbent trend allocation. It deducts turnover costs and emits a no-live candidate package. A weekly workflow refreshes evidence; no code path edits live configuration or submits orders.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: scikit-learn, existing pandas/project analytics  
**Storage**: JSON/Markdown sidecar artifacts; no database migration  
**Testing**: pytest, hypothesis where useful, ruff, workflow static tests  
**Target Platform**: GitHub Actions and Linux research worker  
**Project Type**: Python library, CLI probe, scheduled workflow  
**Performance Goals**: 1971-present monthly experiment under 90 seconds  
**Constraints**: deterministic, no future leakage, no broker calls, long-only, costs included  
**Scale/Scope**: 3 assets, roughly 600 monthly observations, 2 model families, 3 cost levels

## Constitution Check

- I Position limits: PASS. Candidate weights cap each asset at 40% and total at 99%; no live cap changes.
- II Deny-by-default: PASS. Research universe is fixed and no whitelist changes occur.
- III AI judgment points: PASS. ML predicts returns; deterministic gates, not an LLM, decide readiness.
- IV Audit: PASS. Every run emits fingerprints, folds, gates, and replay command.
- V Secrets: PASS. Public research data only.
- VI Backtest → Canary → Full: PASS. This feature creates backtest evidence only.
- VII External APIs: PASS. Downloads are bounded and failure closes the run.
- VIII Change discipline: PASS. Workflow is research-only and rollback is one PR revert.
- IX Kernel: PASS. No K1-K6 or K-meta files change.
- X Measurement-driven growth: PASS. Candidate cannot reach capital from this feature. Rung-0 exploration and exact fingerprint checks remain; capital above 20% still requires existing EDGE_CONFIRMED gates. Missing holdout, forward, hardened-canary, broker, NAV, or fingerprint evidence fails closed.

## Project Structure

### Documentation

```text
specs/145-ml-edge-ensemble/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/ml-edge-report.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/ml_edge_ensemble.py
scripts/ml_edge_ensemble_probe.py
.github/workflows/ml-edge-ensemble.yml
tests/unit/test_ml_edge_ensemble.py
tests/integration/test_ml_edge_ensemble_probe.py
```

**Structure Decision**: Follow existing pure analytics + thin probe + sidecar workflow patterns. Live strategy and broker packages are not dependencies.

## Complexity Tracking

No constitutional violations. Two model families are required to estimate disagreement and avoid trusting one model's errors.
