# Feature Specification: Source Diversification Candidate Closure

**Feature Branch**: `Codex/090-source-diversification-bottleneck`
**Created**: 2026-07-03
**Status**: Draft
**Input**: User description: "다음 후보를 목표 스킬과 SDD 기준으로 꼼꼼하게 완수한다. 최신 재현 후보는 `candidate-source-diversification-sidecar-bottleneck`이며, 스펙 089가 만든 산출 후보가 다시 실행 후보로 선택되는 자기참조 루프를 닫는다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 완료된 산출 후보를 장부로 닫기 (Priority: P1)

운영자는 스펙 089가 이미 구현한 후보 소스 다변화 산출물이 다음 세션에서 다시 "새 작업"처럼 선택되지 않기를 원한다.

**Why this priority**: 현재 최신 sidecar 재현은 `candidate-source-diversification-sidecar-bottleneck`을 `EXECUTION_READY`로 고른다. 하지만 이 후보의 행동 설명은 스펙 089가 이미 구현한 내용과 겹치므로, 같은 일을 다시 시작하면 자율 루프가 완료 후보를 재발굴하는 셈이다.

**Independent Test**: 완료된 스펙 090에서 `candidate-source-diversification-sidecar-bottleneck` 완료 마커를 읽은 released-work 장부가 해당 후보를 `released`로 기록하면 검증된다.

**Acceptance Scenarios**:

1. **Given** 스펙 089가 source diversification 후보를 생성했고 스펙 090 tasks가 모두 완료됨, **When** released-work 장부가 저장소를 스캔함, **Then** `candidate-source-diversification-sidecar-bottleneck`을 완료 후보로 기록한다.
2. **Given** 스펙 090 tasks가 완료되지 않음, **When** released-work 장부가 저장소를 스캔함, **Then** 해당 후보를 완료로 기록하지 않는다.

---

### User Story 2 - 다음 실제 후보로 전진시키기 (Priority: P2)

운영자는 완료된 source diversification 산출 후보가 닫힌 뒤 자율 작업 실행 루프가 다음 거시 후보인 목적 함수와 탐색 예산 보정으로 넘어가기를 원한다.

**Why this priority**: 스펙 089는 upstream 후보 생성을 개선했지만, downstream 실행 루프가 산출 후보를 완료로 보지 못하면 같은 후보가 계속 최상위에 남는다.

**Independent Test**: 최신 sidecar와 저장소 released-work override를 넣어 자율 작업 실행을 재현했을 때 `selected_work.candidate_id`가 `candidate-autonomous-growth-objective-calibration`이면 검증된다.

**Acceptance Scenarios**:

1. **Given** evolution backlog에 `candidate-source-diversification-sidecar-bottleneck`이 있고 released-work가 이 후보를 완료로 기록함, **When** 자율 작업 실행 루프가 다음 작업을 고름, **Then** 이 후보를 `RELEASED`로 억제하고 다음 거시 후보를 선택한다.
2. **Given** released-work에 해당 후보가 없음, **When** 같은 sidecar로 실행함, **Then** 기존처럼 source diversification 후보가 선택되어 완료 마커 누락을 드러낸다.

---

### User Story 3 - 안전 경계와 인계 재현성 유지 (Priority: P3)

운영자는 후보 폐쇄가 자동화를 더 안정적으로 만들되 돈 경로, 주문, 자본, live 전략, 허용 종목, 헌법, 커널, 비밀값을 바꾸지 않기를 원한다.

**Why this priority**: 이 작업은 다음 세션 행동을 바꾸는 등급 2 운영 보정이지만, 실거래 권한이나 안전 경계를 넓히면 안 된다.

**Independent Test**: 변경 산출물과 PR 본문이 위험 등급 2, 돈 경로 `PREVIEW_ONLY`, 안전 경계 변경 없음, 전체 검증 결과를 명시하면 검증된다.

**Acceptance Scenarios**:

1. **Given** source diversification 후보가 완료 처리됨, **When** safety boundary를 확인함, **Then** 주문·브로커·자본·live 전략·허용 종목·비밀값·외부 유료 서비스 변경은 없다.
2. **Given** PR이 머지됨, **When** 다음 세션이 `HANDOFF.md`를 읽음, **Then** 최신 후보와 sidecar 순서 해석을 다시 조사하지 않고 이어갈 수 있다.

### Edge Cases

- 스펙 090 tasks가 미완료면 완료 마커가 있어도 released-work 장부가 후보를 닫지 않아야 한다.
- released-work sidecar가 아직 같은 push 안에서 갱신되지 않았더라도, 저장소 override 재현으로 다음 선택 후보를 확인할 수 있어야 한다.
- source diversification 후보가 아닌 이전 macro 후보의 완료 상태는 기존 released-work 장부 규칙을 그대로 따른다.
- 새 후보 폐쇄는 읽기 전용 장부와 회귀 테스트만 바꾸며 주문, 브로커 API, 자본 배분, live 전략, whitelist/caps, 비밀값, 헌법, 커널, 외부 유료 서비스를 바꾸지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST distinguish the completed source-diversification output candidate from a genuinely new follow-up candidate.
- **FR-002**: System MUST publish an explicit completed candidate marker for `candidate-source-diversification-sidecar-bottleneck`.
- **FR-003**: System MUST let released-work record that candidate only after the owning Speckit tasks are complete.
- **FR-004**: System MUST include a regression test proving that released source-diversification output is not selected as `EXECUTION_READY`.
- **FR-005**: System MUST advance to `candidate-autonomous-growth-objective-calibration` when source diversification output and prior macro bootstrap candidates are complete and no higher-priority repair packet exists.
- **FR-006**: System MUST preserve the existing safety boundary: no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, and no external paid service.
- **FR-007**: System MUST verify focused behavior, released-work reproduction, latest sidecar replay, full tests, lint, HANDOFF fact check, strict harness, and PR quality gate before merge.

### Key Entities *(include if feature involves data)*

- **Source Diversification Output Candidate**: `candidate-source-diversification-sidecar-bottleneck`, the candidate emitted by spec 089 after static candidate saturation.
- **Completion Marker**: Explicit Speckit contract field consumed by released-work to close a completed candidate.
- **Released Work Ledger**: Read-only report that prevents completed candidates from being selected again.
- **Next Macro Candidate**: `candidate-autonomous-growth-objective-calibration`, the follow-up work that should surface after source diversification output is closed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `released_work_probe.py --repo-root .` includes `candidate-source-diversification-sidecar-bottleneck` after this spec's tasks are complete.
- **SC-002**: A focused autonomous work execution test shows released source diversification output is not `EXECUTION_READY`.
- **SC-003**: Latest sidecar replay with repo-root released-work override selects `candidate-autonomous-growth-objective-calibration`.
- **SC-004**: Focused tests, full pytest, ruff, HANDOFF fact check, strict harness, and PR quality gate pass.
- **SC-005**: The final handoff records that this is a grade 2 operating automation closure, not a money-path or safety-perimeter change.

## Assumptions

- 스펙 089의 implementation and merge already satisfied the behavioral work described by `candidate-source-diversification-sidecar-bottleneck`.
- Closing the output candidate through released-work is safer than changing ranking heuristics, because it uses the existing completed-candidate contract.
- The next macro candidate should remain the existing deterministic template `candidate-autonomous-growth-objective-calibration`.
