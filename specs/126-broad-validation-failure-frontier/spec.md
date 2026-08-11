# Feature Specification: Broad Validation Failure Frontier

**Feature Branch**: `codex/broad-validation-failure-frontier`  
**Created**: 2026-08-11  
**Status**: Complete  
**Input**: User description: "검토 범위가 너무 갇혀 있다. 수단과 방법을 가리지 말고 다각도로 폭넓게 사고하라." Current autonomous-work selected `candidate-broad-frontier-expansion-validation-failures-22f38b8629eb`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 검증 실패 parent 뒤에 기다리지 않고 전진한다 (Priority: P1)

운영자는 막힌 검증 패키지 2개가 남아 있는 상태에서 `candidate-broad-frontier-expansion-validation-failures-22f38b8629eb`가 완료되면, 자동 작업 루프가 `wait-for-fresh-evidence`로 멈추지 않고 구체적인 no-live 검증 후보로 넘어가기를 원한다.

**Why this priority**: 지금 문제는 “엣지가 없다” 하나가 아니라, 실패한 검증 패키지를 다음 탐색의 재료로 쓰지 못하면 같은 결론만 반복한다는 점이다.

**Independent Test**: released-work에 parent 후보가 들어 있고 retryable `execution_failed` 패키지 2개가 남아 있는 fixture에서 autonomous-work 선택 후보가 `candidate-broad-validation-failure-command-replay-contract`인지 확인한다.

**Acceptance Scenarios**:

1. **Given** 검증 실패 parent 후보가 아직 released-work에 없음, **When** 자동 작업 보고서를 만들면, **Then** 기존 parent 후보가 `EXECUTION_READY`로 발행된다.
2. **Given** 같은 parent 후보가 released-work에 있음, **When** 같은 검증 실패 증거를 다시 읽으면, **Then** `wait-for-fresh-evidence`가 아니라 검증 명령 재현 후보가 발행된다.

---

### User Story 2 - 실패를 여러 관점의 frontier 지도로 분리한다 (Priority: P2)

운영자는 `execution_failed`를 한 줄짜리 실패로 보지 않고, 명령 재현, 데이터 준비도, 전략·포트폴리오 패키지 분리, 승격 재검토 조건으로 나눠서 다음 일을 보고 싶다.

**Why this priority**: 같은 실패도 원인이 명령 계약인지, 데이터 history 준비인지, 후보 패키지 구조인지, 억제 기억인지에 따라 다음 행동이 달라진다.

**Independent Test**: 자동 작업 JSON과 Markdown에 `broad_validation_failure_frontier_map`과 `검증 실패 frontier 지도`가 안정적인 순서로 렌더링되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** strategy backtest와 portfolio backtest 패키지가 모두 `execution_failed`로 blocked임, **When** 보고서를 만들면, **Then** 네 개의 검증 실패 frontier 행이 package count와 검토 축을 포함한다.
2. **Given** 첫 frontier 후보가 released-work에 있음, **When** 보고서를 다시 만들면, **Then** 다음 frontier 후보인 데이터 준비도 계약으로 전진한다.

---

### User Story 3 - 돈 안전 경계는 넓히지 않는다 (Priority: P3)

운영자는 검토 범위는 넓히되, 실주문·live 재무장·자본 배분·비밀값·whitelist/caps는 절대 열지 않는다는 점을 보고서와 후보에 남기고 싶다.

**Why this priority**: “수단과 방법을 가리지 말라”는 실행력 요구이지, 안전 경계를 깨라는 뜻이 아니다. 등급 4 돈 경로 실행은 별도 명시 승인 없이는 금지다.

**Independent Test**: 새로 발행되는 검증 실패 frontier 후보의 safety boundary에 브로커 API 호출 금지, 실제 주문 금지, live 재무장 금지, 자본 배분 금지가 포함되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** money-path가 `PREVIEW_ONLY`이고 edge-autoarm이 `WAIT_EDGE`임, **When** 검증 실패 frontier 후보가 발행되면, **Then** 후보 사유는 no-live 검증 설계만 허용한다고 설명한다.
2. **Given** 같은 입력에 blocked 패키지가 없음, **When** 보고서를 만들면, **Then** 검증 실패 frontier 후보를 억지로 만들지 않는다.

### Edge Cases

- parent 후보가 released-work에 없으면 세부 frontier 후보보다 parent 후보를 먼저 발행한다.
- retryable blocked package가 없으면 검증 실패 frontier 후보를 발행하지 않는다.
- 첫 세부 후보가 released-work에 있으면 다음 미완료 세부 후보로 이동한다.
- 모든 세부 후보가 released-work에 있으면 같은 실패 지문을 반복하지 않고 기존 대기 규칙으로 돌아간다.
- money-path와 edge-autoarm이 live 가능 상태가 아니어도 no-live 진단 후보는 만들 수 있지만, 실주문 가능으로 표시하면 안 된다.
- 헌법, 커널, 주문 라우팅, capital ladder, auto-reassign gate, live config, broker integration, secrets, whitelist/caps는 이번 범위 밖이다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a deterministic `broad_validation_failure_frontier_map` in autonomous-work JSON output.
- **FR-002**: System MUST render a `검증 실패 frontier 지도` Markdown section with stable row ordering.
- **FR-003**: System MUST include at least four validation-failure frontier entries: command replay, data readiness, package-kind expansion, and promotion recheck.
- **FR-004**: System MUST mark each frontier entry with `coverage_status`, recommended candidate id, package count, retryable count, failure codes, package kinds, review axes, and required inputs.
- **FR-005**: System MUST emit `candidate-broad-validation-failure-command-replay-contract` when a broad validation-failure parent candidate is released and retryable blocked validation packages remain.
- **FR-006**: System MUST advance to the next unreleased validation-failure frontier entry when an earlier entry is recorded in released-work.
- **FR-007**: System MUST preserve blocked package refs and validation failure groups on the emitted work packet.
- **FR-008**: System MUST NOT emit a validation-failure frontier packet before the broad validation-failure parent candidate is recorded in released-work.
- **FR-009**: System MUST NOT emit a validation-failure frontier packet when no retryable blocked validation package remains.
- **FR-010**: System MUST preserve the no-live safety boundary: no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no paid external service.
- **FR-011**: System MUST mark this work's completed candidate as `candidate-broad-frontier-expansion-validation-failures-22f38b8629eb`.
- **FR-012**: System MUST NOT modify constitution, kernel, order routing, capital ladder, auto-reassign gates, live config, broker integrations, secrets, whitelist/caps, or deployment guard behavior.

### Key Entities *(include if feature involves data)*

- **Broad Validation Failure Frontier Map**: A deterministic list of next no-live validation candidates generated after the broad validation-failure parent is released.
- **Frontier Entry**: One map row with label, coverage status, package counts, recommended candidate, review axes, reason, and next action.
- **Blocked Package Ref**: Existing candidate-result evidence that identifies the candidate, package, package kind, diagnostic codes, next safe action, and source reference.
- **Validation Failure Group**: Existing grouped diagnostic summary such as `execution_failed` with retryable package count and safe next actions.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-broad-frontier-expansion-validation-failures-22f38b8629eb`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Focused autonomous-work tests pass and prove parent release advances to `candidate-broad-validation-failure-command-replay-contract`.
- **SC-002**: Focused tests prove the validation-failure map is deterministic and rendered in Markdown.
- **SC-003**: Focused tests prove releasing the command replay entry advances to `candidate-broad-validation-failure-data-readiness-contract`.
- **SC-004**: Safety boundary strings for the emitted work packet include no broker API call, no orders, no capital allocation, and no live strategy change.
- **SC-005**: Local autonomous-work replay with current sidecars and repo-root released-work scan selects the command replay contract after this spec marker is scanned.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- Current sidecar truth is authoritative: money-path remains `PREVIEW_ONLY` / `NO_EDGE_YET`, edge-autoarm remains `WAIT_EDGE` / `NO_EDGE`, and two retryable blocked validation packages remain visible.
- The broad validation-failure parent id is stable for the current package/diagnostic fingerprint: `candidate-broad-frontier-expansion-validation-failures-22f38b8629eb`.
- This feature is risk grade 2 because it changes autonomous work selection and reporting, while leaving all money-path and safety-perimeter controls unchanged.
