# Implementation Plan: Agent Harness Evaluation

**Branch**: `Codex/world-class-agent-harness` | **Date**: 2026-06-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/056-agent-harness-eval/spec.md`

## Summary

Codex 하네스를 세계 최고 수준에 가깝게 만들기 위해, 규칙을 더 쓰는 데서 멈추지 않고
하네스 자체를 평가하는 로컬 프로브와 대표 과제 묶음을 추가한다. 등급 2 이상 PR에는 strict
하네스 평가 증거를 남기게 하여 운영 체계 변경의 회귀를 빠르게 드러낸다.

## Technical Context

**Language/Version**: Python 3.11 이상  
**Primary Dependencies**: 표준 라이브러리만 사용(`argparse`, `json`, `tomllib`, `dataclasses`)  
**Storage**: 저장소 파일(`.codex/harness/evaluation_tasks.toml`, PR 본문 Markdown)  
**Testing**: `pytest`, `ruff`  
**Target Platform**: 로컬 Mac, Codex Cloud, GitHub Actions  
**Project Type**: Python CLI + 운영 문서  
**Performance Goals**: 프로브는 일반 저장소 상태에서 1초 안팎으로 끝나고 네트워크를 사용하지 않는다.  
**Constraints**: 읽기 전용, 비밀값 접근 없음, 외부 API 없음, 주문 없음, 헌법·커널 변경 없음.  
**Scale/Scope**: 첫 버전은 정적 통제 10개 이상과 평가 과제 12개 이상을 다룬다.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|-----------|------------|
| I. Position Sizing & Exposure Limits | 변경 없음. 주문 경로와 포지션 한도 코드를 건드리지 않는다. |
| II. Deny-by-Default | 변경 없음. 허용 종목·주문 허용 목록을 건드리지 않는다. |
| III. Claude Is Invoked Only at Defined Judgment Points | 변경 없음. 새 LLM 호출을 만들지 않는다. |
| IV. Append-Only Audit Log + Daily Reconciliation | 변경 없음. 감사 로그 삭제·수정 없음. |
| V. Secret Isolation | 통과. 프로브는 비밀값과 환경 변수를 읽지 않는다. |
| VI. Staged Rollout | 변경 없음. 배포·실거래 승격 흐름을 바꾸지 않는다. |
| VII. External API Robustness | 통과. 외부 API를 호출하지 않는다. |
| VIII.A Change Discipline | 통과. 배포를 수행하지 않는다. |
| IX. Self-Modification Boundary | 통과. 헌법과 커널 목록은 변경하지 않는다. |
| X. Measurement-Driven Autonomous Growth | 통과. 돈 경로가 아니라 작업 하네스 평가만 추가한다. |

## Project Structure

### Documentation (this feature)

```text
specs/056-agent-harness-eval/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── harness-probe.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
.codex/
├── harness/
│   └── evaluation_tasks.toml
└── quality-gate.md

.github/
└── pull_request_template.md

scripts/
├── agent_harness_probe.py
└── check_pr_quality_gate.py

tests/
└── unit/
    ├── test_agent_harness_probe.py
    └── test_check_pr_quality_gate.py
```

**Structure Decision**: 기존 운영 자동화는 `scripts/`와 `.codex/`에 있으므로 같은 표면에
추가한다. 패키지 런타임과 거래 경로는 건드리지 않는다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/harness-probe.md](./contracts/harness-probe.md),
and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

설계 후에도 헌법·커널·주문·비밀값·배포·돈 경로 변경은 없다. 새 프로브는 로컬 파일만 읽고,
PR 검사기는 본문 Markdown만 읽는다. 안전 경계 확대 없음.
