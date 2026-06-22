# Feature Specification: Micro GTAA Live Canary

**Feature Branch**: `Codex/micro-gtaa-live-canary`  
**Created**: 2026-06-22  
**Status**: Implemented  
**Input**: User description: "실제 돈 투입을 가능한 빠르게 앞당기고 싶다. 마이크로 GTAA 실거래 캐너리 방향으로, 세계 최고 수준과 최대 수익을 목표로 완수하라."

## User Scenarios & Testing

### User Story 1 - Same-Day Micro Live Exposure (Priority: P1)

운영자는 기존 자본 사다리의 20개 전진 관측을 기다리지 않고, 별도 운영자 승인형 소액 캐너리로 오늘 바로 실제 시장 노출을 만들고 싶다. 이 노출은 주식, 중기 미국채, 금의 세 비상관 축을 정수주 제약 안에서 담아야 하며, 실험 손실이 계좌 전체를 위협하지 않아야 한다.

**Why this priority**: 이 기능의 핵심 가치는 첫 자본 투입 시점을 앞당기는 것이다. 기존 `SPY`, `IEF`, `GLD` 조합은 소액 정수주에서 한쪽 다리만 체결되는 한계가 있어, 빠른 실거래 경험과 수익 기회 모두 약하다.

**Independent Test**: 소액 자본으로 드라이런 미리보기를 실행했을 때, 주식·채권·금 후보가 모두 허용 종목 안에 있고 주문은 정규장 지정가로만 계획되며, 기본 상태에서는 실주문이 나가지 않음을 확인한다.

**Acceptance Scenarios**:

1. **Given** 마이크로 캐너리가 기본 비무장 상태일 때, **When** 워크플로가 실행되면, **Then** 실주문 없이 드라이런 미리보기와 기록만 남는다.
2. **Given** 운영자가 명시적으로 무장했고 정규장 또는 수동 실행 조건이 맞을 때, **When** 마이크로 캐너리가 실행되면, **Then** 최대 1,000달러 자본 안에서 허용 ETF 정수주 주문만 제출된다.
3. **Given** 현재 계좌 또는 설정이 1,000달러 초과 자본을 요청할 때, **When** 마이크로 캐너리가 실행되면, **Then** 주문 제출 전에 거부되고 기록이 남는다.

---

### User Story 2 - Downside-Bounded Growth Attempt (Priority: P2)

운영자는 "최대 수익"을 목표로 하지만, 마진·옵션·레버리지 없이 생존성을 우선하는 한도 안에서만 위험을 키우고 싶다. 마이크로 캐너리는 성장 노출을 만들되, 손실이 사전에 선언한 작은 범위를 넘으면 자동 또는 운영자 조치로 빠르게 멈출 수 있어야 한다.

**Why this priority**: 빠른 실거래 시작은 손실 한도를 함께 고정하지 않으면 프로젝트의 안전 경계를 훼손한다. 수익 목표는 손실면을 먼저 고정한 뒤 그 안에서 추구해야 한다.

**Independent Test**: 캐너리 설정과 실행 기록을 확인해, 허용 자본·허용 종목·허용 주문 방식·손실 중단 기준이 모두 명시되어 있고 기존 킬스위치와 감사 경로가 보존됨을 확인한다.

**Acceptance Scenarios**:

1. **Given** 마이크로 캐너리 손실이 경고선에 도달했을 때, **When** 운영자가 상태 보고를 확인하면, **Then** 중단 검토가 필요한 이유와 현재 노출이 명확히 표시된다.
2. **Given** 마이크로 캐너리 손실이 강제 중단선에 도달했을 때, **When** 다음 실행이 평가되면, **Then** 신규 실주문이 차단되거나 운영자에게 즉시 무장 해제를 요구하는 상태가 된다.

---

### User Story 3 - Reproducible Operator Forensics (Priority: P3)

운영자와 다음 세션은 왜 기존 사다리를 우회하지 않고 별도 마이크로 캐너리를 만들었는지, 어떤 자산·자본·손실 한도로 시작했는지, 실제 주문 가능 경로가 어디인지 재현할 수 있어야 한다.

**Why this priority**: 실거래 경로는 다음 세션이 같은 결론을 재현할 수 있어야 한다. 판단 기록 없이 빠른 실거래만 만들면 운영 혼동과 중복 작업이 생긴다.

**Independent Test**: 스펙, 실행 안내, 워크플로 기록, PR 본문을 읽어 변경 목적·비목표·안전 경계·되돌림 방법을 확인한다.

**Acceptance Scenarios**:

1. **Given** 다음 세션이 이 기능을 인계받을 때, **When** 스펙과 최신 실행 기록을 읽으면, **Then** 기본 상태가 실주문 0건인지, 무장 조건이 무엇인지, 중단 방법이 무엇인지 알 수 있다.
2. **Given** 마이크로 캐너리가 부적합하다고 판단될 때, **When** 운영자가 되돌리려 하면, **Then** 센티넬을 비무장으로 돌리거나 워크플로를 멈춰 신규 실주문을 차단할 수 있다.

### Edge Cases

- 미국 정규장이 닫혀 있으면 실주문을 내지 않고 드라이런 또는 보류 상태로 기록한다.
- 브로커 시세 조회, 백필, 계좌 정보 조회가 실패하면 실주문을 제출하지 않는다.
- 후보 ETF 중 일부가 KIS 경로에서 시세 또는 주문 불능이면 그 실행은 실패 또는 축소 기록을 남기고, 허용되지 않은 대체 종목으로 자동 전환하지 않는다.
- 이미 기존 라이브 캐너리 또는 룰 워커가 주문을 낼 수 있는 상태이면 한 실계좌에 두 전략이 충돌하지 않도록 신규 주문을 막거나 명시적으로 기록한다.
- 자본이 너무 작아 세 다리 중 일부만 정수주로 담길 때는 주문을 무리하게 키우지 않고 계획과 한계를 드러낸다.

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a separate micro live-canary path that is independent from the existing evidence-gated capital ladder and does not weaken the ladder's criteria.
- **FR-002**: System MUST default the micro live-canary path to unarmed preview-only mode, producing no real orders until the operator-approved sentinel is armed.
- **FR-003**: System MUST cap manually armed micro canary capital at 1,000 USD or less unless a future ladder-authority field explicitly authorizes more.
- **FR-004**: System MUST restrict the micro canary universe to liquid US-listed ETFs representing US large-cap equity, intermediate US Treasuries, and gold exposure.
- **FR-005**: System MUST use only regular-session limit orders and deny all unknown symbols, accounts, order types, or sessions.
- **FR-006**: System MUST preserve existing position caps, per-symbol caps, global exposure caps, circuit breaker behavior, secret isolation, append-only audit logging, and daily reconciliation requirements.
- **FR-007**: System MUST include a pre-trade preview that shows planned symbols, side, quantity, limit price, and whether real orders would be skipped or submitted.
- **FR-008**: System MUST document warning and stop thresholds for micro canary losses, with a hard stop target no worse than 5% of the micro canary capital.
- **FR-009**: System MUST make the micro canary reversible by a small sentinel or workflow change that blocks future real orders without deleting historical audit evidence.
- **FR-010**: System MUST keep derivatives, leverage, margin, short selling, crypto, domestic Korean equities, and market orders out of scope.

### Key Entities

- **Micro Canary Request**: Operator-controlled arming state, capital amount, requested strategy, and audit note for the micro live canary.
- **Micro GTAA Portfolio**: The allowed asset set, target allocation rule, trend defense rule, and sizing limits used for the live micro canary.
- **Micro Canary Run**: One workflow execution containing trigger type, armed state, capital, preview results, live order outcome, measurement output, and sidecar metadata.
- **Micro Canary Stop Policy**: Warning and hard-stop thresholds that define when the operator or automation must stop adding exposure.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A default run of the micro live canary produces zero real orders and records a complete preview.
- **SC-002**: An armed run cannot submit orders above 1,000 USD of declared micro canary capital.
- **SC-003**: Every candidate real order is rejected unless it uses a whitelisted ETF, a whitelisted account, a limit order, and the regular session.
- **SC-004**: The first micro canary can be stopped before the next scheduled real-order run by changing one clearly documented sentinel state.
- **SC-005**: The implementation has automated tests covering default unarmed behavior, capital guard behavior, and micro portfolio configuration validity.
- **SC-006**: The operator can identify from repository artifacts why this is a bounded live canary rather than a full-live promotion.

## Assumptions

- The operator's latest approval authorizes a bounded micro live canary but does not authorize leverage, margin, derivatives, or relaxing K1/K2 safety mechanisms.
- Existing KIS credentials, SSH secrets, and live account setup remain in place; this feature does not add or reveal secrets.
- SPYM is the preferred low-unit US equity proxy, IEF remains the intermediate Treasury proxy, and GLDM is the preferred low-unit gold proxy because the existing SPY/GLD prices make 1,000 USD integer-share diversification weak.
- The micro canary is a live-canary experiment for faster market exposure, not statistical proof that the strategy has edge.
- Existing forward paper and capital ladder continue to run unchanged and remain the path to larger capital deployment.
