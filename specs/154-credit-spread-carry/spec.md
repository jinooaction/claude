# Feature Specification: Independent Credit Spread Carry

**Feature Branch**: `Codex/154-credit-spread-carry`
**Created**: 2026-08-23
**Status**: Implemented
**Input**: User description: "교정된 수익 엣지 기준으로 다음 우선순위 전략군까지 진행"

## User Scenarios & Testing

### User Story 1 - 독립적인 신용 위험 보상을 검증한다 (Priority: P1)

운영자는 국채 만기 캐리와 다른 원천인 우량 회사채의 추가 금리 보상이 실제 수익 엣지인지
확인한다. 후보는 결과를 보기 전에 네 가지 신호 문법과 64개 조합으로 고정한다.

**Why this priority**: 같은 국채 후보를 반복하는 대신 새로운 경제적 원천을 검증해야 탐색이 전진한다.

**Independent Test**: 고정 입력에서 정확히 64개의 고유 후보와 전략 지문이 생성되고 같은
개발 구간 승자가 재현된다.

**Acceptance Scenarios**:

1. **Given** 사전등록된 네 전략 문법, **When** 후보를 만들면, **Then** 정확히 64개이며 중복 ID와 지문이 없다.
2. **Given** 회사채와 국채 금리 이력, **When** 후보를 평가하면, **Then** 금리 보유수익과 금리 변화 가격효과 및 비용이 모두 반영된다.
3. **Given** 결과가 나온 뒤 새 매개변수를 추가함, **When** 같은 가족으로 제출하면, **Then** 기존 가족 결과에 섞지 않고 새 명세를 요구한다.

---

### User Story 2 - 공개자료와 시점 정합성을 지킨다 (Priority: P1)

운영자는 미국 재무부의 고품질 회사채 금리곡선과 국채 금리만 사용하며 각 판단 시점에
실제로 알려진 관측만 사용한다.

**Why this priority**: 미래 자료나 재배포 제약 자료를 쓰면 백테스트가 좋아도 운영 증거로 쓸 수 없다.

**Independent Test**: 미래 관측, 70일보다 오래된 최신 월간 자료, 120개월 미만 구간 중 하나라도
있으면 후보 승격이 브로커 접촉 전에 닫힌다.

**Acceptance Scenarios**:

1. **Given** 월간 HQM 10년·20년 회사채 금리와 일별 10년 국채 금리, **When** 월말 스냅샷을 만들면, **Then** 목표일 이후 관측은 사용하지 않는다.
2. **Given** 최신 회사채 자료가 발표 주기를 넘겨 오래됨, **When** 최신 신호를 만들면, **Then** 승격 증거를 발행하지 않는다.
3. **Given** 일부 회사채 자료가 누락됨, **When** 공장을 돌리면, **Then** 자료 관문이 실패 닫힘이다.

---

### User Story 3 - 교정된 계층형 관문으로 판정한다 (Priority: P1)

운영자는 이전 576회 연구를 감사 장부에 보존하되, 현재 회사채 64개만 하나의 통계 가족으로
검정한다. 1990~2006년 개발 구간에서 한 후보를 선택하고 한 달 격리 뒤 2007년 이후에는
그 후보만 확인한다.

**Why this priority**: 이전 오류처럼 이질적 연구를 한 가족으로 묶거나 홀드아웃에서 다시 고르면 안 된다.

**Independent Test**: 전체 감사는 640회, 현재 통계 가족은 64회이며 홀드아웃 값을 바꿔도 개발 승자 ID는 바뀌지 않는다.

**Acceptance Scenarios**:

1. **Given** 이전 576회와 현재 64회, **When** 판정하면, **Then** 감사 수는 640이고 DSR/PBO 입력은 현재 64개뿐이다.
2. **Given** 개발 승자가 고정됨, **When** 홀드아웃을 평가하면, **Then** 재선택 없이 혼합 PSR과 경제성만 확인한다.
3. **Given** 교정 보고서가 없거나 버전·코드 지문이 다름, **When** 판정하면, **Then** 승격은 거부된다.

---

### User Story 4 - 연구와 주문 준비가 같은 신호를 쓴다 (Priority: P2)

운영자는 연구에서 계산한 회사채·국채 목표 비중과 주문 미리보기에서 계산한 비중이 정확히
같아야 한다. 이 기능 자체는 실제 화이트리스트나 자본을 넓히지 않는다.

**Why this priority**: 백테스트한 전략과 주문하려는 전략이 다르면 수익 검증은 무의미하다.

**Independent Test**: 동일 정책과 최신 스냅샷은 같은 비중 다이제스트를 만들고, 후보·자료·코드·
전략 지문이 하나라도 다르면 브로커가 호출되지 않는다.

**Acceptance Scenarios**:

1. **Given** 동일 정책과 스냅샷, **When** 연구와 주문 준비가 계산하면, **Then** 목표 비중이 같다.
2. **Given** 현재 라이브 화이트리스트에 회사채 ETF가 없음, **When** 후보가 합격해도, **Then** 연구 캐너리 적격까지만 기록하고 실제 무장은 별도 경계 변경 전까지 막힌다.

---

### User Story 5 - 경제적으로 쓸모 있는 후보만 남긴다 (Priority: P2)

운영자는 회사채 전략을 기존 3자산 전략의 분산 보완재로 사전등록한다. 손대지 않은 홀드아웃에서
80/20 혼합 신뢰도, 샤프 개선, 낙폭 비악화, 낮은 상관, 50bp 비용 후 양수를 모두 요구한다.

**Why this priority**: 통계적으로 우연이 아니어도 계좌 전체를 개선하지 못하면 돈을 벌 전략으로 채택할 이유가 없다.

**Independent Test**: 어떤 차단 관문 하나라도 실패하면 선택 후보, 배포 설정, 자본, 주문이 모두 비어 있다.

**Acceptance Scenarios**:

1. **Given** 혼합 PSR 0.95 미만, **When** 판정하면, **Then** 불합격이다.
2. **Given** 혼합 샤프 개선 0.05 미만 또는 낙폭 악화, **When** 판정하면, **Then** 불합격이다.
3. **Given** 모든 차단 관문 통과, **When** 판정하면, **Then** 단 하나만 연구 캐너리 적격이며 기존 단계 승격을 별도로 거친다.

### Edge Cases

- HQM 월간 관측은 발표 전까지 마지막 공개 월을 사용하되 70일을 넘으면 오래된 자료로 거부한다.
- 회사채 금리에서 같은 만기 국채 금리를 뺀 스프레드가 음수여도 원자료로 보존하고 임의로 0으로 만들지 않는다.
- 수익 근사가 0 이하 월간 배수를 만들면 조용히 자르지 않고 입력 오류로 실패한다.
- 후보 수익률 상관행렬이 특이하거나 음의 평균 상관이면 유효 독립 시도 수를 보수적으로 제한한다.
- 이전 576회 감사 지문이 중복되거나 누락되면 현재 통계 계산과 별개로 승격을 막는다.
- `LQD`가 현재 주문 허용목록에 없으면 합격 결과도 주문 가능한 상태로 표현하지 않는다.

## Requirements

> **돈 경로·안전 경계 변경**: 이 기능은 후보 증거만 만든다. 합격 뒤에도 기존 한 주문당
> 위임 자본 50%, 종목당 60%, 전체 100%, 현금 1% 여유, 첫 연구 캐너리 NAV 10% 한도를
> 유지한다. 현재 허용목록, 자본, 실제 주문, 헌법, 커널은 변경하지 않는다.

### Functional Requirements

- **FR-001**: System MUST use public-domain U.S. Treasury HQM 10-year and 20-year high-quality corporate rates plus Treasury rates, with source, coverage, freshness, and publication status recorded.
- **FR-002**: System MUST create point-in-time monthly snapshots without future observations and require at least 120 development and 120 untouched holdout months.
- **FR-003**: System MUST preregister four credit-signal grammars and exactly 64 parameter combinations before evaluation.
- **FR-004**: System MUST model long-only high-quality corporate and Treasury sleeve returns with prior-month carry, duration price effect, and 10/25/50 basis-point turnover costs.
- **FR-005**: System MUST select one candidate using 1990-2006 development data only, apply a one-month embargo, and prohibit 2007+ holdout reselection.
- **FR-006**: System MUST reconstruct 576 unique prior trials as 256 production price candidates,
  192 exploratory replays, 64 macro candidates, and 64 Treasury candidates, then publish the 64
  current trials as a 640-record unique audit catalog. The historical trial ledger remains append-only,
  while repeated ledger batches MUST NOT count as independent trials.
- **FR-007**: System MUST calculate DSR and PBO from only the 64 current family candidates and report effective independent trial count.
- **FR-008**: System MUST treat development DSR 0.95 and PBO 0.10 as diagnostics and untouched blend PSR 0.95 as a blocking confirmation.
- **FR-009**: System MUST preregister the objective as `diversifier` and require correlation below 0.80, 80/20 blend Sharpe improvement of at least 0.05, and non-worsening blend drawdown.
- **FR-010**: System MUST require positive holdout total return after 50 basis points of turnover cost.
- **FR-011**: System MUST bind every decision to gate version, family, objective, candidate, strategy, data, code, split, and target-weight fingerprints.
- **FR-012**: System MUST use one shared target-weight function for research and order preparation.
- **FR-013**: System MUST reject stale, incomplete, legacy, mismatched, or partially failed evidence before broker access.
- **FR-014**: System MUST emit no selected candidate or deploy configuration when any blocking gate fails.
- **FR-015**: System MUST keep capital, real orders, live arming, whitelist, caps, secrets, constitution, and kernel unchanged.
- **FR-016**: System MUST require the existing `Backtest -> Canary -> Full` ladder after any pass and explicitly mark `LQD` as not currently live-authorized.
- **FR-017**: System MUST advance the next search family to independent foreign-exchange carry only if this complete family has no edge.

### Key Entities

- **CreditCurveSnapshot**: Point-in-time HQM corporate rates, Treasury rates, spreads, histories, completeness, and freshness.
- **CreditSpreadPolicy**: One preregistered signal grammar and its lookback, threshold, confirmation, and maximum credit weight.
- **CreditSpreadCandidate**: Candidate ID, policy, execution symbols, deploy text, and exact strategy fingerprint.
- **CreditFamilyEvidence**: The 64 aligned development and holdout returns plus family-local diagnostics.
- **CreditEdgeDecision**: Calibration, split, holdout confirmation, economic gates, global audit, parity evidence, and final eligibility.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Public collection publishes both HQM series with at least 500 observations and latest age no more than 70 days.
- **SC-002**: Candidate generation always produces exactly 64 unique IDs and 64 unique strategy fingerprints.
- **SC-003**: Production replay reports 640 global audit trials, 64 family trials, and an effective family count between 1 and 64.
- **SC-004**: Holdout changes never alter the development-selected candidate ID.
- **SC-005**: Any one failed blocking gate yields no candidate, no deploy configuration, no capital change, and no order.
- **SC-006**: Research and order preparation produce byte-equivalent target weights and matching digests for identical inputs.
- **SC-007**: Focused tests, full pytest, ruff, strict harness, handoff facts, production workflow, deployment, and KIS no-order smoke pass before completion.
- **SC-008**: The production result identifies either one fully qualified research candidate or a reproducible move to foreign-exchange carry without changing thresholds after seeing results.

## Assumptions

- HQM rates represent AAA, AA, and A U.S. corporate bonds and are a conservative proxy for an investment-grade credit sleeve.
- `LQD` is the intended execution representative, while `IEF` is the defensive Treasury sleeve; instrument-basis risk is reported and not hidden.
- The objective is diversification, not replacement of the incumbent 3-asset strategy.
- No live whitelist expansion is part of this feature even if the research candidate passes.

## Risk Classification

**Grade 4 - money path**. The result may nominate a future live strategy, but this feature itself cannot allocate
capital or submit orders and does not widen the safety perimeter.
