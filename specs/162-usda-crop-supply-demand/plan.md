# Implementation Plan: USDA Crop Supply-Demand Factory

**Branch**: `Codex/162-usda-crop-supply-demand` | **Date**: 2026-08-25 | **Spec**: `specs/162-usda-crop-supply-demand/spec.md`

## Summary

Append a point-in-time USDA crop-revision family to the no-order strategy factory, retain every existing promotion threshold, and add an actual-holdout power diagnosis so a rejection can be attributed to criteria, evidence strength, economics, or live parity.

## Technical Context

- **Language**: Python 3.12 in the existing `uv` environment
- **Primary module**: new `src/auto_invest/analytics/usda_crop_supply_demand_factory.py`
- **Entrypoint**: new `scripts/usda_crop_supply_demand_factory_probe.py`, wired after spec 158
- **Data**: USDA ESMIS archived WASDE XLS releases, existing Shiller/gold/FRED inputs, existing gate controls and calibration
- **Tests**: pytest unit and workflow contracts, then full pytest and ruff
- **Constraints**: deterministic point-in-time parsing, exactly 16 trials, no broker/order/capital/whitelist changes

## Constitution Check

- Principles I-VII and VIII.A remain unchanged.
- Grade 4 full SDD applies because a passing family can nominate a future 10% research canary.
- The producer cannot bypass the versioned complete-family consumer, hardened canary, fingerprint identity, capital ladder, or `Backtest -> Canary -> Full` order.
- Constitution and kernel files are unchanged.
- Reversal: remove the USDA workflow step/module and restore the spec-158 sidecar as canonical; no live state or capital requires migration.

## Design

1. Discover archived WASDE XLS links from official ESMIS index pages and retain source URL/hash lineage.
2. Parse rightmost projected U.S. corn, wheat, and soybean ending stocks and total use from each release.
3. Compute same-marketing-year one/three-release scarcity revisions; neutralize marketing-year rollovers.
4. Freeze four crop families x two horizons x two maximum GLD weights for 16 policies.
5. Select on 60 months, embargo one, evaluate at least 120 months, and retain 10/25/50bp turnover costs.
6. Apply unchanged full and paper gates, append 16 records to the 704-record audit, and expose actual holdout gate power.
7. Publish only complete 720-record evidence; preserve no-order behavior and exact live-parity blocking.

## Verification

- Parser schema, release identity, marketing-year rollover, candidate uniqueness, split isolation, audit counts, source freshness, and broker-boundary regressions.
- Latest-data local replay before result documentation.
- `uv run pytest`, `uv run ruff check src tests`, YAML parse, strict harness, HANDOFF fact check, and PR body gate.
- After merge: deploy, production strategy-factory replay, no-order KIS smoke, and money/capital-path checks.
