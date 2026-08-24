# Feature Specification: Commodity Positioning and Real-World Gate Controls

**Feature Branch**: `Codex/157-commodity-inventory-positioning-positive-controls`  
**Created**: 2026-08-25  
**Status**: Implemented; production verification pending  
**Input**: User description: "다음 우선순위를 진행하고 합격 기준이 현실 전략도 통과할 수 있는지 다시 검증"

## User Scenarios & Testing

### User Story 1 - 현실 자료로 관문을 반증 가능하게 만든다 (Priority: P1)

운영자는 합성 난수뿐 아니라 널리 알려진 실제 위험 프리미엄과 추세 전략이 같은 홀드아웃
PSR 관문을 통과하는지 확인한다. 관문은 좋은 것을 통과시키고 평균이 0인 대조군은 막아야 한다.

**Why this priority**: 모든 실제 후보가 탈락한 상황에서는 검사기의 현실 검출력을 먼저 입증해야 한다.

**Independent Test**: 고정된 Fama-French 시장 초과수익과 AQR 분산 추세 자료를 읽어
2007년 이후 관문 결과를 재현하고, 평균 제거 대조군은 같은 관문에서 탈락한다.

**Acceptance Scenarios**:

1. **Given** 2007년 이후 미국 시장 초과수익, **When** PSR 0.95 관문을 적용하면, **Then** 라이브 통계 대조군을 통과한다.
2. **Given** 2007년 이후 AQR 전체 자산 추세 수익, **When** 같은 관문을 적용하면, **Then** 라이브 통계 대조군을 통과한다.
3. **Given** 각 수익률의 평균을 제거한 대조군, **When** 같은 관문을 적용하면, **Then** 라이브 관문을 통과하지 않는다.
4. **Given** 현실 대조군 자료가 누락·변조·오래됨, **When** 전략을 판정하면, **Then** 후보 성과와 무관하게 승격을 차단한다.

---

### User Story 2 - 독립 원자재 재고·포지셔닝 전략을 검증한다 (Priority: P1)

운영자는 가격 기간구조와 다른 CFTC 거래자 포지션과 EIA 상업 원유 재고를 사용한
16개 고정 후보를 개발 구간에서 하나만 선택하고 손대지 않은 홀드아웃에서 확인한다.

**Why this priority**: 이전 기간구조 신호의 국면 반전을 설명할 수 있는 독립 경제 자료다.

**Independent Test**: CFTC·EIA·GSG·현금 자료로 후보 16개가 정확히 생성되고, 홀드아웃
값을 바꿔도 개발 선택 후보가 변하지 않으며, 비용과 경제성 관문이 모두 재현된다.

**Acceptance Scenarios**:

1. **Given** 사전등록된 네 문법·두 기간·두 최대 비중, **When** 후보를 생성하면, **Then** 고유 후보와 지문이 정확히 16개다.
2. **Given** CFTC 보고일과 EIA 관측일, **When** 월초 목표를 계산하면, **Then** 각각 3일·5일 게시 지연 뒤 알려진 값만 사용한다.
3. **Given** 개발 96개월과 한 달 격리, **When** 홀드아웃을 평가하면, **Then** 최소 120개월에서 후보를 다시 선택하지 않는다.
4. **Given** 후보가 라이브 또는 종이 기준을 통과하지 못함, **When** 결과를 발행하면, **Then** 후보·배포 설정·자본·주문은 비어 있다.

---

### User Story 3 - 자동화와 돈 경로를 분리한다 (Priority: P2)

운영자는 새 자료와 판정을 자동 재생하되, 합격 결과도 기존 단계별 승격과 허용 종목 승인을
건너뛰어 실제 주문으로 이어지지 않게 한다.

**Why this priority**: 관문 감사를 이유로 안전 경계를 낮추면 검사 개선이 주문 우회가 된다.

**Independent Test**: 생산 workflow가 자료·대조군·16개 후보·688개 감사 기록을 발행해도
브로커 모듈을 호출하지 않고 GSG 허용 권한과 배치 자본이 거짓으로 유지된다.

**Acceptance Scenarios**:

1. **Given** 모든 연구 관문 통과, **When** 결과를 발행하면, **Then** 연구 캐너리 자격만 내고 자본과 주문은 바꾸지 않는다.
2. **Given** 자료·코드·전략·대조군 지문 불일치, **When** 승격 증거를 읽으면, **Then** 브로커 조회 전에 실패한다.

### Edge Cases

- CFTC 고정 12개 계약 중 한 계약이라도 전체 기간을 충족하지 못하면 자료 관문을 닫는다.
- 포지션의 미결제약정이 0이거나 숫자가 아니면 해당 보고서를 거부한다.
- EIA 현재 파일은 역사 개정값일 수 있으므로 완전한 빈티지 자료로 가장하지 않는다.
- CFTC 역사 분류는 과거로 갈수록 재분류 오차가 커질 수 있으므로 자료 한계에 기록한다.
- 월초 전에 게시되지 않은 보고서는 해당 월 신호에서 제외한다.
- 현실 양성 대조군은 관문 감사 전용이며 전략 후보, 다중검정 가족, 수익 판정에 섞지 않는다.
- 홀드아웃을 본 뒤 문법·기간·비용·기준·목적을 바꾸면 새 가족으로 다시 사전등록한다.

## Requirements

> **돈 경로·안전 경계 변경**: 이 기능은 판정 증거를 강화하지만 자본·주문·허용목록을
> 변경하지 않는다. 합격해도 기존 `Backtest -> Canary -> Full` 단계를 유지한다.

### Functional Requirements

- **FR-001**: System MUST parse official Fama-French monthly market excess returns and AQR monthly time-series momentum returns with source hashes and coverage.
- **FR-002**: System MUST evaluate preregistered 2007-onward real-world positive controls with the exact live PSR threshold of 0.95.
- **FR-003**: System MUST require the U.S. market excess return and diversified AQR TSMOM controls to pass, while demeaned controls fail.
- **FR-004**: System MUST keep positive controls outside candidate selection, multiplicity counts, and promotion evidence.
- **FR-005**: System MUST make a missing, stale, malformed, or mismatched real-world control audit block promotion.
- **FR-006**: System MUST load CFTC disaggregated futures-only positions for fixed contract codes `001602`, `002602`, `005602`, `023651`, `033661`, `057642`, `067651`, `080732`, `083731`, `084691`, `085692`, and `088691`.
- **FR-007**: System MUST load EIA weekly U.S. commercial crude oil stocks excluding the Strategic Petroleum Reserve, series `WCESTUS1`.
- **FR-008**: System MUST normalize managed-money and producer net positions by open interest, standardize within each contract, and aggregate fixed contracts without raw-contract-size dominance.
- **FR-009**: System MUST generate exactly 16 candidates from four frozen grammars, 26/52-week lookbacks, and 50/100% maximum GSG allocations.
- **FR-010**: The four grammars MUST be managed-money trend, producer scarcity, inventory tightness, and joint positioning-inventory confirmation.
- **FR-011**: System MUST apply CFTC report-date plus 3-day and EIA period-end plus 5-day publication lags before a signal is available.
- **FR-012**: System MUST use GSG NAV returns and prior-known DGS3MO cash returns with 10/25/50 basis-point turnover costs.
- **FR-013**: System MUST select one candidate on 96 development months, embargo one month, and evaluate at least 120 untouched holdout months.
- **FR-014**: System MUST retain live PSR 0.95, paper PSR 0.80, positive 50bp excess return, correlation below 0.80, and objective-specific blend gates.
- **FR-015**: System MUST preserve 672 prior records and append 16 unique strategy fingerprints for 688 global audit records.
- **FR-016**: System MUST publish source, control, candidate, split, target-weight, code, and gate fingerprints plus all failed gates.
- **FR-017**: System MUST keep GSG outside the live whitelist and leave capital, orders, arming, caps, secrets, constitution, and kernel unchanged.
- **FR-018**: System MUST fail before broker import or call on any incomplete evidence and retain the existing staged promotion ladder.

### Key Entities

- **RealWorldGateAudit**: Actual positive and null controls, windows, PSRs, hashes, and pass state.
- **PositioningObservation**: One CFTC contract report with normalized managed-money and producer positions and publication availability.
- **InventoryObservation**: One EIA weekly crude stock level and publication availability.
- **CommodityPositioningPolicy**: Frozen grammar, lookback, maximum allocation, and strategy fingerprint.
- **CommodityPositioningDecision**: Development selection, untouched holdout, costs, economics, audit counts, and tier verdict.

## Success Criteria

### Measurable Outcomes

- **SC-001**: The empirical audit shows both preregistered real positive controls at PSR 0.95 or above and all demeaned controls below 0.95.
- **SC-002**: Repeated runs with identical source bytes produce identical control and strategy fingerprints and metrics.
- **SC-003**: Exactly 16 unique candidates and 688 unique global audit records are emitted.
- **SC-004**: The selected candidate ID is unchanged when only holdout values change.
- **SC-005**: Every target uses only reports published before that target month and all source contract failures close promotion.
- **SC-006**: Focused tests, full pytest, ruff, YAML, strict harness, handoff facts, PR gate, production replay, deployment, and KIS no-order smoke pass before completion.

## Assumptions

- The positive controls prove the gate can recognize strong realized historical effects; they do not promise future profits.
- Current official CFTC and EIA histories can contain revisions or backcast classifications, which remain explicit basis risk.
- GSG is a tradable research proxy for the broad commodity basket but does not exactly match the equal-normalized signal contracts.
- Grade 4 applies because decision evidence could nominate a future live strategy, even though this change authorizes no money movement.

## Risk Classification

**Grade 4 - money path**. The feature strengthens evidence that may nominate a live strategy but does not authorize capital, orders, whitelist changes, or live arming.
