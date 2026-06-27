# Implementation Plan: Micro GTAA Intent-Loss Gate

**Branch**: `Codex/micro-gtaa-intent-loss-gate` | **Date**: 2026-06-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/065-micro-gtaa-intent-loss-gate/spec.md`

## Summary

Stop micro GTAA from repeating real-money attempts after the latest rejected-order opportunity signal shows the intended buy would already be loss-making. The implementation immediately disarms the micro GTAA sentinel, adds a reusable opportunity live gate, wires that gate before preflight/live order submission, preserves prior opportunity evidence when live is skipped, and surfaces the gate decision in sidecar and Telegram outputs.

## Technical Context

**Language/Version**: Python 3.11, GitHub Actions YAML  
**Primary Dependencies**: Existing stdlib helper style, existing `auto_invest.analytics.opportunity_monitor`  
**Storage**: Existing repository sentinel and `automation/rebalance-micro-gtaa-last-run` sidecar JSON files  
**Testing**: `pytest`, static workflow tests, `ruff`  
**Target Platform**: GitHub Actions runner and existing Vultr `/opt/auto-invest` deployment path  
**Project Type**: Python CLI/library plus operations workflows  
**Performance Goals**: Gate evaluation completes within a normal workflow step and does not call broker APIs.  
**Constraints**: No new broker mutation, no capital increase, no whitelist expansion, no secret logging, no market-session bypass.  
**Scale/Scope**: One micro GTAA live canary workflow and its opportunity monitor evidence path.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Rationale |
|-----------|--------|-----------|
| I. Position sizing and exposure limits | PASS | This change reduces exposure and keeps existing caps unchanged. |
| II. Deny-by-default whitelist | PASS | No tradeable symbol is added; live submission can only be blocked. |
| III. LLM judgment points | PASS | No LLM call is added. |
| IV. Append-only audit and reconciliation | PASS | Existing sidecar and workflow evidence are extended; audit deletion is not introduced. |
| V. Secret isolation | PASS | Gate reads public sidecar JSON and logs no secrets. |
| VI. Backtest → Canary → Full Live | PASS | Canary execution is made more conservative; no promotion is introduced. |
| VII. External API robustness | PASS | The new gate does not call external APIs. |
| VIII.A. No live deploys during market hours | PASS | The merge deploy path is still guarded; workflow live step remains regular-session gated. |
| IX. Self-modification boundary | PASS | Kernel safety surfaces are not relaxed. |
| X. Measurement-driven growth | PASS | The live-money path now acts on measured negative evidence instead of ignoring it. |

## Project Structure

### Documentation (this feature)

```text
specs/065-micro-gtaa-intent-loss-gate/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code

```text
automation/
└── rebalance-micro-gtaa.request

src/auto_invest/analytics/
└── opportunity_monitor.py

scripts/
├── opportunity_live_gate.py
└── opportunity_monitor_sidecar.py

.github/workflows/
└── rebalance-micro-gtaa-canary.yml

tests/
├── unit/test_opportunity_monitor.py
├── unit/test_micro_gtaa_canary.py
└── unit/test_micro_gtaa_telegram_alerts.py
```

**Structure Decision**: Keep the new gate beside the opportunity monitor because the evidence and thresholds already live there. Use a small `scripts/` entrypoint so GitHub Actions can evaluate the gate without installing the package.

## Complexity Tracking

No constitution violation is required. The change is grade 4 because it touches a real-order path, but the direction is exposure-reducing.
