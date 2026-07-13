# Feature Specification: Atomic Fill Ledger

**Feature Branch**: `Codex/113-atomic-fill-ledger`
**Created**: 2026-07-13
**Status**: Draft
**Input**: User description: "남은 위험도 해결할까?"

## Problem Statement

라이브 체결 동기화는 브로커가 확인한 체결을 `audit_log`, `fills`, `current_positions`, `orders` 상태에 반영한다. 현재 적용 순서는 감사 이벤트 기록, `fills INSERT OR IGNORE`, 포지션 캐시 갱신, 주문 상태 전이다. 연결은 autocommit이므로 이 작업들이 하나의 원자적 단위가 아니다.

이 구조에서는 프로세스가 중간에 죽거나 같은 체결이 다시 계획될 때 다음 문제가 생길 수 있다.

- `FILL` 감사 이벤트는 남았지만 `fills` 원장이나 포지션 캐시가 갱신되지 않음
- `fills` 중복 삽입은 무시됐는데 포지션 캐시는 다시 증가함
- 포지션 캐시는 갱신됐지만 주문 상태 전이가 실패해 원장과 상태가 서로 다른 사실을 말함

이 스펙은 체결 적용을 하나의 데이터베이스 트랜잭션으로 묶는다. **새 체결 row가 실제로 삽입된 경우에만 감사 이벤트와 포지션 캐시를 갱신하고, 체결 적용 중 어떤 단계라도 실패하면 해당 체결·감사·캐시·상태 변경을 함께 롤백한다.**

## Operator Authorization Boundary

이 작업은 돈 경로의 회계 정확성을 바꾸므로 위험 등급 4로 다룬다. 다만 승인 범위는 코드·테스트·문서의 안전화 변경뿐이다.

허용 범위:

- 체결 적용 계획을 `BEGIN IMMEDIATE` 트랜잭션으로 감싸기
- `fills` 중복 row가 무시되면 `FILL` 감사와 포지션 캐시를 갱신하지 않기
- 체결·감사·포지션·주문 상태 전이가 함께 커밋되거나 함께 롤백되도록 테스트 추가
- 읽기 전용 체결 동기화 테스트와 인계 문서 보강

금지 범위:

- 실제 주문 제출 또는 취소
- `armed: true` 변경
- 실거래 모드 전환
- 자본 배분, 허용 종목, 포지션 한도, 손실 예산 확대
- 운영 서버 또는 KIS 계좌 조회
- `SUBMISSION_UNKNOWN` 자동 복구, 계좌 노출 예약, 단일 실행 권한의 동시 구현

## User Scenarios & Testing

### User Story 1 - 체결 적용은 하나의 원자적 단위다 (Priority: P1)

운영자는 체결 동기화가 중간에 실패해도 `fills`, `audit_log`, `current_positions`, 주문 상태가 서로 다른 사실을 말하지 않는다고 믿을 수 있어야 한다.

**Why this priority**: 체결 원장과 포지션 캐시가 갈라지면 이후 위험 한도, 성과, 재조정, 정합성 검사 모두 오염된다.

**Independent Test**: 포지션 캐시 갱신 단계에서 예외를 강제로 발생시키면 새 `fills` row와 `FILL` 감사 이벤트가 모두 롤백된다.

**Acceptance Scenarios**:

1. **Given** 새 체결 적용 중 포지션 캐시 갱신이 실패함, **When** 체결 계획을 적용하면, **Then** `fills`, `audit_log`, `current_positions`, 주문 상태는 적용 전 상태로 남는다.
2. **Given** 새 체결과 상태 전이가 같은 계획에 있음, **When** 계획 적용이 성공하면, **Then** 체결 row, 감사 row, 포지션 캐시, 주문 상태가 모두 함께 반영된다.

---

### User Story 2 - 중복 체결은 캐시를 다시 움직이지 않는다 (Priority: P1)

운영자는 같은 KIS 체결 식별자가 다시 들어와도 포지션 수량과 평균 단가가 두 번 반영되지 않는다고 확인할 수 있어야 한다.

**Why this priority**: 현재 `INSERT OR IGNORE`는 중복 원장 row만 막고, 이후 캐시 갱신은 막지 못할 수 있다.

**Independent Test**: 이미 존재하는 `kis_fill_id`를 포함한 체결 계획을 적용해도 `fills_applied=0`, 새 `FILL` 감사 0건, 포지션 수량 불변이다.

**Acceptance Scenarios**:

1. **Given** `fills.kis_fill_id`가 이미 존재함, **When** 같은 체결 계획을 다시 적용하면, **Then** `current_positions.qty`는 변하지 않는다.
2. **Given** 중복 체결과 주문 상태 전이가 같은 계획에 있음, **When** 계획을 적용하면, **Then** 중복 체결은 건너뛰고 상태 전이는 기존 규칙대로 한 번만 처리된다.

---

### User Story 3 - 기존 체결 동기화 동작은 유지된다 (Priority: P2)

운영자는 원자성 보강 뒤에도 정상 체결, 부분 체결, 완료 체결, 거래소 스윕, 브로커 오류 격리가 기존처럼 동작한다고 확인할 수 있어야 한다.

**Why this priority**: 안전 보강이 체결 동기화 자체를 멈추면 live/paper 성과와 리밸런싱 상태가 더 나빠진다.

**Independent Test**: 기존 `test_fill_sync.py`, worker fill sync, performance fill reader 테스트가 계속 통과한다.

**Acceptance Scenarios**:

1. **Given** 브로커가 신규 체결을 보고함, **When** `sync_fills`가 실행되면, **Then** 기존처럼 `FILLED` 또는 `PARTIALLY_FILLED` 상태와 포지션이 반영된다.
2. **Given** 브로커 조회가 실패함, **When** `sync_fills`가 실행되면, **Then** 기존처럼 `ERROR` 감사와 오류 결과를 남기고 주문 상태는 유지된다.

### Edge Cases

- `plan_fill_ingestion`이 이미 기록된 누적 수량을 보고 새 체결을 계획하지 않는 정상 멱등 경로는 유지한다.
- 방어적으로 중복 `kis_fill_id`가 계획에 들어와도 `fills` row 삽입 성공분만 감사와 캐시에 반영한다.
- 체결 적용 트랜잭션 실패 뒤 `ERROR` 감사 기록은 별도 트랜잭션으로 남길 수 있지만, 실패한 `FILL` 감사와 원장 row는 남기지 않는다.
- `current_positions`는 계속 재구축 가능한 캐시다. 이번 스펙은 캐시를 원장과 동시에 갱신하는 적용 경로를 닫고, 전체 재구축 정책 변경은 후속으로 분리한다.
- 외부 보유 청산처럼 원장에 선행 매수가 없는 특수 매도는 이번 스펙에서 새로 금지하지 않는다.

## Requirements

### Functional Requirements

- **FR-001**: 체결 계획 적용은 `BEGIN IMMEDIATE` 트랜잭션 안에서 실행되어야 한다.
- **FR-002**: 새 `fills` row 삽입, `FILL` 감사 이벤트, `current_positions` 갱신, 주문 상태 전이는 같은 트랜잭션에서 커밋되어야 한다.
- **FR-003**: 체결 적용 중 어떤 예외가 발생하면 해당 트랜잭션의 `fills`, `audit_log`, `current_positions`, 주문 상태 변경은 모두 롤백되어야 한다.
- **FR-004**: `fills.kis_fill_id` 중복으로 `INSERT OR IGNORE`가 row를 삽입하지 않으면 `FILL` 감사 이벤트와 포지션 캐시 갱신도 실행하지 않아야 한다.
- **FR-005**: 체결 적용 결과의 `fills_applied`와 `qty_applied`는 실제 삽입된 체결 row만 세야 한다.
- **FR-006**: 정상 신규 체결의 `FILL` 감사 payload, `fills` row, 포지션 평균단가 계산은 기존 의미를 유지해야 한다.
- **FR-007**: 기존 `plan_fill_ingestion`의 순수 계획 계약은 유지해야 한다.
- **FR-008**: 브로커 조회 실패 격리 동작은 기존처럼 `ERROR` 감사와 오류 결과를 남겨야 한다.
- **FR-009**: 이 기능은 KIS, SSH, Anthropic, Telegram, 운영 서버, 유료 외부 서비스를 호출하지 않아야 한다.
- **FR-010**: 이 기능은 live sentinels, capital, whitelist, caps, loss budget, constitution, kernel manifest를 변경하지 않아야 한다.
- **FR-011**: 최종 인계는 체결 원자성 보강과 남은 후속 위험을 분리해 기록해야 한다.

### Key Entities

- **Fill Application Transaction**: 하나의 체결 계획 적용을 감싸는 데이터베이스 원자 단위.
- **Inserted Fill**: `fills.kis_fill_id` unique 제약을 통과해 실제로 새로 기록된 체결.
- **Skipped Duplicate Fill**: 이미 기록된 `kis_fill_id`라서 원장·감사·포지션 캐시를 움직이지 않는 체결.
- **Position Cache Update**: `fills` 원장에서 재구축 가능한 `current_positions`의 증분 갱신.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 중복 `kis_fill_id` 계획 적용 테스트에서 `fills_applied=0`, 새 `FILL` 감사 0건, 포지션 수량 불변이다.
- **SC-002**: 포지션 캐시 갱신 실패 주입 테스트에서 새 `fills` row와 `FILL` 감사 row가 모두 0건이다.
- **SC-003**: 정상 체결 계획 적용 테스트에서 `fills`, `audit_log`, `current_positions`, 주문 상태가 함께 반영된다.
- **SC-004**: 기존 fill sync 통합 테스트와 worker fill sync 테스트가 계속 통과한다.
- **SC-005**: `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`, PR 품질 관문이 통과한다.
- **SC-006**: Diff review shows no live sentinel, capital, whitelist, caps, loss budget, constitution, or kernel manifest change.

## Assumptions

- 현재 주요 돈 경로는 `PREVIEW_ONLY`이며 이 기능은 그 상태를 바꾸지 않는다.
- SQLite의 `BEGIN IMMEDIATE`는 단일 계좌 로컬 장부 적용을 직렬화하기에 충분하다.
- `fills.kis_fill_id`는 같은 브로커 누적 체결 상태를 식별하는 멱등 키로 계속 사용한다.
- 전체 포지션 재구축, 음수 포지션 DB 제약, `SUBMISSION_UNKNOWN` 자동 복구는 별도 후속 스펙으로 다룬다.

completed_candidate_id: candidate-atomic-fill-ledger
next_candidate_id: candidate-account-exposure-reservation

## Non-Goals

- Full broker order lookup recovery for `SUBMISSION_UNKNOWN`
- Account exposure reservation
- Degraded execution state and new-buy blocking
- Single execution authority
- Live trading arming
- Changing external holdings baseline semantics
