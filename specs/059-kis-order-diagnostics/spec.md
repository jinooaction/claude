# Feature Specification: KIS Order Diagnostics

**Feature Branch**: `Codex/kis-order-diagnostics`  
**Created**: 2026-06-22  
**Status**: Draft  
**Input**: User description: "마이크로 GTAA 실패의 다음 정확한 진행을 목표 스킬로 진행하라. 실제 주문 재시도 전에 원인 확정 능력, 주문 전제 검증, KIS payload 정합성을 복구한다."

## User Scenarios & Testing

### User Story 1 - Prove Live Order Preconditions Before Submission (Priority: P1)

운영자는 마이크로 GTAA가 실주문을 보내기 전에 현재 실행이 허용된 주문 세션인지, 계좌의 즉시 매수 가능 현금이 충분한지, 그리고 예약주문이 필요한 시간대에 일반 주문을 보내지 않는지 확인할 수 있어야 한다.

**Why this priority**: 직전 실패는 미국 정규장 밖에서 일반 주문 경로로 들어갔고, 실제 코드에는 스펙 058의 "정규장 지정가" 조건을 강제하는 게이트가 없었다. 이 전제가 닫히지 않으면 주문 재시도는 원인 확정이 아니라 도박이 된다.

**Independent Test**: 미국 정규장이 닫힌 시각을 주입한 실행에서 실주문 단계가 주문을 보내지 않고, 이유와 세션 판정을 결과 기록에 남기는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 마이크로 GTAA가 무장되어 있고 현재 시각이 미국 정규장 밖일 때, **When** 라이브 실행이 평가되면, **Then** 일반 주문은 제출되지 않고 세션 차단 사유가 기록된다.
2. **Given** 마이크로 GTAA가 무장되어 있고 현재 시각이 미국 정규장 안일 때, **When** 라이브 실행이 평가되면, **Then** 계좌 현금과 주문 예정 금액이 함께 확인된 뒤 기존 위험 게이트를 통과한 주문만 제출 후보가 된다.
3. **Given** 계좌 현금 조회가 실패하거나 즉시 매수 가능 금액을 확인할 수 없을 때, **When** 라이브 실행이 평가되면, **Then** 실주문은 제출되지 않고 "계좌 전제 미확정" 상태로 기록된다.

---

### User Story 2 - Match KIS Order Request Shape to Current Official Samples (Priority: P2)

운영자는 KIS 일반 해외주식 주문 요청이 현재 KIS 공식 예제의 필수 필드와 같은 형태인지 자동 테스트로 확인할 수 있어야 한다.

**Why this priority**: 직전 실패 당시 현재 코드의 일반 주문 payload에는 KIS 공식 예제가 필수로 검증하는 `ORD_SVR_DVSN_CD`가 없었다. 응답 본문이 없더라도 이 불일치는 주문 재시도 전에 제거해야 하는 확인된 내부 결함이다.

**Independent Test**: 브로커 클라이언트를 모킹해 매수와 매도 주문을 제출하면, 요청 본문에 공식 예제 기준 필수 필드가 포함되고 민감한 계좌번호는 테스트 외부 로그에 그대로 노출되지 않는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 미국 일반 지정가 매수 주문이 준비되었을 때, **When** KIS 요청 본문이 만들어지면, **Then** `CANO`, `ACNT_PRDT_CD`, `OVRS_EXCG_CD`, `PDNO`, `ORD_QTY`, `OVRS_ORD_UNPR`, `CTAC_TLNO`, `MGCO_APTM_ODNO`, `SLL_TYPE`, `ORD_SVR_DVSN_CD`, `ORD_DVSN`이 포함된다.
2. **Given** 미국 일반 지정가 매도 주문이 준비되었을 때, **When** KIS 요청 본문이 만들어지면, **Then** 매도용 `SLL_TYPE`이 명시되고 주문 구분은 지정가로 고정된다.
3. **Given** 예약주문 또는 주간거래가 필요한 시간대일 때, **When** 마이크로 GTAA 일반 주문 경로가 평가되면, **Then** 별도 예약·주간거래 API로 자동 우회하지 않고 이번 실행을 보류한다.

---

### User Story 3 - Preserve Evidence Needed to Confirm Broker Rejections (Priority: P3)

운영자와 다음 세션은 KIS가 주문을 거부했을 때 HTTP 상태 문자열만 보는 것이 아니라, 민감정보가 마스킹된 요청 요약과 KIS 응답 본문을 감사 로그와 사이드카에서 확인할 수 있어야 한다.

**Why this priority**: 직전 run `27935469561`은 KIS가 `500`을 반환했다는 사실만 남겼고, 실제 `msg_cd` 또는 `msg1` 사유는 사라졌다. 같은 장애가 재발하면 정확한 원인을 확정할 수 있어야 한다.

**Independent Test**: 브로커가 본문이 있는 HTTP 오류를 반환하도록 모킹하면, 감사 payload와 결과 JSON에 HTTP 상태, KIS 오류 코드/메시지, 마스킹된 요청 요약이 남고 계좌번호·토큰·키는 남지 않는지 확인한다.

**Acceptance Scenarios**:

1. **Given** KIS가 JSON 오류 본문을 포함한 HTTP 오류를 반환할 때, **When** 주문 라우터가 거부 결과를 기록하면, **Then** 응답 본문의 진단 필드는 보존되고 비밀값은 마스킹된다.
2. **Given** KIS가 비JSON 또는 빈 오류 본문을 반환할 때, **When** 주문 라우터가 거부 결과를 기록하면, **Then** HTTP 상태와 endpoint, 요청 요약, 본문 파싱 실패 여부가 기록된다.
3. **Given** 사이드카가 최신 마이크로 GTAA 실행 결과를 발행할 때, **When** 라이브 주문이 거부되면, **Then** 원인 확정에 필요한 broker diagnostics 섹션이 결과에 포함된다.

### Edge Cases

- GitHub Actions의 수동 실행이 미국 정규장 밖에서 호출되면 무장 상태여도 실주문을 보내지 않는다.
- 예약주문 가능 시간대는 "일반 주문 허용"으로 취급하지 않는다. 예약주문 지원은 별도 스펙 전까지 자동 사용하지 않는다.
- KIS 잔고 또는 매수 가능 현금 조회가 실패하면 주문 금액이 작아 보여도 실주문을 보내지 않는다.
- KIS 오류 본문이 너무 크면 진단에 필요한 앞부분만 제한적으로 보존하고 비밀값 마스킹을 먼저 적용한다.
- KIS가 HTTP 200을 반환했지만 `rt_cd`가 실패이거나 `output.ODNO`가 없으면 성공으로 취급하지 않고 응답 코드·메시지를 진단으로 남긴다.
- HTTP 오류가 재시도 후 최종 실패했을 때도 마지막 응답의 상태와 본문 요약을 잃지 않는다.
- 이 기능은 헌법, 커널 목록, 포지션 한도, 화이트리스트, 비밀값 로딩 규칙을 완화하지 않는다.

## Requirements

### Functional Requirements

- **FR-001**: System MUST block micro GTAA live order submission outside US regular trading hours unless a future spec explicitly implements a separate reservation-order path.
- **FR-002**: System MUST record the evaluated market-session state, evaluation timestamp, and skip reason for every armed micro GTAA live attempt.
- **FR-003**: System MUST perform a same-run read-only KIS account/cash preflight before live order submission and block submission when purchasable cash is unknown or below the planned order notional plus a conservative fee buffer.
- **FR-004**: System MUST keep push-triggered arming commits preview-only and MUST NOT place real orders from a push event.
- **FR-005**: System MUST align the normal US overseas-stock order body with the current KIS official sample's required normal-order fields, including `ORD_SVR_DVSN_CD`.
- **FR-006**: System MUST keep normal micro GTAA orders as regular-session limit orders only and MUST NOT silently switch to reservation-order or daytime-order endpoints.
- **FR-007**: System MUST preserve broker rejection diagnostics, including HTTP status, endpoint, KIS response code/message when present, response body preview, and sanitized request summary, even when KIS returns HTTP 200 with an error body.
- **FR-008**: System MUST mask account numbers, tokens, app keys, app secrets, and any authorization header value in diagnostics.
- **FR-009**: System MUST expose diagnostics in both the local audit payload used by order routing and the micro GTAA sidecar output used by the operator.
- **FR-010**: System MUST include automated tests for session blocking, KIS payload shape, diagnostics preservation, and secret masking.
- **FR-011**: System MUST NOT execute a live order as part of implementing or validating this feature.
- **FR-012**: System MUST leave capital amount, allowed universe, existing position caps, whitelist, circuit breaker, and halt behavior unchanged.

### Key Entities

- **Order Preconditions**: Market-session state, account cash state, planned notional, trigger event, and reason that permits or blocks live submission.
- **KIS Normal Order Request**: Sanitizable request shape for the regular overseas-stock order endpoint.
- **Broker Rejection Diagnostics**: Structured evidence captured when KIS rejects or fails a request.
- **Micro GTAA Run Evidence**: Sidecar-visible record containing preview, preflight, breaker, live result, and diagnostics.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A simulated armed micro GTAA run outside US regular hours submits zero broker orders and records a session-blocked reason.
- **SC-002**: Unit tests prove normal KIS buy and sell request bodies contain all official-sample required fields.
- **SC-003**: Unit tests prove an HTTP error with a KIS JSON body preserves the KIS diagnostic fields while masking account and credential material.
- **SC-003A**: Unit tests prove an HTTP 200 response without an accepted KIS order id is rejected with KIS diagnostic fields instead of an opaque `KeyError`.
- **SC-004**: A simulated insufficient-cash preflight submits zero broker orders and records the observed cash and planned notional.
- **SC-005**: The implementation passes the repository's full `uv run pytest` and `uv run ruff check src tests` gates before merge.
- **SC-006**: The operator can read the sidecar output from the next failed broker attempt and identify whether the cause was session, cash, request shape, or KIS response content.

## Assumptions

- The current operator approval remains limited to micro GTAA `capital_usd=1000` and does not authorize a broader strategy, larger capital, leverage, margin, or derivatives.
- The next live attempt should be delayed or skipped rather than rerouted to reservation order when regular-session conditions are not satisfied.
- Current KIS credentials and account permissions are not changed by this feature.
- Official KIS samples in `koreainvestment/open-trading-api` are the reference for request-shape conformance.
- Read-only KIS preflight calls are allowed for validation, but implementation verification in this session uses automated mocks and does not place real orders.
