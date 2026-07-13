# Feature Specification: Order Submission Uncertainty Recovery

**Feature Branch**: `Codex/112-order-submission-uncertainty-recovery`
**Created**: 2026-07-13
**Status**: Draft
**Input**: User description: "남은 작업도 마무리 할 수 있어?"

## Problem Statement

현재 브로커 공통 HTTP 클라이언트는 메서드 구분 없이 전송 오류와 5xx 응답을 재시도한다. 해외주식 주문 제출은 이 클라이언트로 `POST /uapi/overseas-stock/v1/trading/order`를 호출하므로, 브로커가 첫 요청을 접수했지만 응답이 유실되거나 5xx로 돌아온 경우 같은 주문이 자동 재전송될 수 있다.

라우터도 이 실패를 `REJECTED_BY_BROKER`로 닫는다. `REJECTED_BY_BROKER`는 접수·체결 0건으로 보는 의미인데, 전송 실패나 5xx는 실제 접수 여부가 불명확하다. 이 상태를 거부로 기록하면 운영자는 확인 조회 없이 새 주문을 시도하거나, 중복 주문 위험을 놓칠 수 있다.

이 스펙은 주문 제출의 불명확성을 명시 상태로 보존한다. **새 주문 제출 `POST`는 자동 재시도하지 않고, 접수 여부가 불명확한 실패는 `SUBMISSION_UNKNOWN`으로 기록해 수동 또는 별도 복구 조회 전까지 거부와 구분한다.**

## Operator Authorization Boundary

이 작업은 돈 경로 변경이므로 위험 등급 4로 다룬다. 다만 승인 범위는 코드·테스트·문서의 안전화 변경뿐이다.

허용 범위:

- 브로커 클라이언트의 요청별 재시도 정책 추가
- 신규 주문 제출 경로의 자동 재시도 제거
- 불명확한 제출 실패의 상태·감사 이벤트 추가
- 운영 알림과 읽기 전용 요약의 상태 표시 보강
- 관련 단위·통합 테스트 추가

금지 범위:

- 실제 주문 제출 또는 취소
- `armed: true` 변경
- 실거래 모드 전환
- 자본 배분, 허용 종목, 포지션 한도, 손실 예산 확대
- 운영 서버 또는 KIS 계좌 조회
- 체결 원장 원자성, 노출 예약, 단일 실행 권한의 동시 구현

## User Scenarios & Testing

### User Story 1 - 신규 주문 제출은 자동 재시도되지 않는다 (Priority: P1)

운영자는 신규 주문 제출이 응답 유실 또는 5xx를 만났을 때 같은 주문을 자동으로 한 번 더 보내지 않는다고 확신할 수 있어야 한다.

**Why this priority**: 자동 재시도는 실제 계좌에 중복 주문을 만들 수 있는 직접 돈 경로 위험이다.

**Independent Test**: 주문 제출 엔드포인트가 500을 반환하거나 전송 오류를 내도 실제 `POST /trading/order` 호출 수는 1회다.

**Acceptance Scenarios**:

1. **Given** KIS 주문 제출이 500을 반환함, **When** 라우터가 주문을 제출하면, **Then** 라우터는 같은 `POST`를 재시도하지 않는다.
2. **Given** 주문 제출 중 네트워크 전송 오류가 발생함, **When** 라우터가 실패를 처리하면, **Then** 추가 주문 제출 요청은 발생하지 않는다.
3. **Given** 읽기 전용 조회가 일시 5xx 후 회복함, **When** 조회 요청을 실행하면, **Then** 기존 조회 재시도 동작은 유지된다.

---

### User Story 2 - 접수 여부 불명확 실패는 거부와 구분된다 (Priority: P1)

운영자는 브로커가 명시적으로 거부한 주문과 접수 여부가 불명확한 주문을 다른 상태로 본다.

**Why this priority**: 불명확한 제출을 거부로 닫으면 운영자가 중복 주문 가능성을 모른 채 복구 행동을 할 수 있다.

**Independent Test**: HTTP 5xx 또는 전송 오류는 `SUBMISSION_UNKNOWN` 상태와 `ORDER_SUBMISSION_UNKNOWN` 감사 이벤트를 남기고, KIS 업무 오류 응답은 기존 `REJECTED_BY_BROKER`로 남는다.

**Acceptance Scenarios**:

1. **Given** 주문 제출 응답이 5xx임, **When** 라우터가 실패를 처리하면, **Then** `orders.state`는 `SUBMISSION_UNKNOWN`이고 감사 로그에는 `ORDER_SUBMISSION_UNKNOWN`이 남는다.
2. **Given** 전송 오류가 발생함, **When** 라우터가 실패를 처리하면, **Then** 상태와 감사 이벤트는 접수 여부 불명확으로 남는다.
3. **Given** HTTP 200이지만 KIS 응답 본문이 `rt_cd=1` 업무 거부를 명시함, **When** 라우터가 실패를 처리하면, **Then** 기존 `REJECTED_BY_BROKER` 상태와 `ORDER_REJECTED_BY_BROKER` 이벤트가 유지된다.
4. **Given** KIS가 정상 주문번호를 반환함, **When** 라우터가 성공을 처리하면, **Then** 기존 `SUBMITTED` 상태와 `ORDER_SUBMITTED` 이벤트가 유지된다.

---

### User Story 3 - 운영 표면이 불명확 상태를 숨기지 않는다 (Priority: P2)

운영자는 알림과 읽기 전용 요약에서 불명확한 제출을 오류·주의 상태로 볼 수 있어야 한다.

**Why this priority**: 상태를 기록해도 알림과 요약에서 빠지면 다음 세션과 운영자가 다시 같은 위험을 추론해야 한다.

**Independent Test**: 텔레그램 감사 꼬리 포맷터와 읽기 전용 요약 카운트가 `ORDER_SUBMISSION_UNKNOWN`을 포함한다.

**Acceptance Scenarios**:

1. **Given** `ORDER_SUBMISSION_UNKNOWN` 감사 이벤트가 있음, **When** 알림 포맷터가 메시지를 만들면, **Then** 접수 여부 확인 필요와 자동 재시도 없음이 보인다.
2. **Given** 설계 확인 또는 읽기 전용 상태 요약이 주문 오류 수를 집계함, **When** 불명확 제출 이벤트가 있음, **Then** 기존 오류·브로커 거부와 함께 누락 없이 집계된다.

### Edge Cases

- `cancel_order` 같은 취소 요청은 이번 스펙의 핵심 신규 주문 중복 위험과 별도 문제다. 이번 변경은 신규 주문 제출 경로를 우선 닫되, 요청별 재시도 제어를 제공해 후속 취소 정책 변경이 가능하게 한다.
- HTTP 200 본문이 명시적 업무 거부(`rt_cd != 0` 또는 주문번호 없음)를 담으면 접수 여부 불명확이 아니라 브로커 거부로 본다.
- JSON 파싱 실패가 200 응답에서 발생하면 브로커가 주문번호를 반환하지 못한 것이므로 보수적으로 불명확 상태로 둔다.
- 서킷 브레이커는 전송 오류와 5xx를 실패로 기록하되, 같은 주문을 재시도하지 않는다.
- 감사 진단 정보는 기존 계좌·비밀값 마스킹을 유지한다.
- 기존 역사적 `REJECTED_BY_BROKER` 행은 변경하지 않는다.
- `SUBMISSION_UNKNOWN`은 열린 주문 상태가 아니다. 체결 동기화가 주문번호 없이 자동 확인할 수 없으므로 별도 조회·복구 절차 전까지 운영 주의 상태로 남긴다.

## Requirements

### Functional Requirements

- **FR-001**: `ResilientClient.request` MUST support a per-request no-retry policy while preserving existing retry behavior for read-only calls by default.
- **FR-002**: `place_order` MUST call the KIS 신규 주문 `POST` with no automatic retry on 5xx or `httpx.TransportError`.
- **FR-003**: Existing read-only `GET` requests MUST keep transient retry behavior unless explicitly disabled.
- **FR-004**: A transient order submission failure MUST still record circuit-breaker failure state.
- **FR-005**: The order router MUST classify HTTP 5xx and transport failures from `place_order` as `SUBMISSION_UNKNOWN`.
- **FR-006**: The order router MUST classify missing or non-JSON accepted-order-id responses after a submitted write attempt as `SUBMISSION_UNKNOWN` unless the response clearly indicates a business rejection.
- **FR-007**: The order router MUST preserve explicit KIS business rejections as `REJECTED_BY_BROKER`.
- **FR-008**: `SUBMISSION_UNKNOWN` MUST be persisted in `orders.state` and `order_state_history`.
- **FR-009**: `ORDER_SUBMISSION_UNKNOWN` MUST be appended to `audit_log` with masked diagnostics.
- **FR-010**: `ORDER_SUBMISSION_UNKNOWN` payload MUST include error code, message, diagnostics, and an operator next action that says not to auto-retry before broker order lookup.
- **FR-011**: No `kis_order_id` may be set for `SUBMISSION_UNKNOWN` unless a later explicit reconciliation path proves the broker order id.
- **FR-012**: `ORDER_REJECTED_BY_BROKER` MUST continue to mean broker rejection or invalid request with no accepted order id.
- **FR-013**: Telegram/audit-tail formatting MUST include `ORDER_SUBMISSION_UNKNOWN` with wording that 접수 여부 is unknown.
- **FR-014**: Read-only status summaries that count live errors MUST include `ORDER_SUBMISSION_UNKNOWN`.
- **FR-015**: Tests MUST prove the KIS 신규 주문 endpoint is called once on 5xx and once on transport failure.
- **FR-016**: Tests MUST prove read-only retries still retry 5xx and transport failures.
- **FR-017**: Tests MUST prove diagnostics remain masked for account and token material.
- **FR-018**: This feature MUST NOT execute KIS, SSH, Anthropic, Telegram, or any paid external service.
- **FR-019**: This feature MUST NOT modify live sentinels, capital, whitelist, caps, loss budget, constitution, or kernel manifest.
- **FR-020**: The handoff MUST name the new status, retained retry behavior for reads, and remaining manual recovery gap.

### Key Entities

- **Retry Policy**: Per-request instruction controlling whether transient failures are retried by `ResilientClient`.
- **Order Submission Failure Classification**: Deterministic classification of broker write failures into `SUBMISSION_UNKNOWN` or `REJECTED_BY_BROKER`.
- **Submission Unknown Audit Payload**: Append-only audit event for cases where KIS may have accepted a write but the local system lacks a confirmed order id.
- **Operator Next Action**: Human-readable instruction attached to unknown submissions: do not auto-retry; query broker order/execution history first.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Focused broker-client tests show default GET retry still calls a 5xx route more than once.
- **SC-002**: Focused order-submit tests show `POST /uapi/overseas-stock/v1/trading/order` is called exactly once on 5xx.
- **SC-003**: Focused order-submit tests show transport failure is called exactly once and produces `SUBMISSION_UNKNOWN`.
- **SC-004**: Router tests show 5xx and transport failures append `ORDER_SUBMISSION_UNKNOWN` and persist `SUBMISSION_UNKNOWN`.
- **SC-005**: Router tests show HTTP 200 KIS business rejection remains `REJECTED_BY_BROKER`.
- **SC-006**: Audit payload tests show `ORDER_SUBMISSION_UNKNOWN` is part of `EventType` and accepts masked diagnostics.
- **SC-007**: Notification tests show the alert says 접수 여부 확인 필요 and does not claim broker rejection.
- **SC-008**: Search and diff review show no changes to live sentinels, caps, whitelist, loss budget, constitution, or kernel manifest.
- **SC-009**: `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`, and PR quality gate pass before merge.
- **SC-010**: The final handoff identifies `113-atomic-fill-ledger` as the next execution-safety item unless new evidence changes priority.

## Assumptions

- This repository currently runs primary money paths in `PREVIEW_ONLY` or `armed: false`; this feature does not change that state.
- KIS 신규 주문 API does not provide a repo-visible idempotency key that can make blind replay safe.
- A no-retry order submission may leave uncertain orders requiring broker lookup; that is safer than automatic duplicate submission.
- A full automated recovery workflow belongs in a later feature once order/execution lookup semantics are designed.

completed_candidate_id: candidate-order-submission-uncertainty-recovery
next_candidate_id: candidate-atomic-fill-ledger

## Non-Goals

- Implementing full broker order lookup recovery
- Making fill ingestion transactional
- Adding account exposure reservation
- Building a single execution authority
- Changing cancel/modify retry semantics beyond adding reusable request policy support
- Arming live trading
- Proving actual server or KIS account state

## Follow-on

- `113-atomic-fill-ledger`
- `114-account-exposure-reservation`
- `115-degraded-execution-state`
- `116-single-execution-authority`
