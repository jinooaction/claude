# Implementation Plan: 주문 거부·체결 품질 손익 관측

**Branch**: `Codex/083-rejected-order-execution-quality` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/083-rejected-order-execution-quality/spec.md`

## Summary

기존 064번 거부 주문 누적 평가를 중복 구현하지 않는다. 새 `execution-quality` 패키지는 이미 발행된 `opportunity_monitor.json`, `opportunity_history.json`, micro GTAA `LAST_RUN.md`, KIS smoke `LAST_RUN.md`만 읽어 실행 품질 JSON/Markdown을 발행한다. 이후 autonomous evolution loop와 pipeline liveness가 이 sidecar를 소비해 후보 선택과 생존 감시에 같은 근거를 남긴다.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: standard library, pytest, existing GitHub Actions shell workflow
**Storage**: GitHub Actions sidecar branch `automation/execution-quality-last-run`
**Testing**: pytest, ruff, PR quality gate, strict agent harness
**Target Platform**: GitHub Actions and local Codex worktree
**Project Type**: Python CLI/automation repository
**Performance Goals**: Probe remains deterministic and completes within a 10 minute workflow timeout.
**Constraints**: read-only, no broker API, no SSH, no order, no capital allocation, no live strategy change, no whitelist/caps change, no secrets.
**Scale/Scope**: One analytics module, one probe, one workflow, evolution manifest/candidate update, liveness registry update, tests and SDD docs.

## Constitution Check

- I Position sizing: pass. No position sizing or order path changes.
- II Whitelist: pass. No whitelist or symbol permission changes.
- III LLM judgment points: pass. No LLM call.
- IV Append-only audit and reconciliation: pass. No audit row deletion or reconciliation change.
- V Secret isolation: pass. The workflow reads public automation sidecars only and never reads secrets.
- VI Staged rollout: pass. Output is observation only and cannot promote Backtest, Canary, or Full stages.
- VII External API robustness: pass. No new external API call; KIS smoke result is consumed as existing evidence.
- VIII.A Market-hours deploy: pass. No deploy guard change.
- IX Self-modification boundary: pass. No constitution or kernel list change.
- X Measurement-driven autonomous growth: pass. Existing execution-quality evidence becomes a first-class measurement surface.

## Project Structure

### Documentation

```text
specs/083-rejected-order-execution-quality/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── execution-quality.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/execution_quality.py
src/auto_invest/analytics/evolution_loop.py
src/auto_invest/analytics/pipeline_liveness.py
scripts/execution_quality_probe.py
.github/workflows/execution-quality.yml
tests/unit/test_execution_quality.py
tests/unit/test_evolution_loop.py
tests/unit/test_pipeline_liveness.py
tests/integration/test_execution_quality_probe.py
tests/integration/test_evolution_loop_probe.py
tests/integration/test_pipeline_liveness_probe.py
```

**Structure Decision**: 새 CLI는 만들지 않는다. 기존 automation pattern처럼 `scripts/*_probe.py`와 workflow sidecar를 추가한다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Risk Grade

등급 2. 운영 자동화와 자율 후보 선택 근거를 바꾸지만, 주문·자본·전략·브로커 호출·비밀값·헌법·커널을 바꾸지 않는다.

## Rollback

- 기능 rollback은 `execution-quality.yml`, `execution_quality.py`, probe, evolution/liveness registry 변경을 되돌리면 된다.
- sidecar branch는 보고용이므로 stale/missing 상태가 liveness에서 비핵심 저하로만 드러난다.
- 064번 기존 `opportunity_monitor`와 live gate는 변경하지 않으므로 rollback해도 현재 주문 차단 안전장치는 유지된다.
