# Feature Specification: Independent FX Carry and Gate Power

**Feature Branch**: `Codex/155-fx-carry-gate-power`
**Created**: 2026-08-24
**Status**: Preregistered
**Input**: User description: "독립적인 외환 금리차 전략군을 사전등록하고 즉시 백테스트하며, 합격 기준 자체의 오류나 둔감함도 다시 검증"

## User Scenarios & Testing

### User Story 1 - 외환 금리차라는 독립 수익 원천을 검증한다 (Priority: P1)

운영자는 주식·채권·금·회사채와 다른 원천인 국가별 단기금리 차이와 환율 움직임이
실제로 반복 가능한 수익 우위인지 확인한다. 결과를 보기 전에 네 전략 문법과 16개 조합을 고정한다.

**Why this priority**: 같은 자산과 매개변수를 반복하지 않고 경제적 원인이 다른 후보를 시험해야 한다.

**Independent Test**: 고정 입력에서 정확히 16개 고유 후보와 전략 지문이 생성되고 개발 구간 승자가 재현된다.

**Acceptance Scenarios**:

1. **Given** 사전등록된 네 문법과 두 신호 창·두 최대 외화 비중, **When** 후보를 만들면, **Then** 정확히 16개이며 ID와 지문이 모두 고유하다.
2. **Given** AUD·CAD·JPY·GBP·USD 금리와 환율, **When** 월별 수익을 만들면, **Then** 전월 금리 수익·환율 손익·10/25/50bp 회전 비용을 모두 반영한다.
3. **Given** 생산 결과가 나온 뒤 새 매개변수를 추가함, **When** 재제출하면, **Then** 같은 가족에 섞지 않고 새 명세와 새 감사 횟수를 요구한다.

---

### User Story 2 - 시점 기준 공개자료와 통화 방향을 정확히 지킨다 (Priority: P1)

운영자는 연준 H.10 일별 환율과 OECD 단기금리의 FRED 전송본을 사용하고, 각 판단 시점에
알려진 이전 월 자료만 사용한다. 통화마다 다른 환율 표기 방향도 명시적으로 변환한다.

**Why this priority**: 미래 자료, 반대 환율 방향, 오래된 금리는 가짜 수익을 만들 수 있다.

**Independent Test**: 미래 관측, 100일보다 오래된 금리, 14일보다 오래된 환율, 방향 변환 오류 중 하나라도 있으면 승격이 닫힌다.

**Acceptance Scenarios**:

1. **Given** 직접 표기 AUD·GBP와 역표기 CAD·JPY, **When** 달러 기준 통화가치를 만들면, **Then** 같은 방향의 USD 가치로 정규화된다.
2. **Given** 목표 월의 금리 발표값, **When** 그 월 신호를 만들면, **Then** 해당 값은 사용하지 않고 이전 공개 월까지만 사용한다.
3. **Given** 자료가 누락·오래됨·불연속임, **When** 공장을 돌리면, **Then** 자료 관문이 실패 닫힘이다.

---

### User Story 3 - 합격 기준이 좋은 전략을 알아보는지 검증한다 (Priority: P1)

운영자는 무신호와 연율 샤프 0.20~0.80을 심은 신호를 반복 투입해 가족 크기 16과 64에서
거짓 합격률, 후보 선택률, 최종 검출력을 확인한다.

**Why this priority**: 합격자가 계속 0일 때 전략 문제와 검사기 문제를 숫자로 분리해야 한다.

**Independent Test**: 고정 시드에서 라이브 관문의 무신호 거짓 합격률은 5% 이하이고,
샤프 0.60 신호 검출력은 80% 이상이며 전체 검출력 곡선이 재현된다.

**Acceptance Scenarios**:

1. **Given** 무신호 후보 가족, **When** 500회 반복하면, **Then** 라이브 거짓 합격률은 5% 이하이다.
2. **Given** 샤프 0.20~0.80 신호, **When** 같은 관문을 반복하면, **Then** 신호별 선택률과 검출률을 모두 기록한다.
3. **Given** 샤프 0.60 검출력이 80% 미만, **When** 외환 판정을 요청하면, **Then** 전략 결과와 무관하게 승격을 차단한다.

---

### User Story 4 - 유망 후보를 버리지 않고 무자본으로 전진시킨다 (Priority: P2)

운영자는 라이브 신뢰도 0.95를 낮추지 않는다. 대신 홀드아웃 PSR 0.80 이상이고 비용 후
양수이며 계좌 혼합을 악화시키지 않는 후보는 `PAPER_CHALLENGER`로 보존해 자동 종이검증에 넘긴다.

**Why this priority**: 중간 신뢰 후보를 완전 탈락시키면 자동화가 학습할 증거를 축적하지 못한다.

**Independent Test**: PSR 0.80~0.95 후보는 자본·주문·허용목록 없이 종이 후보만 발행하고,
0.95 이상 모든 라이브 관문 통과 후보만 연구 캐너리 적격이 된다.

**Acceptance Scenarios**:

1. **Given** PSR 0.80 이상 0.95 미만과 완화 없는 경제 관문, **When** 판정하면, **Then** `PAPER_CHALLENGER`만 발행한다.
2. **Given** PSR 0.95 이상과 모든 차단 관문, **When** 판정하면, **Then** `FACTORY_EDGE` 연구 캐너리 후보 하나를 발행한다.
3. **Given** PSR 0.80 미만 또는 비용 후 손실, **When** 판정하면, **Then** 후보를 발행하지 않는다.

---

### User Story 5 - 연구와 주문 준비의 차이를 숨기지 않는다 (Priority: P2)

운영자는 합성 외화 현금 수익과 미국 상장 통화 ETF 사이의 기초 위험을 명시한다. 연구와
주문 준비는 같은 목표 비중 함수를 쓰지만, 별도 허용목록 승인 전에는 실제 주문이 불가능하다.

**Why this priority**: 백테스트 수익과 거래 상품 수익이 다를 수 있으므로 실행 가능성을 과장하면 안 된다.

**Independent Test**: 같은 정책·스냅샷은 같은 목표 비중 다이제스트를 만들고, 자료·코드·지문·허용목록 중 하나라도 다르면 브로커 호출 전에 거부된다.

**Acceptance Scenarios**:

1. **Given** 같은 정책과 최신 스냅샷, **When** 연구와 주문 준비가 계산하면, **Then** 비중이 바이트 단위로 같다.
2. **Given** FXA·FXC·FXY·FXB·UUP가 현재 라이브 허용목록에 없음, **When** 후보가 합격해도, **Then** 실제 무장은 별도 안전 경계 변경 전까지 막힌다.

### Edge Cases

- 월말이 휴일이면 그 이전의 마지막 환율만 사용한다.
- 음수 단기금리는 원자료로 보존하고 0으로 자르지 않는다.
- 역표기 통화의 환율이 0 이하이면 조용히 보정하지 않고 실패한다.
- 선택할 양의 외화 점수가 없거나 위기 방어 조건이면 USD 100%로 둔다.
- 후보 상관행렬이 특이하면 유효 독립 시도 수를 1~가족 크기로 제한한다.
- 과거 640개 감사 지문이 누락·중복이면 현재 통계와 별개로 승격을 막는다.
- `PAPER_CHALLENGER`는 어떤 경우에도 실자본·브로커 접근 권한을 갖지 않는다.

## Requirements

> **돈 경로·안전 경계 변경**: 이 기능은 연구 및 무자본 종이 후보만 만든다. 라이브
> 0.95 관문, NAV 10% 연구 캐너리, 기존 포지션 한도·현금 여유·손실 차단·허용목록·
> `Backtest -> Canary -> Full`은 유지한다. 실제 주문, 자본, 헌법, 커널은 변경하지 않는다.

### Functional Requirements

- **FR-001**: System MUST use FRED-delivered Federal Reserve H.10 spot rates and OECD immediate rates for AUD, CAD, JPY, GBP, and USD with source, units, coverage, freshness, and citation requirements recorded.
- **FR-002**: System MUST normalize direct and inverse exchange-rate quotations to USD value per foreign-currency unit.
- **FR-003**: System MUST create point-in-time monthly snapshots with prior-month rate publication lag, no future observations, spot age no more than 14 days, rate age no more than 100 days, at least 120 development months, one embargo month, and at least 120 untouched holdout months.
- **FR-004**: System MUST preregister four economic grammars and exactly 16 parameter combinations before evaluation.
- **FR-005**: System MUST model unlevered long-only foreign-cash and USD-cash factors with prior-month interest, spot movement, and 10/25/50 basis-point turnover costs.
- **FR-006**: System MUST select one candidate using 1990-2006 development data only and prohibit holdout reselection.
- **FR-007**: System MUST preserve 640 unique prior audit records, add 16 current records, and publish a 656-record unique audit catalog while using only the 16 current candidates for family statistics.
- **FR-008**: System MUST report effective independent trials, development DSR/PBO diagnostics, untouched holdout excess PSR, standalone economics, and 80/20 incumbent blend utility.
- **FR-009**: System MUST publish deterministic gate power curves for planted annual Sharpe 0.20, 0.30, 0.40, 0.50, 0.60, and 0.80 for family sizes 16 and 64.
- **FR-010**: System MUST block live eligibility unless null false acceptance is no more than 5%, planted Sharpe 0.60 detection is at least 80%, and holdout PSR is at least 0.95.
- **FR-011**: System MUST classify a no-capital `PAPER_CHALLENGER` only when holdout PSR is at least 0.80, 50bp cost return is positive, incumbent correlation is below 0.80, blend Sharpe does not decline, and blend drawdown is no worse than 120% of incumbent drawdown.
- **FR-012**: System MUST require live `FACTORY_EDGE` to satisfy holdout PSR 0.95, positive 50bp return, correlation below 0.80, blend Sharpe improvement at least 0.05, and non-worsening blend drawdown.
- **FR-013**: System MUST bind every decision to gate, family, objective, candidate, strategy, data, code, split, and target-weight fingerprints.
- **FR-014**: System MUST use one shared target-weight function for research and optional order preparation.
- **FR-015**: System MUST reject stale, incomplete, legacy, mismatched, partially failed, or non-whitelisted evidence before broker access.
- **FR-016**: System MUST keep capital, real orders, live arming, whitelist, caps, secrets, constitution, and kernel unchanged.
- **FR-017**: System MUST publish the immediate production result and either one live-grade candidate, one paper-only challenger, or a reproducible no-edge conclusion without threshold changes after observing returns.

### Key Entities

- **FxCarrySnapshot**: Point-in-time USD-normalized spot levels, short rates, histories, observation dates, completeness, and freshness.
- **FxCarryPolicy**: One fixed family, signal lookback, maximum foreign allocation, and selection count.
- **FxCarryCandidate**: Candidate ID, policy, execution representatives, exact strategy fingerprint, and basis-risk disclosure.
- **GatePowerEvidence**: Null false acceptance, planted-edge selection and detection curves by family size and signal strength.
- **FxCarryDecision**: Audit, calibration, split, holdout, economics, parity, and `FACTORY_EDGE`/`PAPER_CHALLENGER`/`NO_FACTORY_EDGE` result.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Production collection provides five rate series with at least 400 observations and four spot series with at least 14,000 observations, within their freshness limits.
- **SC-002**: Candidate generation always produces exactly 16 unique IDs and fingerprints.
- **SC-003**: Production replay reports 656 global audit trials, 16 family trials, and an effective family count between 1 and 16.
- **SC-004**: Fixed-seed calibration holds live false acceptance at 5% or less and Sharpe 0.60 detection at 80% or more for both 16 and 64 candidate families.
- **SC-005**: Holdout changes never alter the development-selected candidate ID.
- **SC-006**: Any live blocking failure yields no live candidate, no deploy configuration, no capital, and no order.
- **SC-007**: A paper-only challenger is machine-distinguishable from live eligibility and cannot pass broker evidence validation.
- **SC-008**: Focused tests, full pytest, ruff, strict harness, handoff facts, production workflow, deployment, and KIS no-order smoke pass before completion.

## Assumptions

- Foreign-cash total returns approximate an unlevered currency deposit and are not identical to CurrencyShares ETF returns.
- FXA, FXC, FXY, FXB, and UUP are execution representatives only; none is added to the live whitelist in this feature.
- The strategy objective is an alternative return and diversification sleeve, not replacement of the incumbent portfolio.
- The 0.80 paper threshold accepts more false leads because it moves no money and exists only to gather new forward evidence.

## Risk Classification

**Grade 4 - money path**. The result may nominate a future strategy, but this feature cannot allocate capital,
submit orders, or widen the safety perimeter.
