# Implementation Plan: Broad Frontier Expansion NO_EDGE Refresh

## Summary

Extend autonomous-work routing so completed broad no-edge first-wave work does not loop back into a fresh parent candidate. Add deterministic second-wave no-live candidates that keep the system moving toward investable evidence without opening live-money gates.

## Risk Grade

Grade 2: operating-loop and handoff behavior changes. No safety perimeter or live-money action changes.

## Technical Context

- Main module: `src/auto_invest/analytics/autonomous_work_execution.py`
- Tests: `tests/unit/test_autonomous_work_execution.py`
- Release marker: `completed_candidate_id: candidate-broad-frontier-expansion-no-edge-122eb31c06bd`

## Safety Boundary

No broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel change, no external paid service.

## Validation

Run focused tests first, then full pytest, lint, diff check, handoff facts, strict harness, and PR quality gate.
