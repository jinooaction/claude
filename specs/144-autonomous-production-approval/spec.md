# Feature Specification: Autonomous Production Approval

**Feature Branch**: `Codex/144-autonomous-production-approval`  
**Created**: 2026-08-16  
**Status**: In Progress  
**Input**: 운영자가 실제 주문까지 남은 사람 승인을 모두 자동화하라고 명시적으로 지시함.

## User Scenarios & Testing

### User Story 1 - 사람 없는 예약 주문 승인 (Priority: P1)

운영자는 평일 예약 실행이 시작될 때 GitHub 승인 버튼을 누르지 않아도, 기존 자본·시간·위험
증거가 모두 맞으면 시스템이 스스로 production 주문 관문까지 진행하기를 원한다.

**Why this priority**: 현재 `production` 필수 검토자가 유일한 사람 의존점이며, 승인 지연은 정규장
주문 기회를 놓치게 한다.

**Independent Test**: `main`의 예약 실행이 별도 기계 승인 작업을 통과하고 사람 승인 대기 없이
환경 전용 서명키를 사용하되, 잘못된 이벤트·브랜치·무장·자본은 서명 전에 거부된다.

**Acceptance Scenarios**:

1. **Given** `main`, 예약 이벤트, `armed:true`, 유효 자본, **When** 기계 승인 작업이 실행됨,
   **Then** `scheduled-real-order` 결정을 내리고 production 서명 작업을 허용한다.
2. **Given** push 또는 `main`이 아닌 ref, **When** 승인 작업이 평가함, **Then** 실제 주문 서명 전에 거부한다.
3. **Given** 수동 실행, **When** 기계 승인이 통과함, **Then** 서명·서버 권위만 검증하고 주문은 0건이다.

---

### User Story 2 - 자동화 상태를 정직하게 표시 (Priority: P2)

운영자는 돈 경로 보고서에서 더 이상 사람 승인이 필요하다고 오해하지 않고, 남은 자동 관문과 다음
예약 시각을 바로 확인하기를 원한다.

**Independent Test**: `REAL_ORDER_PATH_ARMED` 상태의 필수 관문과 설명이 `production machine
authorization`을 표시하고 사람 승인 문구를 포함하지 않는다.

**Acceptance Scenarios**:

1. **Given** 자본 사다리 경로가 무장됨, **When** money-path를 생성함, **Then** 사람 승인 대신
   production 기계 승인과 기존 정규장·현금·손실·K1/K2 관문을 표시한다.

### Edge Cases

- GitHub 환경 비밀값이 없으면 서명 단계가 실패 폐쇄한다.
- 필수 검토자가 다시 설정되면 주문은 승인 대기 상태가 되어 자동 진행하지 못하며 운영 상태 점검에서 드러나야 한다.
- 수동 실행과 예약 실행은 같은 동시성 그룹에서 겹치지 않는다.
- 예약 실행이라도 서버 배포 SHA, 서명, 만료, nonce, 센티넬, rung, NAV가 다르면 주문 CLI를 호출하지 않는다.

## Requirements

### Functional Requirements

- **FR-001**: 실제 주문 전 별도 기계 승인 작업이 `main`, 허용 이벤트, 무장, 자본 가드 증거를 검증해야 한다.
- **FR-002**: 실제 주문은 `schedule`, 주문 없는 사전점검은 `workflow_dispatch`로만 분기해야 한다.
- **FR-003**: production 환경은 유지하고 `LIVE_ORDER_SIGNING_KEY`는 환경 비밀값에만 남겨야 한다.
- **FR-004**: production 환경의 사람 required reviewer는 제거하되 배포 branch policy는 `main`만 유지해야 한다.
- **FR-005**: 실제 주문 작업은 기계 승인 성공 결과 없이는 실행되지 않아야 한다.
- **FR-006**: K1 한도, K2 허용 목록, 정규장, 현금 1% 여유, 손실 서킷 브레이커, 단계 자본 한도를 변경하지 않는다.
- **FR-007**: 서버의 Ed25519 서명·10분 만료·nonce 1회성·센티넬·rung·NAV·배포 SHA 재검증을 유지한다.
- **FR-008**: 수동 `workflow_dispatch`는 주문 CLI를 호출하지 않고 주문 0건으로 끝나야 한다.
- **FR-009**: sidecar와 money-path는 사람 승인 대신 기계 승인 상태를 표시해야 한다.
- **FR-010**: 외부 환경 설정 변경은 API 재조회와 주문 없는 production 사전점검으로 검증해야 한다.
- **FR-011**: 되돌림은 production 환경에 required reviewer를 다시 추가하는 것으로 즉시 가능해야 한다.

### Key Entities

- **Autonomous Approval Decision**: 이벤트, ref, 무장, 자본, 실행 종류와 승인 결과.
- **Production Environment Policy**: 환경 전용 비밀값, main-only branch policy, required reviewer 0명.
- **Signed Live Order Request**: 저장소, 워크플로, run, commit, 자본, 만료, nonce와 Ed25519 서명.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 수동 production 사전점검이 사람 승인 대기 없이 완료되고 주문 0건을 확인한다.
- **SC-002**: 예약 주문 경로가 기계 승인 성공에 의존하며 push와 main 외 ref는 주문 서명 전에 차단된다.
- **SC-003**: GitHub API에서 required reviewer 0명과 `main` 단일 branch policy가 확인된다.
- **SC-004**: 환경 개인키는 저장소·sidecar·로그에 노출되지 않는다.
- **SC-005**: 전체 pytest, ruff, 셸·YAML·diff, 엄격 하네스, HANDOFF 사실, PR 품질 관문을 통과한다.

## Assumptions

- 운영자의 이번 명시 지시는 X.4의 기존 자율 자본 위임 아래 사람 승인 단계를 기계 증거로 대체할 권한을 제공한다.
- 다음 예약 시각은 시장·GitHub 스케줄에 따라 달라질 수 있으며 수익이나 체결은 보장하지 않는다.
- GitHub production 환경과 환경 전용 비밀값은 이미 정상이며, required reviewer만 제거할 수 있다.

