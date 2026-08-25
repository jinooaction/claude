# Feature Specification: Paired Forward Edge Gate

**Feature Branch**: `Codex/159-strategy-usability-energy-replication`  
**Created**: 2026-08-25  
**Status**: In Progress  
**Input**: User description: "다음 우선순위를 진행하고, 전략이 정말 없는지와 합격 기준 오류를 끝까지 확인"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 같은 날의 초과수익을 검정한다 (Priority: P1)

운영자는 전략과 벤치마크를 서로 무관한 표본처럼 비교하지 않고, 같은 날짜의 전략 수익률에서
같은 날짜의 벤치마크 수익률을 뺀 능동 수익률로 우위를 판정한다.

**Why this priority**: 현재 방식은 추정된 벤치마크 샤프를 오차 없는 상수로 취급해 두 수익률의
공분산을 버린다. 그 결과 실제 초과수익이 일관돼도 합격 확률이 지나치게 낮아질 수 있다.

**Independent Test**: 공통 시장 충격은 크지만 능동 수익률이 일정한 짝지은 곡선을 평가하면,
공통 충격의 크기와 무관하게 같은 능동 PSR이 재현된다.

**Acceptance Scenarios**:

1. **Given** 같은 길이의 전략·벤치마크 곡선, **When** 판정하면, **Then** 기간별 전략 수익률에서 벤치마크 수익률을 뺀 능동 수익률의 PSR과 DSR을 사용한다.
2. **Given** 전략과 벤치마크에 동일한 시장 충격이 추가됨, **When** 능동 수익률이 변하지 않음, **Then** 벤치마크 대비 PSR도 변하지 않는다.
3. **Given** 서로 다른 길이의 곡선, **When** 판정하면, **Then** 잘못 짝지어 합격시키지 않고 데이터 부족으로 실패 닫힘한다.

---

### User Story 2 - 새 관문의 오탐과 미탐을 공개한다 (Priority: P1)

운영자는 결과가 마음에 든다는 이유로 계산을 바꾼 것이 아닌지 확인할 수 있도록, 48개 전진
관측을 닮은 고정 모의실험에서 기존 방식과 짝지은 방식의 오탐률과 검출률을 함께 본다.

**Why this priority**: 통계 수정은 특정 전략의 합격 여부가 아니라 대조군에서의 교정 성능으로
정당화돼야 한다.

**Independent Test**: 고정 시드로 무엣지와 사전 정의된 능동 샤프 1.50 시나리오를 반복하면
동일한 합격률 보고서가 재현된다.

**Acceptance Scenarios**:

1. **Given** 참 능동 수익이 0인 짝지은 표본, **When** PSR 0.95 관문을 반복 평가하면, **Then** 거짓 합격률은 6% 이하이다.
2. **Given** 참 능동 수익이 0인 짝지은 표본, **When** 연구 캐너리 PSR 0.80 관문을 반복 평가하면, **Then** 거짓 합격률은 명목 20%에서 허용 오차 3%포인트 이내이다.
3. **Given** 사전 정의된 능동 샤프 1.50, **When** 기존 방식과 새 방식을 비교하면, **Then** 새 방식의 검출률이 기존 방식보다 높고 차이가 수치로 남는다.

---

### User Story 3 - 전략의 절대 품질과 상대 우위를 함께 보존한다 (Priority: P2)

운영자는 초과수익 통계만 보고 위험한 전략을 합격시키지 않도록 전략 자체 샤프, 벤치마크 자체
샤프, 총 초과수익, 칼마와 최대낙폭을 계속 함께 확인한다.

**Why this priority**: 능동 수익률 PSR은 일관된 벤치마크 초과를 재지만, 절대 위험과 자본 방어는
별도 지표가 필요하다.

**Independent Test**: 능동 PSR이 높아도 전략 샤프가 벤치마크 이하이거나 총 초과수익이 음수인
곡선은 합격하지 않는다.

**Acceptance Scenarios**:

1. **Given** 능동 PSR이 임계값 이상, **When** 전략 샤프가 벤치마크보다 높고 총 초과수익도 양수, **Then** 기존 나머지 조건과 함께 합격할 수 있다.
2. **Given** 능동 PSR만 통과, **When** 절대·경제성 조건 중 하나가 실패, **Then** `NO_EDGE`를 유지한다.
3. **Given** 판정 JSON, **When** 운영자가 읽음, **Then** 통계 방법과 버전을 구버전 결과와 구별할 수 있다.

---

### User Story 4 - 기존 승격 사다리를 그대로 거친다 (Priority: P2)

운영자는 보정된 판정이 특정 전략을 합격시켜도 주문이나 자본이 즉시 열리지 않고 기존
`Backtest -> Canary -> Full` 단계와 지문·계좌·위험 관문을 그대로 거치게 한다.

**Why this priority**: 통계 오류 수정이 안전장치 우회로 변하면 안 된다.

**Independent Test**: 보정된 `EDGE_CONFIRMED`를 입력해도 다른 필수 증거가 없으면 돈 경로는
브로커 호출 전에 실패 닫힘한다.

**Acceptance Scenarios**:

1. **Given** 보정된 전진 판정, **When** 생산 루프가 읽음, **Then** 기존 PSR 임계값, 최소 관측, 칼마, 전략 지문과 캐너리 관문을 모두 요구한다.
2. **Given** 구버전 또는 통계 방법이 없는 판정, **When** 새 결과로 승격을 시도, **Then** 새 관문 증거로 가장하지 않는다.
3. **Given** 코드 배포 완료, **When** 전진 트랙을 다시 판정, **Then** 결과와 돈 경로 상태를 주문 없이 보고한다.

### Edge Cases

- 전략·벤치마크 곡선 길이가 다르거나 기간 수익률 수가 다르면 짝을 임의로 자르지 않는다.
- 능동 수익률의 분산이 0이면 무한 정보비율로 합격시키지 않고 통계 계산 불가로 처리한다.
- 벤치마크가 없으면 기존 절대 수익 PSR 경로를 유지하되 상대 우위로 표현하지 않는다.
- 다중 시도 보정값이 주어지면 DSR도 전략 절대수익이 아니라 같은 능동 수익률에 적용한다.
- 통계 보정 뒤 기존 후보가 계속 실패해도 임계값을 결과에 맞춰 낮추지 않는다.
- 생산 전진 데이터가 외부 워커에만 있으면 코드 배포 뒤 같은 워커에서 재판정하고 실행 지문을 남긴다.

## Requirements *(mandatory)*

> **돈 경로·안전 경계 변경**: 이 기능은 승격 증거 계산을 바꾸는 등급 4 변경이다. 실제 주문,
> 자본 한도, 허용 종목, 비밀값, 감사 로그, 장중 배포 제한과 `Backtest -> Canary -> Full`은
> 바꾸지 않는다.

### Functional Requirements

- **FR-001**: System MUST compute paired active returns as strategy period return minus benchmark period return on exactly aligned observations.
- **FR-002**: System MUST compute benchmark-relative PSR, MinTRL, and optional DSR from paired active returns against a zero benchmark.
- **FR-003**: System MUST continue to compute strategy and benchmark absolute Sharpe ratios from their own return series.
- **FR-004**: System MUST continue to require positive total excess return and strategy Sharpe above benchmark Sharpe in addition to active-return significance.
- **FR-005**: System MUST fail closed when paired curves or return arrays have different lengths, fewer than the minimum observations, or zero active-return variance.
- **FR-006**: System MUST preserve the no-benchmark absolute-return path without labeling it paired benchmark evidence.
- **FR-007**: System MUST retain existing paper and live PSR thresholds of 0.80 and 0.95; this feature MUST NOT tune thresholds to pass a named strategy.
- **FR-008**: System MUST publish a deterministic 48-observation calibration comparing legacy fixed-benchmark-Sharpe inference with paired active-return inference.
- **FR-009**: Calibration MUST report null false acceptance at both 0.80 and 0.95 plus planted-edge detection for both methods.
- **FR-010**: Paired live-threshold null false acceptance MUST be at most 6% over at least 2,000 repetitions.
- **FR-011**: Paired paper-threshold null false acceptance MUST remain within 17% to 23% over at least 2,000 repetitions.
- **FR-012**: Paired planted-edge detection MUST exceed legacy planted-edge detection under the preregistered correlated scenario.
- **FR-013**: Every verdict MUST expose a schema version and significance method that distinguish paired evidence from legacy evidence.
- **FR-014**: Downstream money-path readers MUST reject missing or legacy significance-method evidence when paired evidence is required for new promotion.
- **FR-015**: System MUST preserve existing minimum observations, Calmar, fingerprint, hardened-canary, account, position-cap, whitelist, and broker safety gates.
- **FR-016**: System MUST not call a broker, create an order, or allocate capital during calibration, testing, or evidence regeneration.
- **FR-017**: Production verification MUST rerun the deployed forward verdict and report the resulting strategy eligibility and money-path state.
- **FR-018**: Rollback MUST be possible by reverting the paired-gate commit; missing new evidence after rollback MUST fail closed rather than reuse stale paired results.

### Key Entities

- **PairedActiveReturnEvidence**: Aligned strategy and benchmark returns, active-return information ratio, PSR, DSR, MinTRL, method, and version.
- **ForwardGateCalibrationReport**: Fixed scenario, thresholds, null false-acceptance rates, planted-edge detection rates, and pass/fail state.
- **EdgeVerdictV12**: Existing absolute and drawdown metrics plus explicitly versioned paired significance evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Adding an identical market-return sequence to both strategy and benchmark changes paired PSR by exactly 0 at serialized precision.
- **SC-002**: Misaligned paired curves produce `INSUFFICIENT_DATA` in 100% of tests and never `EDGE_CONFIRMED`.
- **SC-003**: Fixed-seed calibration is byte-reproducible and finishes in under 10 seconds locally.
- **SC-004**: At least 2,000 null repetitions produce paired PSR 0.95 false acceptance at or below 6% and paired PSR 0.80 false acceptance between 17% and 23%.
- **SC-005**: The preregistered planted-edge scenario shows higher detection under paired inference than legacy inference.
- **SC-006**: Existing no-benchmark, drawdown, deterministic, and serialization tests continue to pass.
- **SC-007**: Focused tests, full pytest, ruff, strict harness, handoff facts, PR quality gate, deployment, production forward replay, KIS no-order smoke, and money-path truth check complete before final closure.
- **SC-008**: No code path added by this feature imports a broker client, sends an order, changes a whitelist, or raises a capital limit.

## Assumptions

- The forward strategy and buy-and-hold benchmark are sampled on the same NAV dates in production.
- `strategy return - benchmark return` is the existing product question's active return; it does not claim to be a robust bootstrap test of the exact difference between two Sharpe ratios.
- The separate strategy-Sharpe-above-benchmark check remains because active-return significance and absolute risk-adjusted quality answer different questions.
- Paper PSR 0.80 is an early evidence threshold with a nominal one-sided 20% false-positive rate, not proof for full capital.
- The current `global-trend-fixed` result is not used to choose the statistic or threshold; positive and null controls determine correctness first.

## Risk Classification

**Grade 4 - money path**. The evidence used by an existing capital ladder can change. This feature does not
authorize real orders or capital by itself, and all staged promotion and execution safety gates remain mandatory.
