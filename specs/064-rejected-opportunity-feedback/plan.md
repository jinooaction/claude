# Implementation Plan: Rejected Opportunity Feedback Loop

**Branch**: `Codex/opportunity-strategy-loop` | **Date**: 2026-06-26 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/064-rejected-opportunity-feedback/spec.md`

## Summary

Extend the existing rejected-order opportunity report from a per-run diagnostic into a rolling measurement loop. Each micro GTAA run appends the latest report to a bounded history, emits a cumulative monitor summary, includes that summary in Telegram and the micro sidecar, and exposes the same summary as read-only execution feedback to the autonomous reassignment workflow. The signal can request strategy or execution review, but it cannot place orders or override the existing reassignment gates.

## Technical Context

**Language/Version**: Python 3.11 plus GitHub Actions YAML  
**Primary Dependencies**: Standard library and existing project modules only  
**Storage**: Sidecar JSON files on `automation/rebalance-micro-gtaa-last-run`; no database migration  
**Testing**: `pytest`, `ruff`, PR quality gate script, handoff fact check, strict agent harness  
**Target Platform**: GitHub Actions runner and local CLI  
**Project Type**: Python CLI + operational workflows  
**Performance Goals**: History update is small JSON processing and must fit inside existing workflow timeout.  
**Constraints**: Grade 2 operational change. No broker order submission, no capital change, no whitelist/cap change, no strategy file mutation from this feedback signal.

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Position Sizing & Exposure Limits | No cap or sizing logic changes. |
| II. Deny-by-Default | No whitelist expansion. |
| III. Defined Judgment Points | No LLM or discretionary runtime call. |
| IV. Append-Only Audit Log | Does not alter audit semantics; sidecar history is bounded operational evidence. |
| V. Secret Isolation | No new secrets; sidecar and Telegram contain no token/account identifiers. |
| VI. Staged Rollout | Adds observation and review signals only. |
| VII. External API Robustness | History/monitor generation tolerates missing opportunity reports and malformed previous history. |
| VIII.A Change Discipline | Workflow changes land through PR; no market-hours deploy guard change. |
| IX. Self-Modification Boundary | No constitution or kernel manifest change. |
| X. Measurement-Driven Autonomous Growth | Adds live execution feedback as a measured input to strategy evolution without bypassing gates. |

Risk classification: **Grade 2 operational-system change**. The workflow and reassignment evidence path change, but actual money path and safety boundaries do not.

## Project Structure

```text
specs/064-rejected-opportunity-feedback/
├── spec.md
├── plan.md
├── tasks.md
└── quickstart.md

src/auto_invest/
├── analytics/opportunity_monitor.py
├── cli.py
└── portfolio/auto_reassign.py

scripts/
└── opportunity_monitor_sidecar.py

.github/workflows/
├── rebalance-micro-gtaa-canary.yml
└── reassign-on-tournament.yml

tests/
├── integration/test_opportunity_monitor_cli.py
└── unit/
    ├── test_opportunity_monitor.py
    ├── test_micro_gtaa_canary.py
    ├── test_reassign_workflow_leaderboard_json.py
    ├── test_auto_reassign.py
    └── test_safety_command_registry.py
```

## Design Decisions

- Keep the single-run sign convention from `order_opportunity.py`: positive means the rejected order would now be favorable; negative means rejection avoided a worse outcome.
- Interpret negative cumulative PnL as strategy-intent review evidence and positive cumulative PnL as execution/broker-path review evidence.
- Store a bounded rolling history on the existing micro GTAA sidecar branch instead of adding a new branch.
- Feed the monitor summary into `reassign-decide` as evidence, not as a gate override.

## Validation

1. Focused tests for monitor math, CLI/script behavior, workflow wiring, and reassign feedback.
2. Full `uv run pytest`.
3. Full `uv run ruff check src tests`.
4. `uv run python scripts/check_handoff_facts.py`.
5. `uv run python scripts/agent_harness_probe.py --strict`.
6. PR body quality gate check before merge.
