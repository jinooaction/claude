# Feature Specification: Broker Rejection Taxonomy Contract

**Feature Branch**: `Codex/103-broker-rejection-taxonomy-contract`
**Created**: 2026-07-07
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-broker-rejection-taxonomy-contract`를 목표 스킬로 꼼꼼하게 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 브로커 거부 원인을 분류한다 (Priority: P1)

운영자는 `execution-quality`, `rebalance-micro-gtaa`, `kis-smoke` 증거를 손으로 다시 읽지 않고도, 최근 브로커 거부가 어떤 원인군에 속하고 재발 가능성이 어떤지 구조화된 계약 보고서로 본다.

**Why this priority**: 스펙 102는 체결 품질 frontier에서 첫 후보를 `candidate-broker-rejection-taxonomy-contract`로 열었다. 현재 증거는 KIS 오류 코드와 거부 주문 수를 보여주지만, 원인군·재발 기준·다음 후보 전진 가능성을 독립 계약으로 닫지 않으면 다음 세션이 같은 sidecar를 다시 해석해야 한다.

**Independent Test**: `APBK1672` 거부 2건, KIS smoke 성공, micro GTAA `latest_intent_loss` 입력으로 보고서를 생성하면 원인군, 재발 위험, 관측 신뢰도, 주문 재시도 금지 안전 경계가 JSON과 Markdown에 나타난다.

**Acceptance Scenarios**:

1. **Given** `execution-quality`에 KIS 코드별 거부 요약이 있고 `kis-smoke`가 성공인 상태, **When** 브로커 거부 분류 보고서를 생성하면, **Then** 보고서는 KIS 코드별 taxonomy row와 "브로커 연결 장애가 아니라 주문 응답 거부 관측"이라는 분류를 제공한다.
2. **Given** `rebalance-micro-gtaa` live gate가 `latest_intent_loss`로 실주문을 막는 상태, **When** 보고서를 생성하면, **Then** 보고서는 자동 주문 재시도나 자본 변경을 권하지 않고 관측·전략 검토 대기를 다음 행동으로 남긴다.

---

### User Story 2 - 증거 결손을 PASS/WAIT/FAIL로 분리한다 (Priority: P2)

운영자는 거부 분류가 준비됐는지, 더 관측해야 하는지, 입력 증거가 깨져 계약을 막는지 명확히 구분한다.

**Why this priority**: 브로커 거부 표본은 적고 sidecar는 비동기로 갱신된다. 결손 입력을 성공으로 착각하면 실행 품질 판단을 과신하고, 반대로 정상적인 표본 부족을 장애로 보면 자율 루프가 불필요하게 멈춘다.

**Independent Test**: 필수 입력이 정상인 경우 `CONTRACT_READY`, 거부 주문이 없는 경우 `OBSERVATION_WAIT`, `execution-quality`가 없거나 malformed인 경우 `BLOCKED`가 되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 필수 sidecar가 모두 parse 가능하고 거부 코드가 관측됨, **When** 보고서를 생성하면, **Then** 모든 필수 gate는 PASS이고 overall status는 `CONTRACT_READY`다.
2. **Given** `execution-quality`가 없거나 결정 JSON이 깨짐, **When** 보고서를 생성하면, **Then** overall status는 `BLOCKED`이고 누락·파싱 실패한 입력이 evidence surface에 남는다.
3. **Given** 거부 주문이 아직 없음, **When** 보고서를 생성하면, **Then** overall status는 `OBSERVATION_WAIT`이고 "거부 표본 대기"로 분류한다.

---

### User Story 3 - 완료 후보를 닫고 다음 체결 품질 후보로 전진한다 (Priority: P3)

운영자는 `candidate-broker-rejection-taxonomy-contract`가 완료 처리된 뒤 같은 후보를 다시 받지 않고, 다음 체결 품질 후보인 `candidate-execution-cost-basis-contract`로 전진한 자율 work packet을 받는다.

**Why this priority**: 계약 보고서만 만들어도 released-work 완료 마커가 없으면 자율 루프는 같은 후보를 반복 선택한다. 스펙 102가 만든 체결 품질 frontier 순서를 실제로 소비해야 한다.

**Independent Test**: released-work가 `candidate-broker-rejection-taxonomy-contract` 완료를 읽으면 autonomous-work selected_work가 `candidate-execution-cost-basis-contract`로 전진하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 스펙 102와 브로커 거부 분류 후보가 released-work에 있음, **When** autonomous-work 보고서를 생성하면, **Then** selected_work는 `candidate-execution-cost-basis-contract`이고 브로커 거부 taxonomy frontier row는 released 상태다.
2. **Given** 브로커 거부 분류 후보만 완료되고 체결 비용 기준 후보는 미완료임, **When** 보고서를 생성하면, **Then** 체결 품질 frontier는 비용 기준 후보를 open 상태로 유지한다.

### Edge Cases

- `execution-quality`는 parse 가능하지만 `broker_rejections`가 비어 있으면 분류 계약은 실패가 아니라 관측 대기로 둔다.
- `kis-smoke`가 실패하거나 누락되면 브로커 연결 생존성 의심을 별도 gate로 WAIT/FAIL 처리하지만 주문 재시도는 제안하지 않는다.
- KIS code가 알려진 taxonomy 사전에 없으면 `unknown_broker_response`로 분류하고 원문 코드는 마스킹된 집계값으로만 남긴다.
- `rebalance-micro-gtaa`가 `latest_intent_loss`를 보고하면 분류 결과와 별개로 live 주문 재시도는 금지된 다음 행동으로 남긴다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a deterministic broker rejection taxonomy report from existing sidecar snapshots only.
- **FR-002**: System MUST consume `automation/execution-quality-last-run:LAST_RUN.md`, `automation/kis-smoke-last-run:LAST_RUN.md`, `automation/rebalance-micro-gtaa-last-run:LAST_RUN.md`, `automation/pipeline-liveness-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, and `automation/capital-path-readiness-last-run:capital_path_readiness.json`.
- **FR-003**: System MUST classify each observed KIS message code into a stable taxonomy key, confidence level, recurrence risk, and action category.
- **FR-004**: System MUST distinguish `CONTRACT_READY`, `OBSERVATION_WAIT`, and `BLOCKED` from quality gates rather than free text.
- **FR-005**: System MUST include `completed_candidate_id: candidate-broker-rejection-taxonomy-contract` and `next_candidate_id: candidate-execution-cost-basis-contract`.
- **FR-006**: System MUST preserve the existing autonomous-work ordering so released broker rejection taxonomy advances to `candidate-execution-cost-basis-contract`.
- **FR-007**: System MUST include safety invariants showing no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel modification, and no external paid service.
- **FR-008**: System MUST NOT infer full broker availability from rejected-order rows; the classification scope is only the observed rejected-order evidence.

### Key Entities *(include if feature involves data)*

- **Broker Rejection Taxonomy Report**: The read-only report containing overall status, evidence surfaces, taxonomy rows, live intent context, quality gates, completion marker, next candidate, and safety boundary.
- **Broker Rejection Class**: A stable classification for a KIS message code or broker rejection signature, including count, confidence, recurrence risk, and action category.
- **Quality Gate**: A PASS/WAIT/FAIL condition for parseability, rejected-order evidence, KIS smoke health, live intent gate context, and safety boundary.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-broker-rejection-taxonomy-contract`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With current execution-quality evidence (`APBK1672` 2건, KIS smoke success, latest intent loss), the report returns `CONTRACT_READY` and at least one taxonomy row.
- **SC-002**: Missing or malformed `execution-quality` evidence returns `BLOCKED` with a failing parse/evidence gate.
- **SC-003**: No rejected orders returns `OBSERVATION_WAIT` without suggesting order retry, capital change, or live strategy change.
- **SC-004**: Report JSON includes `completed_candidate_id` and `next_candidate_id`, and Markdown includes `## 브로커 거부 분류`.
- **SC-005**: Focused unit and integration tests for the new probe and autonomous-work advancement pass.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- The current `APBK1672` evidence is treated as an observed KIS order response rejection signature, not as proof of whole-broker outage.
- KIS smoke success means broker connectivity and credentials were healthy at the smoke timestamp; it does not prove rejected orders would now be accepted.
- The micro GTAA `latest_intent_loss` gate continues to block live order attempts unless a separate future safety-approved change re-arms it.
- This feature emits local/probe reports and SDD completion markers; it does not add a new scheduled workflow unless a later automation task explicitly decides to publish the report.
