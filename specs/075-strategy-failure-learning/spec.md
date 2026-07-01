# Feature Specification: Strategy Failure Learning

**Feature Branch**: `Codex/075-strategy-failure-learning`  
**Created**: 2026-07-01  
**Status**: Draft  
**Input**: User description: "스펙 074/075 이후 가격 이력 부족이 해소되고 실패로 판정된 전략/포트폴리오 후보 2개가 다시 반복 승격 큐에 올라오지 않도록, 다음 자율 성장 작업을 최신 main 기준으로 정의하고 SDD·구현·검증·PR·머지·배포/sidecar 확인·handoff까지 완료한다. 단, 실제 주문, 실거래 전환, 자본 배분, 브로커 주문 경로, whitelist/caps/live 설정/헌법/커널은 변경하지 않는다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 실패한 전략 후보를 학습 장부에 고정 (Priority: P1)

운영자는 가격 이력 부족이 해소된 뒤 `DISCARD`로 판정된 전략·포트폴리오 후보가 다음 자율 성장 실행에서 다시 새 후보처럼 살아나지 않기를 원한다.

**Why this priority**: 같은 실패를 반복하면 자동 루프가 돈 버는 방향으로 진화하지 못하고 검증 비용만 다시 쓴다.

**Independent Test**: promotion summary에 `DISCARD` 후보 2개가 있을 때 evolution scan이 두 후보를 `rejected` learning ledger entry로 출력하면 독립적으로 검증된다.

**Acceptance Scenarios**:

1. **Given** promotion summary에 `candidate-1ed634d8bf6d`가 `DISCARD`로 기록됨, **When** autonomous evolution scan이 실행됨, **Then** learning ledger에는 같은 후보의 `rejected` entry가 생긴다.
2. **Given** promotion summary에 `candidate-cc96b35062da`가 `DISCARD`로 기록됨, **When** autonomous evolution scan이 실행됨, **Then** learning ledger에는 같은 후보의 실패 사유와 evidence package reference가 남는다.

---

### User Story 2 - 실패 후보 재활성화 차단 (Priority: P2)

운영자는 rejected ledger entry가 있는 후보가 새 증거나 재검토 조건 없이 active candidate backlog에 다시 들어오지 않기를 원한다.

**Why this priority**: 학습 장부는 단순 기록이 아니라 다음 루프의 행동을 바꿔야 한다.

**Independent Test**: 기존 ledger에 `rejected` entry가 있는 후보를 evolution scan에 넣었을 때 candidate backlog의 해당 후보 상태가 `rejected`로 유지되면 검증된다.

**Acceptance Scenarios**:

1. **Given** learning ledger에 재검토 조건 없는 rejected entry가 있음, **When** 같은 후보가 다시 생성됨, **Then** 후보 상태는 `rejected`로 유지된다.
2. **Given** rejected entry에 명시적 재검토 조건이 있음, **When** 같은 후보가 다시 생성됨, **Then** 기존 조건은 보존되고 자동 pass로 승격되지 않는다.

---

### User Story 3 - 자동화 sidecar 소비 경로 보존 (Priority: P3)

운영자는 autonomous evolution workflow가 최신 promotion summary를 읽어 이 학습을 자동으로 수행하되, 주문·브로커·자본 경로를 건드리지 않기를 원한다.

**Why this priority**: 로컬 smoke만 성공하고 서버 루프가 최신 sidecar를 읽지 못하면 다음 세션이 같은 문제를 다시 추적한다.

**Independent Test**: workflow manifest가 `automation/autonomous-promotion-last-run:promotion_summary.json`을 수집하고, workflow safety regression이 브로커·KIS·SSH·live 명령 부재를 확인하면 검증된다.

**Acceptance Scenarios**:

1. **Given** promotion summary sidecar가 존재함, **When** autonomous evolution workflow가 evidence를 수집함, **Then** evolution probe는 해당 JSON을 읽어 rejected ledger entry를 만들 수 있다.
2. **Given** promotion summary sidecar가 누락됨, **When** autonomous evolution workflow가 실행됨, **Then** 기존 후보 발굴은 실패하지 않고 단지 외부 실패 학습을 생략한다.

### Edge Cases

- promotion summary JSON이 깨졌거나 schema가 예상과 다르면 기존 후보 발굴을 유지하고 외부 실패 학습만 생략한다.
- promotion summary에 `DISCARD`가 아닌 `FACTORY_PACKAGE_READY` 후보는 rejected ledger로 쓰지 않는다.
- 이미 같은 후보의 `rejected` entry가 있으면 중복 entry를 만들지 않는다.
- 외부 실패 후보가 현재 evolution candidate 목록에 없어도 ledger entry는 남길 수 있어야 한다.
- 실패 사유에 비밀값처럼 보이는 문자열이 들어오면 기존 secret masking 규칙을 통과해야 한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST collect the latest autonomous promotion summary as read-only evidence for the autonomous evolution loop.
- **FR-002**: System MUST parse `DISCARD` assessments from the promotion summary without requiring broker, order, capital, whitelist, caps, live strategy, or secret access.
- **FR-003**: System MUST add a `rejected` learning ledger entry for every `DISCARD` strategy or portfolio candidate that does not already have the same rejected entry.
- **FR-004**: System MUST preserve the promotion failure reason and a source reference in the learning ledger entry.
- **FR-005**: System MUST keep existing candidate generation working when the promotion summary is missing, stale, or malformed.
- **FR-006**: System MUST continue to keep rejected candidates out of active status unless a recheck condition is explicitly present.
- **FR-007**: System MUST NOT mark failed candidates as passed, forward-ready, canary-ready, or live-ready.
- **FR-008**: System MUST publish the updated learning ledger through the existing autonomous evolution sidecar.

### Key Entities *(include if feature involves data)*

- **Promotion Failure Signal**: A machine-readable record derived from promotion summary assessments with candidate id, title, stage, reason, action, and source reference.
- **Learning Ledger Entry**: Durable candidate-level learning record with decision, reason, optional evidence package reference, optional recheck condition, and created timestamp.
- **Evolution Evidence Surface**: Read-only sidecar input collected before autonomous evolution scan.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With a promotion summary containing two `DISCARD` strategy/portfolio candidates, the evolution scan emits exactly two corresponding `rejected` ledger entries and no duplicate entries.
- **SC-002**: With a missing or malformed promotion summary, the evolution scan still emits candidate backlog and learning ledger artifacts without raising an exception.
- **SC-003**: The autonomous evolution workflow collects the promotion summary sidecar without adding SSH, KIS, broker, order, capital, whitelist, caps, or live strategy commands.
- **SC-004**: Full repository tests and lint pass before merge, including focused evolution loop and workflow regression tests.

## Assumptions

- The autonomous promotion summary is the source of truth for current `DISCARD` stage decisions.
- Candidate ids are stable enough to connect promotion assessments back to evolution candidates and ledger entries.
- This feature is read-only with respect to market data, broker state, capital, and live trading configuration.
- Strategy redesign itself remains a later candidate. This feature only prevents failed candidates from reappearing as if nothing was learned.
