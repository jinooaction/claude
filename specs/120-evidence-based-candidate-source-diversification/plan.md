# Implementation Plan: Evidence-Based Candidate Source Diversification

**Branch**: `codex/evidence-based-candidate-source-diversification` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/120-evidence-based-candidate-source-diversification/spec.md`

## Summary

The autonomous work loop currently has enough evidence to know that real money must stay `PREVIEW_ONLY` / `NO_EDGE_YET`, but its next-work selection can still fall back to closed candidates when blocked validation packages are present. This feature adds an evidence-based source-diversification packet that turns retryable validation blockers into a fresh, read-only Codex work item without approving live workflows, changing capital, or weakening trading gates.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: stdlib dataclasses/json, existing `auto_invest.analytics` modules
**Storage**: Git-published sidecar JSON/Markdown artifacts only; no database migration
**Testing**: pytest, ruff, existing SDD/handoff probes
**Target Platform**: GitHub Actions sidecar workflows and local Codex validation
**Project Type**: Python CLI/analytics package inside a trading automation repository
**Performance Goals**: Deterministic report generation from current sidecars in under one second for fixture-sized inputs
**Constraints**: No broker API calls, no order submission, no live arming, no capital allocation, no whitelist/caps changes, no secret reads or writes
**Scale/Scope**: Current autonomous work report reads roughly two dozen sidecar surfaces and ranks at most ten operator-visible work packets

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|-----------|-------|--------|
| I. Position sizing & exposure limits | No position sizing or order path is changed. | PASS |
| II. Deny-by-default whitelist | No symbol, account, order-type, or session allowlist is changed. | PASS |
| III. Defined judgment points | No new LLM judgment point or always-on model call is added. | PASS |
| IV. Append-only audit + reconciliation | No audit mutation or reconciliation bypass is introduced. | PASS |
| V. Secret isolation | Inputs are public sidecars; summaries must remain redacted. | PASS |
| VI. Backtest -> Canary -> Full Live | The feature recommends more validation and never promotes to live. | PASS |
| VII. External API robustness | No new external API call is added. | PASS |
| VIII.A No market-hours deploys | This is repository logic; production deploy remains guarded by existing workflow policy. | PASS |
| IX. Self-modification boundary | No kernel path, constitution, or kernel manifest is touched. | PASS |
| X. Measurement-driven autonomous growth | The change uses measured sidecar evidence to choose the next work packet and keeps deploy distinct from live money. | PASS |

Risk grade: **2**. This changes autonomous operating behavior and handoff interpretation, but does not change the trading safety perimeter or money path.

## Project Structure

### Documentation (this feature)

```text
specs/120-evidence-based-candidate-source-diversification/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── evidence-source-diversification.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/
├── autonomous_work_execution.py
├── candidate_factory.py
└── candidate_result_executor.py

scripts/
├── autonomous_work_execution_probe.py
├── candidate_factory_probe.py
└── candidate_result_executor_probe.py

tests/unit/
├── test_autonomous_work_execution.py
├── test_candidate_factory.py
└── test_candidate_result_executor.py

tests/integration/
├── test_autonomous_work_execution_probe.py
├── test_candidate_factory_probe.py
└── test_candidate_result_executor_probe.py
```

**Structure Decision**: Keep the feature in the existing analytics/reporting modules. The primary behavior belongs in `autonomous_work_execution.py`; candidate factory and result executor changes should be limited to diagnostics only if the work packet needs richer fields.

## Complexity Tracking

No constitution violations or additional architectural complexity are required.
