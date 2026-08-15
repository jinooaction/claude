# Implementation Plan: Broad No-Edge Tail-Risk Convexity

**Branch**: `codex/broad-no-edge-tail-risk-convexity` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

## Summary

Add a no-live, deterministic contract that turns existing broad `NO_EDGE` evidence into tail-risk and convexity experiment lanes. The contract consumes existing sidecars only and emits JSON/Markdown for automation, tests, and released-work closure.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: stdlib dataclasses/json, existing `auto_invest.analytics.released_work`  
**Storage**: none; reads sidecar snapshots from files supplied to the probe  
**Testing**: pytest, ruff  
**Target Platform**: local and GitHub Actions runners  
**Project Type**: Python analytics module + CLI-style probe

## Constitution Check

- Real orders: none.
- Capital allocation/live strategy/whitelist/caps: unchanged.
- Broker API/secrets/external paid services: not touched.
- Safety boundary: no-live contract only.
- Risk grade: 2 because autonomous-work, SDD, PR quality gate, handoff/released-work behavior affect the operating loop.

## Project Structure

```text
src/auto_invest/analytics/broad_no_edge_tail_risk_convexity.py
scripts/broad_no_edge_tail_risk_convexity_probe.py
tests/unit/test_broad_no_edge_tail_risk_convexity.py
tests/integration/test_broad_no_edge_tail_risk_convexity_probe.py
specs/136-broad-no-edge-tail-risk-convexity/
```

## Complexity Tracking

No new safety boundary exception. The new code mirrors the existing broad no-edge contract pattern to avoid a new framework.
