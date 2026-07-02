# Implementation Plan: 레짐·성과 후보 점수화

**Branch**: `Codex/082-regime-performance-candidate-scoring` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/082-regime-performance-candidate-scoring/spec.md`

## Summary

자율 성장 루프가 `regime-stratify`, `public-data`, `promote-readiness`를 함께 읽어 분석 후보 점수에 반영한다. `promote-readiness`는 승격 실행 신호가 아니라 읽기 전용 성과·트랙레코드 표면으로만 쓰고, 누락·stale·오류 상태는 후보 신뢰도를 낮추거나 증거 의존 상태로 남긴다.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: standard library, pytest, existing GitHub Actions shell workflow  
**Storage**: JSON/Markdown sidecar artifacts on automation branches  
**Testing**: pytest, ruff, existing PR quality gate  
**Target Platform**: GitHub Actions and local Codex worktree  
**Project Type**: Python CLI/automation repository  
**Performance Goals**: Evolution scan remains deterministic and completes within existing workflow timeout.  
**Constraints**: read-only, no broker API, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secrets.  
**Scale/Scope**: One candidate-scoring loop, one probe manifest, unit/integration tests, SDD and handoff.

## Constitution Check

- I Position sizing: pass. No order sizing or capital exposure path changes.
- II Whitelist: pass. No tradeable universe or order symbol path changes.
- III LLM judgment points: pass. No new LLM call.
- IV Append-only audit and reconciliation: pass. No audit schema or reconciliation path changes.
- V Secret isolation: pass. Existing sidecar text is masked through current output safeguards; no new secret read.
- VI Staged rollout: pass. `promote-readiness` remains evidence only and cannot promote capital or live strategies.
- VII External API robustness: pass. No new external API call.
- VIII.A Market-hours deploy: pass. No live deploy logic change; normal deploy guard remains authoritative.
- IX Self-modification boundary: pass. No kernel, constitution, or safety perimeter touch.
- X Measurement-driven autonomous growth: pass. This feature makes autonomous growth more measurement-driven by using existing performance evidence before candidate scoring.

## Project Structure

### Documentation

```text
specs/082-regime-performance-candidate-scoring/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── regime-performance-candidate-scoring.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/evolution_loop.py
scripts/evolution_loop_probe.py
tests/unit/test_evolution_loop.py
tests/integration/test_evolution_loop_probe.py
tests/fixtures/evolution_loop/
.github/workflows/autonomous-evolution-loop.yml
CLAUDE.md
.specify/feature.json
```

**Structure Decision**: 기존 autonomous evolution loop와 probe manifest를 확장한다. 새 CLI나 새 workflow를 만들지 않는다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
