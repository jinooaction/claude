# Implementation Plan: Broad No-Edge Vol-Target Drawdown

## Technical Context

- Language: Python
- Existing patterns: `src/auto_invest/analytics/broad_no_edge_tail_risk_convexity.py`, probe script pattern, released-work scan override
- Inputs: automation sidecar Markdown/JSON snapshots only
- Output: deterministic JSON and Markdown report
- Safety: no broker call, no order submission, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no paid external service, no constitution/kernel change

## Constitution Check

- Risk grade: 2
- Money path: no-live contract only
- Safety perimeter unchanged
- Audit behavior: completed candidate marker added to spec for released-work consumption

## Phase 0 Research

Use existing sidecars as the authority. Current money-path is `PREVIEW_ONLY`/`NO_EDGE_YET`; edge-autoarm is `WAIT_EDGE`; forward verdicts are all `NO_EDGE` with PSR below 0.95 and material drawdowns.

## Phase 1 Design

- Add core report builder in `src/auto_invest/analytics/broad_no_edge_vol_target_drawdown.py`.
- Add probe in `scripts/broad_no_edge_vol_target_drawdown_probe.py`.
- Add unit and integration tests.
- Add completed candidate marker in `spec.md`.

## Post-Design Check

The feature creates only a read-only contract. It does not alter live money behavior, broker routing, capital ladder execution, secrets, or safety policy files.
