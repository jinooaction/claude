# Implementation Plan: Full-Gate Audit and Commodity Supply-Demand Factory

**Branch**: `Codex/158-full-gate-audit-commodity-supply-demand` | **Date**: 2026-08-25 | **Spec**: `specs/158-full-gate-supply-demand/spec.md`

## Summary

Extend the empirical controls from PSR-only to the complete candidate promotion decision, then append a new 16-policy EIA petroleum supply-demand family to the autonomous no-order strategy factory.

## Technical Context

- **Language**: Python 3.12, existing `uv` environment
- **Primary modules**: `real_world_gate_controls.py`, new `commodity_supply_demand_factory.py`
- **Entrypoint**: new `commodity_supply_demand_factory_probe.py`, wired after spec 157
- **Data**: official EIA weekly XLS, AQR/Fama-French controls, existing GSG/Shiller/gold/FRED inputs
- **Tests**: pytest unit and workflow contract tests; full pytest and ruff before merge
- **Constraints**: deterministic, point-in-time publication lag, no broker import, no orders, no capital or whitelist changes

## Constitution Check

- Principles I-VII and VIII.A remain unchanged.
- The feature is backtest evidence only and cannot bypass `Backtest -> Canary -> Full`.
- Grade 4 full SDD is used because a passing result could nominate a later research canary.
- Constitution and kernel files are not modified.
- Reversal: remove the new workflow step/module and restore the spec-157 sidecar chain; existing safety gates remain intact.

## Design

1. Add a reusable complete diversifier-gate evaluator to the real-world control audit.
2. Align AQR, cash, and incumbent returns on common 2007-onward destination months; apply a fixed 50bp annual haircut.
3. Require the positive control to pass and the demeaned null to fail the complete decision.
4. Parse four fixed EIA series with five-day availability and aggregate latest-known weekly observations to monthly signals.
5. Generate four grammars x two windows x two maximum weights, select on 96 months, embargo one, evaluate untouched holdout.
6. Publish 704-record audit evidence and preserve fail-closed no-order behavior.

## Verification

- Parser schema, lag, candidate-count, identity, full-control positive/null, split isolation, gate attribution, and broker-boundary tests.
- Latest-data local replay before commit.
- `uv run pytest`, `uv run ruff check src tests`, YAML parse, strict harness, HANDOFF fact check, PR quality gate.
- After merge: deploy, production strategy-factory replay, KIS no-order smoke, money/capital-path truth check.
