# Implementation Plan: Commodity Positioning and Real-World Gate Controls

**Branch**: `Codex/157-commodity-inventory-positioning-positive-controls` | **Date**: 2026-08-25 | **Spec**: [spec.md](spec.md)

## Summary

Add an empirical gate audit using Fama-French market excess returns and AQR diversified time-series
momentum, then build a 16-candidate CFTC/EIA positioning and inventory family that reuses the corrected
development-only selection and untouched-holdout decision contract.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: NumPy, httpx, xlrd, standard-library ZIP/XML/CSV  
**Storage**: JSON/Markdown sidecar evidence and append-only audit catalog  
**Testing**: pytest and ruff  
**Target Platform**: GitHub Actions and the existing Linux production worker  
**Project Type**: analytics library plus no-order command-line probe  
**Performance Goals**: source collection and 16-candidate replay under 15 minutes  
**Constraints**: official sources, deterministic hashes, no broker import, no raw licensed-series publication  
**Scale/Scope**: 12 CFTC contracts, one EIA inventory series, 16 candidates, 688 audit records

## Constitution Check

| Principle | Design response | Status |
|---|---|:---:|
| I-II Limits and deny-by-default | GSG remains unapproved and every output is research-only. | PASS |
| III Determinism | Candidate generation, controls, and verdict contain no model call. | PASS |
| IV Audit | Preserve 672 prior records and append 16 immutable fingerprints. | PASS |
| V Secrets | Primary strategy sources are keyless; no secret is persisted. | PASS |
| VI Staging | A pass grants only research-canary eligibility before existing stages. | PASS |
| VII External failure | Source, schema, lag, freshness, and hash failures close promotion. | PASS |
| VIII.A Market hours | Research and production replay submit no order. | PASS |
| IX Self modification | Full SDD, grade-4 PR, rollback, production replay, and handoff. | PASS |
| X Measured growth | Synthetic and empirical gate power, holdout, costs, and blend precede promotion. | PASS |

## Project Structure

```text
specs/157-commodity-positioning-gate-controls/
src/auto_invest/analytics/real_world_gate_controls.py
src/auto_invest/analytics/commodity_positioning_factory.py
scripts/commodity_positioning_factory_probe.py
tests/unit/test_real_world_gate_controls.py
tests/unit/test_commodity_positioning_factory.py
tests/integration/test_commodity_positioning_factory_probe.py
.github/workflows/autonomous-strategy-factory.yml
```

## Sequence

1. Implement parsers and tests for real positive controls, CFTC JSON, and EIA XLS.
2. Implement publication lags, normalized signals, 16 frozen candidates, costs, and split.
3. Bind empirical and synthetic calibration to the existing tiered decision.
4. Add no-order probe, workflow artifacts, audit catalog, and immediate replay.
5. Run full validation, merge, deploy, verify production and KIS no-order state, and refresh handoff.

## Rollback

Revert the two analytics modules, probe, workflow additions, xlrd dependency, and spec pointer. Prior
commodity-term-structure and all existing strategy evidence remain readable. Capital, orders, whitelist,
constitution, and kernel are never changed.
