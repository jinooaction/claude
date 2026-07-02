# Feature Specification: 자율 루프 품질 폐쇄

**Feature Branch**: `Codex/081-autonomous-loop-world-class`  
**Created**: 2026-07-02  
**Status**: Draft  
**Input**: User description: "남은 흠 모두 세계 최고 수준으로 개선하고 싶어"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 다음 세션이 바로 착수한다 (Priority: P1)

운영자는 자율 작업 실행 루프가 고른 후보를 다시 해석하지 않고, 다음 Codex 세션이 안전 범위 안에서 바로 작업을 시작할 수 있기를 원한다.

**Why this priority**: 현재 루프는 다음 후보를 고르지만, "이 후보를 어떻게 착수해도 되는가"를 별도 판단해야 한다. 세계 최고 수준에 가까워지려면 자동 주문이나 자동 코드 수정이 아니라, 안전한 후보에 대해 작업 착수 계약과 완료 관문이 기계 판독 가능해야 한다.

**Independent Test**: 최신 sidecar를 입력으로 자율 작업 실행 보고를 만들면 선택된 후보에 자율 착수 수준, 착수 설명, 완료 관문, 필요한 입력이 함께 표시된다.

**Acceptance Scenarios**:

1. **Given** 위험 등급 2 이하의 안전 후보가 선택됨, **When** 자율 작업 실행 보고가 생성됨, **Then** 후보는 운영자 추가 질문 없이 Codex 작업 절차로 시작 가능한 상태로 표시된다.
2. **Given** 후보가 주문, 자본, 비밀값, 헌법, live 전략, 유료 서비스 표면을 건드림, **When** 자율 작업 실행 보고가 생성됨, **Then** 후보는 운영자 승인 필요로 남고 자동 착수로 표시되지 않는다.

---

### User Story 2 - 관측 시점 차이를 혼동하지 않는다 (Priority: P1)

운영자는 돈 경로 보고에서 `14/20`과 `15/20`처럼 숫자가 함께 보일 때 장애인지 정상 실행 시점 차이인지 즉시 구분하길 원한다.

**Why this priority**: 오래된 sidecar를 최신 판단으로 읽는 문제는 반복된 운영 혼동의 원인이었다. 같은 결론 안의 숫자 차이가 정상 시점 차이라면 그것을 별도 정보로 드러내야 하고, 실제 게이트 불일치라면 빨리 막아야 한다.

**Independent Test**: money-path와 edge-autoarm의 관측 수가 다르지만 둘 다 관측 부족 대기라면 보고는 `ALIGNED_WAITING`을 유지하면서 `SNAPSHOT_SKEW` 또는 동등한 정보성 이슈로 시점 차이를 표시한다.

**Acceptance Scenarios**:

1. **Given** money-path는 `14/20`, edge-autoarm은 `15/20`을 보고함, **When** 돈 경로 정렬 보고가 생성됨, **Then** 관측 범위가 `14-15/20`처럼 표시되고 안전 판단은 대기로 유지된다.
2. **Given** money-path와 capital-path-readiness가 서로 다른 live 상태를 보고함, **When** 돈 경로 정렬 보고가 생성됨, **Then** 정보성 시점 차이가 아니라 `MISALIGNED`로 표시된다.

---

### User Story 3 - 상태판 뒤 생존 감시가 따라온다 (Priority: P2)

운영자는 operator-status가 새로 발행된 뒤 pipeline-liveness가 오래된 "미발행 예정" 상태를 남기지 않기를 원한다.

**Why this priority**: 상태판 자체가 정상이어도 생존 감시 sidecar가 직전 순서를 보고 있으면 다음 세션은 불필요하게 다시 확인한다. 보고 루프가 끝난 뒤 감시 루프가 한 번 더 실행되면 현재 상태가 하나의 진입점에 모인다.

**Independent Test**: operator-status 워크플로 완료 이벤트가 pipeline-liveness 워크플로를 다시 실행하도록 구성되어, operator-status sidecar 발행 후 생존 감시가 최신 sidecar를 읽을 수 있다.

**Acceptance Scenarios**:

1. **Given** operator-status workflow가 완료됨, **When** GitHub Actions가 후속 트리거를 평가함, **Then** pipeline-liveness workflow가 다시 실행될 수 있다.
2. **Given** operator-status sidecar가 신선함, **When** pipeline-liveness를 현재 sidecar 입력으로 재현함, **Then** operator-status는 `PENDING`이 아니라 `OK`로 평가된다.

### Edge Cases

- 최신 sidecar와 직전 sidecar가 서로 다른 commit에서 생성될 수 있다.
- 관측 수는 다르지만 live 상태와 게이트 결론은 같을 수 있다.
- operator-status 알림 비밀값이 없거나 전송이 실패해도 상태판과 생존 감시 발행은 계속되어야 한다.
- 안전 후보라도 실제 주문, 자본 배분, live 전략 교체, 헌법·커널 변경, 외부 비용 발생은 자동 착수 대상이 아니다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add an explicit Codex execution contract to each selected work packet, including autonomy level, start guidance, completion gates, required inputs, and safety boundary.
- **FR-002**: System MUST classify risk grade 2 or lower candidates without safety-boundary impact as safe for Codex autonomous start, not as automatic code execution.
- **FR-003**: System MUST classify risk grade 3 or higher, money-path, safety-boundary, secret, kernel, live-strategy, and paid-service candidates as operator approval required.
- **FR-004**: System MUST preserve the invariant that the loop does not create branches, edit code, open PRs, merge, place orders, allocate capital, or call broker APIs by itself.
- **FR-005**: System MUST detect observation-count skew across money-path, edge-autoarm, and forward sidecars when the conclusion remains aligned waiting.
- **FR-006**: System MUST report observation-count skew as informational provenance, not as a money-path blocker, when all involved gates still agree on observation waiting.
- **FR-007**: System MUST continue to report true live-state, stage, blocker, or malformed sidecar disagreements as blocked or misaligned.
- **FR-008**: System MUST ensure pipeline-liveness can rerun after operator-status completes so the latest operator-status sidecar is visible to the next session.
- **FR-009**: System MUST keep all new reports Korean-first while preserving code identifiers and sidecar names.
- **FR-010**: System MUST add regression tests for execution contracts, observation skew reporting, and workflow trigger wiring.

### Key Entities

- **Codex Execution Contract**: Work-packet fields that explain whether Codex may start autonomously, what to read first, and which validation gates close the work.
- **Observation Snapshot Skew**: A non-blocking provenance item showing that different sidecars were produced at different moments while still agreeing on the same waiting state.
- **Post-Status Liveness Refresh**: A workflow trigger that lets pipeline-liveness rerun after operator-status completes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new session can identify the selected candidate, autonomous-start status, required inputs, and completion gates from one JSON report in under five minutes.
- **SC-002**: 100% of candidates touching orders, capital, whitelists, caps, live strategies, secrets, kernel, constitution, or paid services remain outside autonomous-start status.
- **SC-003**: A money-path report with `14/20` and `15/20` aligned-waiting inputs exposes the count range and remains non-blocking.
- **SC-004**: The workflow definition contains a post-operator-status trigger for pipeline-liveness.
- **SC-005**: Focused tests for the three repaired flaws pass, and full test, lint, handoff fact check, strict harness, and PR quality checks pass before merge.

## Assumptions

- "세계 최고 수준" means fewer repeated interpretations, clearer safety boundaries, stronger provenance, and faster safe handoff, not automatic live-money authority.
- Existing Codex PR, validation, and auto-merge policy remains the only path for code changes.
- Existing sidecar branches remain the system of record for loop state.
