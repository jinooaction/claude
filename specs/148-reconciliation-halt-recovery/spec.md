# Feature Specification: 정합성 중지의 조건부 자동 복구

**Feature Branch**: `Codex/148-reconciliation-halt-recovery`
**Created**: 2026-08-22
**Status**: Complete
**Risk Grade**: 4 - 라이브 주문 가능 상태와 중지 해제 경로를 변경

## User Scenarios & Testing

### User Story 1 - 안전한 무인 복구 (Priority: P1)

운영자는 계좌 정합성 오류로 멈춘 시스템이 최신 브로커 상태와 전략 측정 계약을 다시 확인한 뒤, 문제가 실제로 사라졌을 때만 사람 개입 없이 복구되기를 원한다.

**Independent Test**: 정합성 오류 halt를 만들고 브로커·외부 보유를 일치시키면 새 검사 뒤 halt가 해제되고 주문은 0건이다. 수동·손실 halt 또는 불일치 상태에서는 halt가 그대로 남는다.

**Acceptance Scenarios**:
1. **Given** 정합성 오류로 생긴 halt와 유효한 최신 전략 측정 계약, **When** 새 정합성 검사가 OK이면, **Then** 같은 halt임을 재확인하고 감사 기록을 남긴 뒤 halt를 해제한다.
2. **Given** 수동 중지, 손실 차단, 다른 이유의 halt, **When** 복구기를 실행하면, **Then** 중지를 해제하지 않고 차단 이유를 보고한다.
3. **Given** 정합성 불일치·API 불확실·오래되거나 다른 측정 계약, **When** 복구기를 실행하면, **Then** fail-closed 상태와 주문 0건을 보고한다.

### User Story 2 - 실제 중지 상태를 반영하는 돈 경로 (Priority: P1)

운영자는 돈 경로 보고가 실제 halt를 무시하고 `REAL_ORDER_PATH_ARMED`라고 말하지 않기를 원한다.

**Independent Test**: 최신 복구 보고가 차단·오래됨·누락 중 하나이면 다른 자동매매 증거가 준비돼도 돈 경로는 `BLOCKED`이고 실제 주문 제출 가능성은 false다.

**Acceptance Scenarios**:
1. **Given** halt가 남은 최신 복구 보고, **When** 돈 경로를 계산하면, **Then** 가장 높은 우선순위로 `BLOCKED`를 반환한다.
2. **Given** 최신 복구 보고가 halt 없음과 유효한 정합성 OK를 증명함, **When** 돈 경로를 계산하면, **Then** 기존 자본 사다리와 마이크로 라이브 판정을 계속 적용한다.

### User Story 3 - 배포 뒤 자동 운영 (Priority: P2)

운영자는 배포와 KIS 연결 확인 뒤 고정된 SSH 명령만으로 복구 검사가 자동 실행되고, 결과가 sidecar와 돈 경로에 이어지기를 원한다.

**Independent Test**: 워크플로 정적 검증에서 임의 셸 실행 없이 고정 gateway 명령만 사용하고, 복구 sidecar가 money-path 입력에 포함된다.

## Requirements

- **FR-001**: 복구기는 실행할 때마다 브로커에서 새 정합성 상태를 읽어야 한다.
- **FR-002**: 자동 해제 대상은 이유가 `reconciliation mismatch:`로 시작하는 halt로 제한해야 한다.
- **FR-003**: 최신 정합성 상태가 OK이고 최신 전략 측정 계약이 유효하며 복구 준비도 계약과 일치할 때만 halt를 해제해야 한다.
- **FR-004**: 검사 전후 halt가 바뀌면 해제를 거부해야 한다.
- **FR-005**: 해제와 감사 기록 중 오류가 나면 halt를 복원해야 한다.
- **FR-006**: 복구 결과는 상태, 전후 halt, 정합성, 계약 ID, 이유, 주문 수를 기계 판독 가능한 JSON으로 제공해야 한다.
- **FR-007**: 복구기는 주문·취소·자본 변경을 수행하지 않아야 한다.
- **FR-008**: production 워크플로는 고정된 root 소유 SSH helper만 호출해야 한다.
- **FR-009**: 최신 복구 sidecar가 누락·오래됨·차단·halt 존재이면 돈 경로는 fail-closed 해야 한다.
- **FR-010**: 기존 whitelist, 포지션 한도, 손실 차단, 수동 중지, `Backtest -> Canary -> Full` 단계는 유지해야 한다.

## Success Criteria

- **SC-001**: 모든 수동·손실·알 수 없는 halt 시험에서 자동 해제 횟수는 0건이다.
- **SC-002**: 정합성 OK 성공 경로는 주문 0건으로 halt를 한 번만 해제하고 감사 기록을 남긴다.
- **SC-003**: halt가 있거나 복구 증거가 신선하지 않은 모든 돈 경로 시험은 `can_submit_real_orders=false`다.
- **SC-004**: workflow, SSH gateway, helper, sidecar, money-path가 하나의 자동 실행 경로로 검증된다.
- **SC-005**: 전체 테스트·린트·strict 하네스·HANDOFF 사실 검증·PR 품질 관문이 통과한다.

## Out of Scope

- 손실 차단 또는 운영자가 직접 건 수동 halt의 자동 해제.
- 주문 한도·허용 종목·자본 사다리 완화.
- 복구 실행 자체에서 실제 주문 제출.
