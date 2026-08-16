# Feature Specification: Uncertainty-Aware ML Edge Ensemble

**Feature Branch**: `Codex/145-ml-edge-ensemble`  
**Created**: 2026-08-16  
**Status**: Implemented  
**Input**: User description: "수익 전략을 더 고도화하고 AI 기술과 자동 매매의 장점을 살려라."

## User Scenarios & Testing

### User Story 1 - 비용 차감 AI 후보 검증 (Priority: P1)

운영자는 단순 이동평균 대신 시장 상태와 여러 가격·거시 특징을 학습하는 후보가 미래 누출 없는 표본 외 구간에서 기존 전략보다 실제로 나은지 확인한다.

**Why this priority**: 자동 주문보다 먼저 수익 신호가 우연이 아닌지 증명해야 한다.

**Independent Test**: 고정된 월간 주식·채권·금 자료를 입력하면 같은 AI 후보 보고서가 생성되고, 각 예측은 그 시점 이전 자료만 학습했으며 10·25·50bp 비용 결과가 함께 나온다.

**Acceptance Scenarios**:

1. **Given** 1971년 이후 정렬된 3자산과 거시 자료, **When** 확장형 워크포워드를 실행하면, **Then** 정규화 선형 모델·비선형 부스팅 모델·앙상블의 완전 표본 외 예측과 비중이 생성된다.
2. **Given** 두 모델의 예측 불일치나 큰 검증 오차, **When** 비중을 만들면, **Then** 기존 추세 비중을 유지하고 AI 기울기를 줄인다.
3. **Given** 미래 자료를 학습 입력에 섞은 인덱스, **When** 검증하면, **Then** 실행은 실패 폐쇄한다.

---

### User Story 2 - 자동 주기 연구 (Priority: P2)

운영자는 사람이 다시 실행하지 않아도 최신 공개 자료로 AI 후보가 정기 재학습·재평가되고 결과가 사이드카에 남기를 원한다.

**Why this priority**: AI의 장점은 한 번의 백테스트가 아니라 새 데이터에 따른 반복 학습과 감시다.

**Independent Test**: 수동 workflow 실행이 주문 없이 JSON·Markdown·후보 패키지를 발행하고, 실패 시 이전 성공을 새 성공처럼 덮어쓰지 않는다.

**Acceptance Scenarios**:

1. **Given** 정상 공개 자료, **When** 주기 실행하면, **Then** 모델·데이터 지문, 학습 종료일, 비용별 성과, 레짐별 성과와 판정이 발행된다.
2. **Given** 자료 누락 또는 모델 오류, **When** 실행하면, **Then** `BLOCKED`와 원인이 발행되고 실주문·전략 교체는 0건이다.

---

### User Story 3 - 증거 기반 자동 후보 등록 (Priority: P3)

운영자는 AI 후보가 엄격한 기준을 통과했을 때만 기존 후보·승격 루프가 읽을 수 있는 패키지로 자동 등록되기를 원한다.

**Why this priority**: 좋은 모델 결과가 자동화와 연결되어야 하지만 검증 없는 AI 판단이 돈 경로를 우회해서는 안 된다.

**Independent Test**: 기준 통과 보고서는 `strategy_backtest` 후보 패키지를 만들고, 기준 미달 보고서는 `NO_EDGE`로 남으며 어느 경우에도 live 설정·센티넬·자본을 수정하지 않는다.

**Acceptance Scenarios**:

1. **Given** 모든 사전 등록 기준 통과, **When** 후보 패키지를 만들면, **Then** 정확한 모델·자료·특징 지문과 재현 명령이 포함된다.
2. **Given** 하나 이상의 기준 미달, **When** 패키지를 만들면, **Then** 자동 승격 가능 후보가 생성되지 않고 실패 기준이 명시된다.

### Edge Cases

- 120개월 미만 학습 자료, 한 자산 결측, 중복 월, 비양수 가격은 `BLOCKED_DATA`다.
- 한 모델만 학습 가능하면 앙상블을 성공으로 위장하지 않고 `BLOCKED_MODEL`이다.
- 예측 하한이 모두 0 이하면 AI 기울기는 0이 되고 기존 추세 비중만 유지한다.
- 단일 자산 비중은 40%, 총투자 비중은 99%를 넘지 않는다.
- 결과가 좋아도 비용 25bp, 다중 시도 보정, 최소 워크포워드 승률을 통과하지 못하면 `NO_EDGE`다.

## Requirements

> **돈 경로·안전 경계 변경**: 이 기능은 연구·후보 등록까지만 수행한다. live 설정, 주문, 자본, 허용 종목, 캡, 센티넬을 수정하지 않는다.

### Functional Requirements

- **FR-001**: System MUST build lagged price, volatility, drawdown, correlation, inflation, valuation, and rate features using information available at each prediction date only.
- **FR-002**: System MUST use an expanding walk-forward split with at least 120 training months, a purge gap, and disjoint test folds.
- **FR-003**: System MUST train one regularized linear model and one shallow nonlinear boosting model with deterministic settings.
- **FR-004**: System MUST estimate model uncertainty from validation residuals and model disagreement, and reduce the AI tilt toward a lower-confidence forecast.
- **FR-005**: System MUST constrain weights to long-only, at most 40% per asset, at most 99% total, with the remainder in cash.
- **FR-006**: System MUST deduct realized turnover costs at 10, 25, and 50 basis points and report each separately.
- **FR-007**: System MUST compare against both equal-weight buy-and-hold and the incumbent 3-asset trend ensemble over identical dates.
- **FR-007A**: System MUST retain the incumbent trend allocation as the base and blend toward ML weights only in proportion to measured forecast confidence.
- **FR-008**: System MUST report total return, CAGR, Sharpe, Calmar, maximum drawdown, turnover, fold wins, model errors, prediction coverage, and regime slices.
- **FR-009**: `ML_EDGE_CANDIDATE_READY` MUST require all of: at least 20 disjoint test folds, positive 25bp net CAGR, Sharpe at least 0.20 above both benchmarks, PSR at least 0.95, DSR at least 0.95 across tested variants, fold win rate at least 60%, maximum drawdown no worse than the better benchmark, and positive 50bp net return.
- **FR-010**: Missing or contradictory data, chronology, model, cost, benchmark, or significance evidence MUST fail closed.
- **FR-011**: System MUST emit JSON, Markdown, and a machine-readable candidate package with data/model/feature fingerprints and a replay command.
- **FR-012**: A scheduled and manually dispatchable workflow MUST refresh the report without submitting or cancelling orders.
- **FR-013**: Candidate integration MUST remain read-only and MUST NOT alter live strategy, capital rung, whitelist, caps, signing material, or order sentinels.
- **FR-014**: Any future live use MUST still pass exact fingerprint identity, hardened canary, forward evidence, and the existing Backtest → Canary → Full path.

### Key Entities

- **Feature Snapshot**: one prediction date, asset, lagged features, target date, and target return.
- **Model Fold**: one expanding training window, purge gap, disjoint test window, model errors, and predictions.
- **Allocation Decision**: expected return, uncertainty, lower-confidence forecast, constrained asset weights, cash weight, and turnover.
- **ML Edge Report**: model, benchmark, cost-stress, regime, significance, gate, and fingerprint evidence.
- **Candidate Package**: replayable no-live strategy candidate consumed by existing autonomous research loops.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Repeated runs over identical inputs produce byte-stable decision and metric fields.
- **SC-002**: Tests prove every test target date is later than every label date used to train its model.
- **SC-003**: At least 20 disjoint out-of-sample folds and all three cost assumptions are reported.
- **SC-004**: A synthetic predictable dataset passes candidate gates while shuffled/noise data does not.
- **SC-005**: Workflow and module tests prove zero imports or calls into broker order submission and zero live-file writes.
- **SC-006**: Current real historical data yields an honest `ML_EDGE_CANDIDATE_READY`, `NO_EDGE`, or `BLOCKED` verdict without manual interpretation.

## Assumptions

- Initial scope uses monthly U.S. equity, 10-year Treasury, gold, CPI, earnings, dividends, and long-rate history from existing project sources.
- The first implementation prioritizes low-capacity, regularized tabular models over reinforcement learning because the available clean historical sample is small.
- AI research output can become a challenger, but live reassignment remains governed by the existing constitutional five-gate path.
