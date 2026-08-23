# Feature Specification: Independent Treasury Carry Factory

**Feature Branch**: `Codex/152-independent-asset-carry`
**Created**: 2026-08-23
**Status**: Planned - grammar frozen before first evaluation
**Input**: User description: "기존 시스템을 뿌리부터 재검토해 검증된 신규 투자 엣지를 끝까지 찾고, 다음 고도화를 모두 진행"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 기존 탐색과 다른 국채 만기 엣지를 한 번에 검증한다 (Priority: P1)

운영자는 기존 주식·중기채·금 가격 전략과 거시 비중 조절을 반복하지 않고, 미국 국채의
3개월·2년·5년·10년·30년 금리곡선에서 캐리, 롤다운, 금리 방향, 방어 바벨을 이용하는
장기 전용 후보를 자동으로 검증받는다.

**Why this priority**: 기존 512개 후보가 모두 탈락했으므로 같은 세 자산의 매개변수만 더
늘리면 우연한 승자를 만들 위험이 크다. 만기별 국채 회전은 투자 대상과 수익 원리가 다르다.

**Independent Test**: 후보 생성기를 실행하면 사전 등록된 네 전략군과 다섯 이진 선택의
곱으로 정확히 64개의 서로 다른 후보와 정책 지문이 만들어진다.

**Acceptance Scenarios**:

1. **Given** 후보 문법이 아직 평가되지 않음, **When** 공장을 실행하면, **Then** 정확히 64개
   후보만 완결 평가하고 부분 실행에서는 승자를 내지 않는다.
2. **Given** 동일 입력과 동일 문법, **When** 다시 실행하면, **Then** 후보 ID, 정책 지문,
   목표 비중과 판정이 동일하다.

---

### User Story 2 - 당시 알 수 있던 공식 금리만 사용한다 (Priority: P1)

운영자는 백테스트 날짜 뒤에 발표된 값이나 현재 수정값을 과거 판단에 끼워 넣지 않고,
각 월말까지 관측된 공식 미국 국채 금리만 다음 달 보유 결정에 사용한다.

**Why this priority**: 미래 정보가 한 달만 섞여도 금리 방향 전략의 성과가 크게 부풀 수 있다.

**Independent Test**: 관측일 이후 값을 주입하거나 최신 금리가 오래되거나 필수 만기가
빠지면 데이터 관문이 닫히고 승자가 발행되지 않는다.

**Acceptance Scenarios**:

1. **Given** 한 달의 목표 비중을 계산함, **When** 입력 계보를 검사하면, **Then** 그 달 시작
   이후의 금리 관측은 포함되지 않는다.
2. **Given** 최신 3개월·2년·5년·10년·30년 중 하나가 결측 또는 오래됨, **When** 실거래용
   증거를 만들면, **Then** 연구 결과와 무관하게 실거래 적격은 거부된다.

---

### User Story 3 - 모든 과거 탐색을 포함해 우연한 승자를 거른다 (Priority: P1)

운영자는 실패한 탐색을 지우지 않고 기존 가격 256회, 거시 사전 탐색 192회, 공식 거시
64회와 이번 64회를 합친 정확히 576회의 다중검정 벌점을 본다.

**Why this priority**: 여러 후보 중 가장 좋아 보이는 하나는 실제 엣지가 없어도 좋아 보일 수 있다.

**Independent Test**: 이전 512회 증거와 이번 64회가 모두 있을 때만 DSR과 PBO를 계산하며,
누락·중복·지문 충돌이 있으면 승자를 내지 않는다.

**Acceptance Scenarios**:

1. **Given** 이전 공장 증거가 512회보다 적음, **When** 새 공장을 실행하면, **Then** 결과는
   실패 닫힘이며 선택 후보가 없다.
2. **Given** 576개 지문이 모두 고유함, **When** 판정하면, **Then** 누적 시도 수를 576으로
   기록하고 같은 수를 DSR과 PBO에 사용한다.

---

### User Story 4 - 연구 신호와 주문 목표가 같은지 증명한다 (Priority: P2)

운영자는 합격 후보가 생기더라도 별도 번역 규칙으로 주문 비중이 달라지지 않도록, 연구와
주문 계획이 같은 목표 비중 함수를 사용하고 동일 지문을 남기는지 확인한다.

**Why this priority**: 좋은 백테스트와 다른 주문을 내면 백테스트 합격은 돈 경로의 근거가 아니다.

**Independent Test**: 동일 후보와 동일 최신 금리 스냅샷을 연구 경로와 주문 미리보기 경로에
입력했을 때 종목별 목표 비중과 지문이 정확히 일치한다.

**Acceptance Scenarios**:

1. **Given** 합격 후보와 신선한 공식 금리, **When** 두 경로를 비교하면, **Then** 목표 비중이
   완전히 같고 모두 0 이상이며 합계가 1 이하이다.
2. **Given** 후보 ID, 정책 지문, 데이터 지문 또는 코드 커밋이 다름, **When** 주문 증거를
   검증하면, **Then** 브로커 호출 전에 거부된다.

---

### User Story 5 - 승격 기준을 모두 넘은 후보만 다음 단계로 보낸다 (Priority: P2)

운영자는 국채 사다리 대조군보다 좋아 보이는 후보라도 기존 3자산 포트폴리오와 함께 쓸 때
분산 이득이 없거나 비용·낙폭·구간 안정성 관문을 통과하지 못하면 실거래 후보로 받지 않는다.

**Why this priority**: 독립 전략의 목적은 단독 수익뿐 아니라 전체 계좌의 위험 대비 수익 개선이다.

**Independent Test**: 하나의 수치 관문만 실패시켜도 판정은 `NO_FACTORY_EDGE`, 선택 후보와
실행 설정은 `null`, 자본과 주문은 0으로 유지된다.

**Acceptance Scenarios**:

1. **Given** 모든 데이터·통계·비용·분산·동일성 관문이 통과함, **When** 최종 판정하면,
   **Then** 단 하나의 후보만 연구 캐너리 적격으로 발행한다.
2. **Given** 어떤 관문이라도 실패함, **When** 최종 판정하면, **Then** 다음 전략군을 제시하되
   whitelist, 자본 사다리, 주문 허가는 바꾸지 않는다.

### Edge Cases

- 30년 금리의 2002~2006년 공백은 해당 시점의 30년 만기만 선택 불가로 처리하고 미래값으로 메우지 않는다.
- 한 달에 여러 일별 관측이 있으면 그 달 마지막으로 공개된 유효 관측만 다음 달 결정에 쓴다.
- 금리 변화로 근사 월수익이 -100% 이하가 되면 입력 또는 모델 오류로 실패하고 임의로 정상화하지 않는다.
- 이전 공장 JSON이 손상되었거나 512개의 구간 점수를 재구성할 수 없으면 새 후보를 평가해도 승자는 없다.
- 동일 생산 묶음은 append-only 장부에 다시 추가하지 않는다.
- 합격 후보가 없어도 생산 워크플로는 결과와 실패 관문을 발행하고 주문은 만들지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST collect and validate official 3-month, 2-year, 5-year, 10-year, and 30-year U.S. Treasury constant-maturity yields.
- **FR-002**: System MUST preserve observation dates and use only information available by each decision date.
- **FR-003**: System MUST model five long-only, unlevered maturity sleeves corresponding to cash-like, short, intermediate, medium-long, and long Treasury exposure.
- **FR-004**: System MUST freeze four families: carry-roll, carry-rate-trend, defensive-curve, and curve-barbell.
- **FR-005**: System MUST generate exactly 64 official candidates from four families multiplied by maximum maturity, lookback, selection width, and signal strength choices; every candidate ID and policy fingerprint MUST be unique.
- **FR-006**: System MUST charge turnover costs at 10, 25, and 50 basis points and use 25 basis points for ranking.
- **FR-007**: System MUST evaluate a development period before 2007 and an untouched holdout beginning in 2007, with at least 120 months in each side.
- **FR-008**: System MUST compare candidates with an equal-weight Treasury maturity ladder over the same dates and with the existing equal-weight stock, Treasury, and gold portfolio.
- **FR-009**: System MUST require a 20% candidate and 80% incumbent blend to improve annualized Sharpe by at least 0.05 without worsening maximum drawdown.
- **FR-010**: System MUST require candidate-to-incumbent monthly return correlation below 0.80.
- **FR-011**: System MUST carry forward exactly 512 prior unique trials and combine them with 64 current trials for exactly 576 multiplicity trials.
- **FR-012**: System MUST retain the existing DSR 0.95, PBO 0.10, PSR 0.95, segment win rate 60%, Sharpe superiority 0.20, Calmar superiority, 20% drawdown defense, and positive 50-basis-point return gates against the Treasury ladder benchmark.
- **FR-013**: System MUST use one deterministic target-weight function for research evaluation and order planning.
- **FR-014**: System MUST bind any eligible result to candidate ID, policy fingerprint, data fingerprint, code commit, and target-weight digest.
- **FR-015**: System MUST reject stale, incomplete, mismatched, duplicate, partial, or non-long-only evidence before any broker call.
- **FR-016**: System MUST publish machine-readable JSON, a Korean Markdown summary, current trial records, cumulative trial count, every gate, provisional best candidate, and next strategy family.
- **FR-017**: System MUST keep actual orders, fills, capital allocation, live arming, whitelist widening, caps, secrets, constitution, and kernel unchanged unless every gate passes and the existing Backtest -> Canary -> Full ladder separately authorizes progression.
- **FR-018**: System MUST suppress an identical completed production batch while preserving the append-only historical ledger.

### Key Entities *(include if feature involves data)*

- **TreasuryCurvePoint**: One official maturity yield with observation date, publication availability, value, source, and quality state.
- **TreasuryCurveSnapshot**: The five maturity values known at one decision date, with history and freshness state.
- **TreasuryCarryPolicy**: One frozen family and its maximum maturity, lookback, selection width, and signal strength.
- **TreasuryCarryCandidate**: Stable candidate ID, policy fingerprint, execution mapping, and deployable configuration text.
- **TreasuryTrialRecord**: Cost-adjusted performance, ten chronological segment scores, turnover, and strategy fingerprint for one candidate.
- **PriorTrialEvidence**: The exact 512-trial output from the preceding strategy factory.
- **TreasuryFactoryDecision**: The 576-trial statistics, benchmark and blend evidence, all gates, and either one eligible candidate or no winner.
- **LiveTreasuryEvidence**: Fresh snapshot and candidate/data/code/weight digests required before order planning.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Public-data production publishes all five maturity series with at least 1,500 valid observations each and current freshness within seven days.
- **SC-002**: Candidate generation always yields exactly 64 unique IDs and 64 unique policy fingerprints across all four families.
- **SC-003**: Final multiplicity accounting is exactly 512 prior plus 64 current equals 576 unique trials; any other count fails closed.
- **SC-004**: Historical decisions never consume observations after their decision date, and latest stale or missing inputs block live eligibility.
- **SC-005**: Research and order-preview target weights are byte-equivalent for the same candidate and snapshot.
- **SC-006**: A winner is emitted only when every statistical, cost, drawdown, diversification, data, and parity gate passes; otherwise selected candidate and deploy config are absent.
- **SC-007**: The complete 64-candidate evaluation and 576-trial decision finishes within 15 minutes.
- **SC-008**: Production execution publishes a complete no-order result and leaves capital, orders, fills, whitelist, and live arming unchanged when no winner exists.
- **SC-009**: Focused tests, the full test suite, lint, handoff fact check, strict agent harness, diff check, deployment, public-data run, factory run, and KIS no-order smoke all pass before completion is reported.

## Assumptions

- Official constant-maturity yields are suitable for a conservative rolling-par Treasury return approximation, but are not claimed to equal ETF total returns exactly.
- A candidate that passes the research gates still enters only the existing research/canary ladder; this feature does not skip directly to full live capital.
- The 30-year series gap is known and must remain explicit rather than backfilled from another maturity.
- Current low-price execution mappings may be added only for a fully passing candidate and still require quote, lot-size, whitelist, cap, and capital-ladder checks.
- No paid data service, leverage, short sale, option, futures contract, or margin is introduced.

## Risk Classification

**Grade 4 - money path**. This feature adds a strategy type that can eventually produce live target weights.
Implementation is allowed because the operator explicitly requested autonomous trading completion, but actual capital or orders remain governed by the unchanged staged gates and fail closed unless all evidence passes.
