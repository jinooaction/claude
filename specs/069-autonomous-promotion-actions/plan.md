# Implementation Plan: Autonomous Promotion Actions

**Branch**: `Codex/autonomous-promotion-actions` | **Date**: 2026-06-29 | **Spec**: `specs/069-autonomous-promotion-actions/spec.md`
**Input**: Feature specification from `specs/069-autonomous-promotion-actions/spec.md`

## Summary

스펙 068의 read-only 승격 판단을 실제 검증 채널로 이어 붙인다. 새 순수 코어는 promotion summary를 읽어 forward paper 등록과 canary 제출 상태를 계산한다. GitHub Actions는 상태 변경을 PR로 남기고, 별도 workflow가 등록된 promotion forward/canary 검증을 실행해 사이드카를 발행한다. 실제 주문, live config, capital ladder, whitelist/caps는 건드리지 않는다.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Typer, pytest, GitHub Actions, existing `auto-invest` CLI  
**Storage**: tracked JSON state files plus automation sidecar branches  
**Testing**: pytest, ruff, workflow text invariants  
**Target Platform**: local CLI and GitHub-hosted runners; paper/canary execution through existing server SSH pattern  
**Project Type**: Python CLI + automation workflows  
**Performance Goals**: action classification must be deterministic and complete in under one second for typical promotion queues  
**Constraints**: no direct live orders; no KIS/SSH secrets in action decision workflow; no path traversal; no live sentinel mutation  
**Scale/Scope**: dozens of promotion candidates, low-frequency scheduled runs

## Constitution Check

- Principles I-VII: PASS. No new live order placement, no risk gate weakening, no audit deletion.
- VIII.A: PASS. Safety tests assert no promotion workflow contains live-mode order commands.
- IX: PASS. Automation advances autonomously through PRs and sidecars, but hard safety boundaries remain non-negotiable.
- X.4/X.5: PASS. Capital sizing and strategy reassignment remain governed by existing spec 050 and spec 055 gates.
- `Backtest -> Canary -> Full`: PASS. This feature only automates transition into forward/canary evidence collection.

## Project Structure

### Documentation

```text
specs/069-autonomous-promotion-actions/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/promotion-actions.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/
└── promotion_actions.py

src/auto_invest/
└── cli.py

src/auto_invest/safety/
└── command_registry.py

scripts/
└── promotion_action_probe.py

automation/
├── promotion-forward-registry.json
└── promotion-canary-submissions.json

.github/workflows/
├── autonomous-promotion-actions.yml
├── promotion-forward-tracks.yml
└── promotion-canary-submissions.yml

tests/
├── fixtures/promotion_actions/fresh/
├── unit/test_promotion_actions.py
├── integration/test_promotion_action_probe.py
├── unit/test_pipeline_liveness.py
└── unit/test_safety_command_registry.py
```

**Structure Decision**: 기존 analytics/probe/workflow/liveness 패턴을 그대로 확장한다. 순수 판단 코어와 워크플로 실행을 분리해 테스트 가능한 경계와 운영 사이드카를 모두 남긴다.

## Complexity Tracking

No constitution violations.
