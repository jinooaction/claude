# Feature Specification: Learning Ledger Candidate Memory

**Feature Branch**: `Codex/087-learning-ledger-candidate-memory`
**Created**: 2026-07-03
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-fa66202bf496`를 진행한다. 후보명은 학습 장부로 폐기·보류 후보 재발굴 차단이며, 목표는 장부에 남은 rejected/evidence-dependent/operator-review 결정이 다음 자율 성장 실행에서 같은 후보를 새 작업으로 되살리지 못하게 하는 것이다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 보류 후보를 다시 새 후보로 보지 않음 (Priority: P1)

운영자는 `learning_ledger.json`에 evidence-dependent 또는 deferred로 남은 후보가 다음 자율 성장 실행에서 `new` 후보로 다시 나타나 반복 조사 비용을 만들지 않기를 원한다.

**Why this priority**: 학습 장부가 기록만 하고 행동을 바꾸지 않으면, 후보 공장과 자율 작업 실행 루프가 같은 보류 결론을 반복한다.

**Independent Test**: 기존 ledger에 `candidate-fa66202bf496`의 evidence-dependent entry가 있을 때 evolution scan 결과에서 이 후보가 `safe_high_leverage_work`에 들어가지 않고 보류 상태와 이유를 유지하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** learning ledger에 재검토 조건이 없는 evidence-dependent entry가 있음, **When** 같은 후보가 다시 생성됨, **Then** 후보 상태는 `evidence_dependent`로 유지되고 안전 착수 후보 목록에서 빠진다.
2. **Given** learning ledger entry에 사유와 evidence package reference가 있음, **When** 후보가 억제됨, **Then** 다음 행동 문구는 장부의 사유를 재사용해 다음 세션이 왜 멈췄는지 알 수 있다.

---

### User Story 2 - 운영자 검토 후보를 자동 착수하지 않음 (Priority: P2)

운영자는 이전에 operator-review로 분류된 후보가 명시적 해제 없이 자동 실행 후보로 되살아나지 않기를 원한다.

**Why this priority**: 운영자 검토 상태는 "언젠가 자동 착수"가 아니라 안전·범위 판단이 끝나지 않았다는 의미다.

**Independent Test**: 기존 ledger에 operator_review entry가 있는 후보를 evolution scan에 넣었을 때 후보 상태가 `operator_review`로 유지되고 operator review 목록에 남으면 검증된다.

**Acceptance Scenarios**:

1. **Given** learning ledger에 operator_review entry가 있음, **When** 같은 후보가 다시 생성됨, **Then** 후보는 자동 착수 후보가 아니라 운영자 검토 후보로 표시된다.
2. **Given** ledger entry가 malformed이거나 후보 식별자가 없음, **When** scan이 실행됨, **Then** 기존 후보 발굴은 실패하지 않는다.

---

### User Story 3 - 완료 후보 마커와 인계가 반복을 닫음 (Priority: P3)

운영자는 이 작업 자체가 완료된 뒤 `candidate-fa66202bf496`도 released-work 장부에 들어가 다음 작업 선택에서 반복되지 않기를 원한다.

**Why this priority**: 코드가 보류 후보를 억제해도, 이번 후보 자체가 완료 후보로 소비되지 않으면 다음 세션이 같은 스펙을 다시 시작한다.

**Independent Test**: 작업표가 완료되고 계약 문서에 `completed_candidate_id: candidate-fa66202bf496`가 있을 때 `released_work_probe.py --repo-root .`가 이 후보를 `released`로 출력하면 검증된다.

**Acceptance Scenarios**:

1. **Given** 스펙 087 작업이 완료됨, **When** released-work probe가 저장소를 스캔함, **Then** `candidate-fa66202bf496`가 released 목록에 포함된다.
2. **Given** 변경이 PR 준비 상태임, **When** PR 본문과 HANDOFF를 읽음, **Then** 등급 2 운영 보정, 안전 경계, 검증, 되돌림 의미가 기록되어 있다.

### Edge Cases

- learning ledger JSON이 없거나 깨졌으면 기존 후보 발굴을 유지하고 장부 적용만 생략한다.
- ledger entry가 같은 후보에 여러 개 있으면 마지막으로 읽힌 entry가 해당 후보의 현재 장부 결정을 대표한다.
- `rejected`, `discard`, `evidence_dependent`, `deferred`, `operator_review` 외의 decision은 임의로 억제하지 않는다.
- ledger 사유에 비밀값처럼 보이는 문자열이 들어오면 기존 masking 규칙을 통과해야 한다.
- 이 작업은 주문, 브로커 API, 자본 배분, live 전략, whitelist/caps, 헌법, 커널, 비밀값을 바꾸지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST apply existing learning ledger decisions to generated candidates before computing safe high leverage work.
- **FR-002**: System MUST keep candidates with `rejected` or `discard` ledger decisions out of active status unless the ledger entry is removed or changed by a later run.
- **FR-003**: System MUST keep candidates with `evidence_dependent`, `deferred`, or `observe` ledger decisions out of `safe_high_leverage_work`.
- **FR-004**: System MUST keep candidates with `operator_review` ledger decisions in operator-review status and out of autonomous start status.
- **FR-005**: System MUST preserve ledger reason, evidence package reference, and recheck condition in candidate next-action text when a ledger decision suppresses a candidate.
- **FR-006**: System MUST fail open when the ledger is missing or malformed, preserving current candidate generation.
- **FR-007**: System MUST publish a Speckit contract with an explicit completed-candidate marker for `candidate-fa66202bf496` after implementation tasks are complete.
- **FR-008**: System MUST verify focused unit behavior, released-work reproduction, full tests, lint, HANDOFF fact check, strict harness, and PR quality gate before merge.
- **FR-009**: System MUST keep all safety boundaries unchanged: no broker API, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel change, and no external paid service.

### Key Entities *(include if feature involves data)*

- **Learning Ledger Entry**: Durable candidate-level memory with candidate id, decision, reason, optional evidence package id, optional recheck condition, and created timestamp.
- **Suppressed Candidate**: A generated candidate whose actionability is reduced by a ledger decision.
- **Completed Candidate Marker**: A Speckit contract field consumed by released-work after this feature ships.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With an evidence-dependent ledger entry for `candidate-fa66202bf496`, the evolution summary excludes that candidate from `safe_high_leverage_work`.
- **SC-002**: With an operator-review ledger entry for a generated candidate, the evolution summary includes that candidate in `operator_review` and excludes it from autonomous start.
- **SC-003**: With a missing or malformed ledger, the evolution scan still emits candidates and a learning ledger without raising an exception.
- **SC-004**: `released_work_probe.py --repo-root .` includes `candidate-fa66202bf496` after tasks are checked complete and the explicit contract marker is present.
- **SC-005**: Focused tests, full pytest, ruff, HANDOFF fact check, strict harness, and PR quality gate pass.
- **SC-006**: No changed file belongs to broker order submission, capital ladder authority, whitelist/caps, live strategy switching, secrets, constitution, or kernel manifest.

## Assumptions

- `learning_ledger.json` is the durable memory surface for rejected, evidence-dependent, and operator-review autonomous candidates.
- Ledger decisions are conservative: a prior hold remains non-actionable until a future implementation explicitly changes or removes that ledger decision.
- `released-work` remains the correct surface for completed Speckit candidates, while `learning_ledger` remains the surface for not-yet-released learning decisions.
- This is a grade 2 operating-system change because it affects autonomous candidate selection and next-session behavior, but it does not change the money path.
