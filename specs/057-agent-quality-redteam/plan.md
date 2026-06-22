# Implementation Plan: Agent Quality Redteam Harness

**Branch**: `Codex/agent-quality-redteam-harness` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/057-agent-quality-redteam/spec.md`

## Summary

Extend the existing static Codex harness so it measures the work quality that matters most for this
repository: first-response depth, redteam failure handling, and factual handoff alignment. Keep the
implementation local, read-only, and fast; do not touch trading runtime or safety boundaries.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Standard library only for new scripts (`argparse`, `json`, `re`, `subprocess`, `tomllib`, `dataclasses`)  
**Storage**: Repository files under `.codex/harness/`, `HANDOFF.md`, PR body Markdown  
**Testing**: `pytest`, `ruff`  
**Target Platform**: Local Mac, Codex Cloud, GitHub Actions  
**Project Type**: Python CLI + operating documentation  
**Performance Goals**: Strict harness should stay near 1 second for static checks; full tests remain the broader gate.  
**Constraints**: Read-only probes, no network except caller-managed `git fetch`, no broker, no secrets, no orders, no constitution/kernel changes.  
**Scale/Scope**: Add at least 5 quality tasks, 6 redteam tasks, and HANDOFF fact checks integrated into the existing harness.

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Position Sizing & Exposure Limits | No change to order sizing or caps. |
| II. Deny-by-Default | No change to whitelist or trading permissions. |
| III. Claude Is Invoked Only at Defined Judgment Points | No new runtime LLM calls. |
| IV. Append-Only Audit Log + Daily Reconciliation | No audit-log mutation. |
| V. Secret Isolation | New probes do not read secrets or `.env`. |
| VI. Staged Rollout | No deployment or live promotion path change. |
| VII. External API Robustness | No external API calls in probes. |
| VIII.A Change Discipline | Operating change goes through PR and validation. |
| IX. Self-Modification Boundary | No constitution or kernel manifest touch. |
| X. Measurement-Driven Autonomous Growth | Measures agent work quality, not trading performance or capital. |

## Project Structure

### Documentation

```text
specs/057-agent-quality-redteam/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── harness-quality-redteam.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source

```text
.codex/
├── harness/
│   ├── evaluation_tasks.toml
│   ├── quality_tasks.toml
│   └── redteam_tasks.toml
└── quality-gate.md

.agents/skills/sync/SKILL.md
.claude/skills/sync/SKILL.md
.github/pull_request_template.md
AGENTS.md
CLAUDE.md
HANDOFF.md
scripts/
├── agent_harness_probe.py
├── check_handoff_facts.py
├── check_pr_quality_gate.py
└── local_concurrency_guard.py
tests/unit/
├── test_agent_harness_probe.py
├── test_check_handoff_facts.py
├── test_check_pr_quality_gate.py
└── test_local_concurrency_guard.py
```

**Structure Decision**: Extend the existing harness in place rather than creating a parallel framework.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/harness-quality-redteam.md](./contracts/harness-quality-redteam.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

The design remains a grade 2 operating-system change. It does not change trading safety boundaries,
kernel paths, order behavior, secrets, deploy restrictions, broker calls, or live-money behavior.
