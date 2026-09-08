# 데이터 모델: 모바일 자금·전략 운영판

## 공통 규칙

- 모든 문서는 `read_only: true`여야 한다.
- 금액은 JSON 숫자가 아니라 정밀도를 보존한 USD 문자열 또는 `null`이다.
- `0`은 원천 측정이 성공했고 측정 범위와 시각이 있을 때만 유효하다.
- 요약이 누락·손상되면 해당 요약만 사용할 수 없으며 기존 생존 상태는 계속 해석한다.
- 신선도는 `as_of_utc`, `max_age_minutes`, 현재 기기 시각으로 계산한다. 미래 시각은
  `UNKNOWN`이다.

## CapitalSummary

| 필드 | 형식 | 의미 |
|---|---|---|
| `schema_version` | `"1.0"` | 자금 요약 계약 버전 |
| `as_of_utc` | UTC 문자열/`null` | 자금 원천 기준 시각 |
| `max_age_minutes` | 양의 정수 | 신선도 허용 시간 |
| `account` | AccountVerification | 비공개 계좌 집계 상태 |
| `live_allocation` | LiveAllocation | 현재 저빈도 운용 한도 |
| `intraday_budget` | IntradayBudget | 단타 준비 전용 예산 |
| `performance` | StrategyPerformance | 현재 전략 범위 체결·투자·손익 |
| `risk` | RiskBudget | 현재 운용 경로의 낙폭 한도 |

### AccountVerification

- `status`: `VERIFIED | UNVERIFIED | UNAVAILABLE`
- `total_assets_usd`, `purchasable_cash_usd`, `holdings_market_value_usd`: 검증 전 `null`
- `currency`: `USD`
- `reason_code`: 기계 판독 가능한 정제 사유
- `reason_ko`: 계좌번호나 원시 응답이 없는 한글 설명
- `protection`: `DEVICE_AUTH_REQUIRED`

상태 전이: `UNVERIFIED -> VERIFIED`는 별도 계좌 집계 계약과 인증된 비공개 조회 경로가
모두 검증된 경우에만 가능하다. 이 기능은 전이를 수행하지 않는다.

### LiveAllocation

- `status`, `stage`, `rung`, `capital_pct`, `allocated_capital_usd`
- `can_submit_real_orders`, `next_scheduled_live_utc`
- `detail_ko`: 알파 미확정과 운영 검증 목적을 포함한 정제 설명

### IntradayBudget

- `status`: 현재 `PREPARATION_ONLY`
- `capital_limit_usd`, `order_limit_usd`, `symbol_limit_usd`
- `total_exposure_limit_usd`, `daily_stop_trigger_usd`
- `orders_enabled`, `confirmed_on`

### StrategyPerformance

- `status`, `measurement_scope`, `observed_at_utc`
- `fills_count`, `gross_invested_usd`, `realized_pnl_usd`
- `unrealized_pnl_usd`, `total_pnl_usd`, `return_pct`

### RiskBudget

- `reference_rung`, `current_drawdown_pct`, `demote_drawdown_pct`, `halt_drawdown_pct`
- `loss_at_demote_usd`, `loss_at_halt_usd`

## StrategySummary

| 필드 | 형식 | 의미 |
|---|---|---|
| `schema_version` | `"1.0"` | 전략 요약 계약 버전 |
| `as_of_utc` | UTC 문자열/`null` | 전략 원천 기준 시각 |
| `max_age_minutes` | 양의 정수 | 신선도 허용 시간 |
| `active` | ActiveStrategy | 실제 운영 검증 중 전략 |
| `intraday` | PreparationStrategy | 준비만 승인된 단타 경로 |
| `research` | ResearchStrategy | 주문 없는 연구 공장 상태 |
| `last_execution` | ExecutionSummary | 최근 저빈도 실행 결과 |

### ActiveStrategy

- `strategy_id`: 원천에서 확인된 정확한 식별자
- `role`: `OPERATIONAL_CANARY`
- `entry_route`, `alpha_confirmed`, `rung`, `capital_pct`, `capital_limit_usd`
- `target_symbols`: 정제된 허용 주문 대상
- `forward_observations.current|required`, `forward_psr.current|required`
- `promotion_status`, `blockers_ko`

### PreparationStrategy

- `strategy_id`: `intraday-kis-execution`
- `role`: `PREPARATION_ONLY`
- `status`, `live_eligible`, `orders_enabled`, `orders_submitted`
- `capital_limit_usd`, `blockers`

### ResearchStrategy

- `role`: `RESEARCH_ONLY`
- `status`, `candidate_id`, `observed_at_utc`, `detail_ko`
- 후보가 없거나 원천이 오래되면 이를 활성 전략으로 대체하지 않는다.

### ExecutionSummary

- `timestamp_utc`, `event`, `status`, `preflight_ok`, `preflight_reason`
- `accepted_or_filled_count`, `broker_rejected_count`, `next_scheduled_utc`

## PrivacyGateState (앱 내부 전용)

- `isSupported`, `isUnlocked`, `isShieldVisible`, `lastFailure`
- 앱 시작: 잠금.
- 자금 탭 진입: 인증 요청은 사용자 동작 뒤 수행.
- 인증 성공: 현재 전면 세션에서만 잠금 해제.
- 인증 실패·취소·지원 불가: 잠금 유지.
- `inactive|paused|detached|hidden`: 즉시 잠금+보호막.
- `resumed`: 보호막 제거, 자금은 계속 잠금, 상태 자료 즉시 갱신.
