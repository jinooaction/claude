# Implementation Plan: 자율 루프 품질 폐쇄

**Branch**: `Codex/081-autonomous-loop-world-class` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/081-autonomous-loop-quality-closure/spec.md`

## Summary

자율 성장 루프의 남은 흠을 운영적으로 닫는다. 안전 후보에는 Codex가 바로 착수할 수 있는 실행 계약을 추가하고, 돈 경로 관측 수 차이는 정상 시점 차이로 표시하며, operator-status 뒤 pipeline-liveness가 다시 실행될 수 있게 한다. 실제 주문, 자본 배분, 코드 자동 수정, PR 자동 생성, live 설정 변경은 추가하지 않는다.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Standard library, pytest, GitHub Actions  
**Storage**: Git sidecar branches and repository Markdown/JSON artifacts  
**Testing**: pytest, ruff, handoff fact checker, strict agent harness, PR quality checker  
**Target Platform**: GitHub Actions and local Codex worktrees  
**Project Type**: Python CLI/analytics package with operational workflows  
**Performance Goals**: Probes remain small read-only jobs under existing workflow timeouts  
**Constraints**: No broker API call, no order, no capital allocation, no live strategy change, no secret persistence, no paid-service use  
**Scale/Scope**: Existing autonomous sidecar pipeline and one new operating correction spec

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- 원칙 I-VII, VIII.A, IX, X 보존: 통과. 보고·분류·워크플로 트리거만 바꾸며 돈 경로 권한을 늘리지 않는다.
- K1/K2/K4/K5/K6, 헌법, 커널 목록, 주문 제한, 감사 로그, 비밀값 정책: 변경 없음.
- Backtest -> Canary -> Full 단계: 변경 없음.
- 장중 배포 제한과 외부 비용 경계: 변경 없음.
- 위험 등급: 등급 2 운영 체계 변경. `.codex/quality-gate.md`, strict harness, HANDOFF 사실 검증, 전체 테스트와 린트를 적용한다.

## Project Structure

### Documentation (this feature)

```text
specs/081-autonomous-loop-quality-closure/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── autonomous-loop-quality.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/
├── autonomous_work_execution.py
└── money_gate_alignment.py

tests/unit/
├── test_autonomous_work_execution.py
├── test_money_gate_alignment.py
└── test_pipeline_liveness.py

.github/workflows/
└── pipeline-liveness.yml
```

**Structure Decision**: Existing analytics modules and workflow files are extended in place. No new service or authority boundary is added.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
