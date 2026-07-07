# Feature Specification: Broker Diagnostic Liveness Contract

**Feature Branch**: `Codex/105-broker-diagnostic-liveness-contract`
**Created**: 2026-07-08
**Status**: Draft
**Input**: User description: "다음 할 일 `candidate-broker-diagnostic-liveness-contract`를 목표 스킬로 꼼꼼하게 수행"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 브로커 진단 증거 생존성을 분리한다 (Priority: P1)

운영자는 `kis-smoke`, `execution-quality`, `pipeline-liveness`를 손으로 다시 맞춰보지 않고도 브로커 진단 증거가 신선하고 구조적으로 살아 있는지 PASS/WAIT/FAIL 계약 보고서로 본다.

**Why this priority**: 스펙 102의 체결 품질 frontier는 브로커 거부 분류와 체결 비용 기준을 닫았고, 마지막 열린 영역은 브로커 진단 생존성이다. 브로커 진단이 살아 있는지 독립 계약으로 고정하지 않으면 다음 세션이 같은 sidecar 신선도와 smoke 성공 여부를 반복 해석한다.

**Independent Test**: `kis-smoke`가 성공이고 `execution-quality.broker_smoke`가 성공이며 `pipeline-liveness`가 관련 체크를 OK로 보고하면 `CONTRACT_READY`가 된다.

**Acceptance Scenarios**:

1. **Given** KIS smoke가 success/exit 0/key valid이고 execution-quality가 broker smoke 성공을 포함함, **When** 보고서를 생성하면, **Then** 보고서는 `CONTRACT_READY`와 진단 생존 PASS 요약을 제공한다.
2. **Given** 필수 sidecar는 parse 가능하지만 execution-quality 안에 broker smoke 요약이 없음, **When** 보고서를 생성하면, **Then** 보고서는 `OBSERVATION_WAIT`로 두고 cross-surface 진단 관측 대기를 설명한다.

---

### User Story 2 - 죽은 진단과 단순 관측 대기를 구분한다 (Priority: P2)

운영자는 브로커 키, smoke 실패, stale pipeline 같은 실제 진단 장애와, 브로커 진단 블록이 아직 충분히 연결되지 않은 관측 대기를 구분한다.

**Why this priority**: 진단 실패를 관측 대기로 낮춰 보면 실제 브로커 연결 장애를 놓친다. 반대로 살아 있는 증거를 장애로 과장하면 자율 루프가 불필요한 복구 작업으로 튄다.

**Independent Test**: KIS smoke 실패, key invalid, pipeline critical/stale, 필수 입력 결손은 `BLOCKED`가 되고, broker smoke 요약만 빠진 경우는 `OBSERVATION_WAIT`가 된다.

**Acceptance Scenarios**:

1. **Given** `kis-smoke.smoke_state`가 실패이거나 `key_valid=false`, **When** 보고서를 생성하면, **Then** overall status는 `BLOCKED`이고 broker diagnostic gate가 FAIL이다.
2. **Given** `pipeline-liveness`가 KIS smoke 또는 execution-quality를 stale/critical로 표시함, **When** 보고서를 생성하면, **Then** overall status는 `BLOCKED`이고 pipeline gate가 FAIL이다.

---

### User Story 3 - 완료 후보를 닫고 다음 거시 후보로 전진한다 (Priority: P3)

운영자는 `candidate-broker-diagnostic-liveness-contract`가 완료 처리된 뒤 체결 품질 frontier를 반복하지 않고, 자율 루프가 다음 미탐색 거시 영역으로 전진하는지 확인한다.

**Why this priority**: 브로커 진단 생존성은 체결 품질 frontier의 마지막 열린 후보다. 완료 마커가 없거나 전진 규칙이 깨지면 같은 후보를 반복 선택하거나 후보 재생성 흐름이 멈춘다.

**Independent Test**: released-work가 브로커 거부 분류, 체결 비용 기준, 브로커 진단 생존성을 모두 완료로 읽으면 autonomous-work selected_work가 `candidate-agent-ops-frontier-map`으로 전진한다.

**Acceptance Scenarios**:

1. **Given** 세 체결 품질 frontier 후보가 released-work에 있음, **When** autonomous-work 보고서를 생성하면, **Then** execution-quality frontier는 모두 released이고 selected_work는 다음 거시 후보다.
2. **Given** 브로커 진단 생존성 후보가 아직 released-work에 없음, **When** autonomous-work 보고서를 생성하면, **Then** selected_work는 `candidate-broker-diagnostic-liveness-contract`로 남는다.

### Edge Cases

- `kis-smoke` raw 파일은 존재하지만 표 형식 또는 JSON 파싱에 실패하면 `BLOCKED`다.
- `kis-smoke`는 성공이지만 `execution-quality.broker_smoke`가 없으면 `OBSERVATION_WAIT`다.
- `execution-quality.overall_status=OBSERVE`는 브로커 진단 실패가 아니다. 진단 생존성은 smoke와 pipeline 증거로 판단한다.
- `pipeline-liveness`가 전체 OK여도 관련 체크가 없으면 `OBSERVATION_WAIT`다.
- `money-path`가 `PREVIEW_ONLY`인 것은 브로커 진단 생존성과 별개이며 실주문 가능 상태로 해석하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a deterministic broker diagnostic liveness report from existing sidecar snapshots only.
- **FR-002**: System MUST consume `automation/kis-smoke-last-run:LAST_RUN.md`, `automation/execution-quality-last-run:LAST_RUN.md`, `automation/pipeline-liveness-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, and `automation/capital-path-readiness-last-run:capital_path_readiness.json`.
- **FR-003**: System MUST distinguish `CONTRACT_READY`, `OBSERVATION_WAIT`, and `BLOCKED` from quality gates rather than free text.
- **FR-004**: System MUST require successful KIS smoke evidence and successful execution-quality broker smoke evidence before reporting `CONTRACT_READY`.
- **FR-005**: System MUST treat missing execution-quality broker smoke evidence as observation wait when required inputs are otherwise parseable and KIS smoke is healthy.
- **FR-006**: System MUST treat failed KIS smoke, invalid KIS key, nonzero smoke exit, or stale/critical pipeline status for KIS smoke or execution-quality as `BLOCKED`.
- **FR-007**: System MUST include `completed_candidate_id: candidate-broker-diagnostic-liveness-contract` and `next_candidate_id: candidate-agent-ops-frontier-map`.
- **FR-008**: System MUST preserve autonomous-work ordering so released broker diagnostic liveness advances out of the execution-quality frontier.
- **FR-009**: System MUST include safety invariants showing no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel modification, no fresh external collection, and no external paid service.
- **FR-010**: System MUST NOT infer live-money readiness from broker diagnostic liveness.

### Key Entities *(include if feature involves data)*

- **Broker Diagnostic Liveness Report**: The read-only report containing overall status, required evidence surfaces, KIS smoke summary, execution-quality broker smoke summary, pipeline liveness summary, quality gates, completion marker, next candidate, and safety boundary.
- **Broker Diagnostic Summary**: The normalized view of smoke success, key validity, test count, smoke timestamp, execution-quality embedded broker smoke status, and pipeline freshness.
- **Quality Gate**: A PASS/WAIT/FAIL condition for required parseability, KIS smoke health, execution-quality broker smoke presence, pipeline freshness, and safety boundary.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-broker-diagnostic-liveness-contract`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With current remote sidecar evidence, the report returns `CONTRACT_READY` and `diagnostic_state=BROKER_DIAGNOSTIC_LIVE`.
- **SC-002**: With missing execution-quality broker smoke evidence but healthy required inputs, the report returns `OBSERVATION_WAIT`.
- **SC-003**: With failed KIS smoke, invalid key, nonzero smoke exit, missing required input, or stale/critical pipeline evidence, the report returns `BLOCKED` with the failing gate named.
- **SC-004**: Report JSON includes `completed_candidate_id` and `next_candidate_id`, and Markdown includes `## 브로커 진단 생존성 요약`.
- **SC-005**: Focused unit and integration tests for the new probe and autonomous-work advancement pass.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- Current remote `kis-smoke` and `execution-quality.broker_smoke` evidence are successful enough to classify diagnostic liveness as ready.
- Broker diagnostic liveness means the read-only diagnostic evidence is alive; it does not mean real orders can be submitted.
- This feature emits local/probe reports and SDD completion markers; it does not add a new scheduled workflow unless a later automation task explicitly decides to publish the report.

completed_candidate_id: candidate-broker-diagnostic-liveness-contract
