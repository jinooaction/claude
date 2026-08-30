# 데이터 모델

## ForwardGateCalibration

- `verdict`: `CALIBRATED | UNDERPOWERED | CALIBRATION_FAILED`
- `significance_method`: `paired_active_return_psr_v1`
- `code_commit`: 교정 실행 코드 커밋
- `false_positive_control_passed`: paper/live 무효 오합격 검사와 상대 방법 검사가 모두 참
- `detection_power_passed`: paper/live 심은 신호 검출률이 각각 80% 이상
- `required.minimum_detection_rate`: `0.80`
- `checks`: 개별 오합격·상대 개선·절대 검출력 검사
- 표준 자본 적격: 두 불리언, 같은 코드 커밋, 같은 방법이 모두 참일 때만

## CombinedEdgeVerdict

- `verdict`: `EDGE_CONFIRMED | NO_EDGE | INSUFFICIENT_DATA`
- `source`: `standard | anchored | both | none`
- `significance_method`: 표준이 확정원일 때 `paired_active_return_psr_v1`
- `standard_significance_method`: 표준 원본 값
- `anchored_method`: 앵커드 원본 `backtest_anchored`
- `anchored_oos_n_obs`, `anchored_significance`, `anchored_dsr_threshold`, `anchored_num_trials`
- `n_obs`: 실제 확정원의 전진 관측 수

## CalendarPolicy

- `last_sessions`: 월말 이전 포함 거래일 수, 1~4
- `first_sessions`: 월초 이후 포함 거래일 수, 1~4
- `one_way_cost_bps`: 10
- `annual_fixed_cost_bps`: 50
- `signal`: `market_on_month_boundary_else_cash`

## CalendarCandidate

- `candidate_id`: `calendar-turn-{last}-{first}-{digest}`
- `trial_index`: 1~16
- `policy`: `CalendarPolicy`
- `strategy_fingerprint`: 자료가 아니라 불변 전략 규칙의 SHA-256
- `live_expressible=false`, `live_blocker`: 정확한 실행 동등성·주문 엔진 없음

## FrenchDailyBundle

- `rows`: 날짜, 시장 총수익, 무위험 수익
- `source_url`, `content_digest`, `row_count`, `first_date`, `last_date`
- `latest_complete_month`, `dropped_incomplete_month`
- `complete`, `chronology_passed`, `schema_passed`

## CalendarTrialRecord

- 후보 ID·지문·상태
- 개발 구간 비용 후 월별 현금 초과수익
- 개발 연환산 샤프와 10개 구간 샤프
- 홀드아웃은 후보 선택 전 장부 행에 포함하지 않고 선택 뒤 확인 필드로만 결합

## TurnOfMonthDecision

- `verdict`: `FACTORY_EDGE | PAPER_CHALLENGER | NO_FACTORY_EDGE`
- `provisional_best_candidate_id`: 개발 승자
- `selected_candidate_id`: 역사 전체 관문 승자 ID 또는 `null`
- `selected_deploy_config`: 항상 `null`
- `research_canary_eligible`: 항상 `false`
- `promotion_allowed`: 항상 `false`
- `gates`: 데이터·장부·교정·PBO·PSR·경제성·시대·최근·집중도·낙폭·스트레스·위약
- `paper_gates`: 낮은 PSR 0.80 등 진단용, 승격 불가

## ProgramAudit

- `audit_records`: 기존 752행 + 출시 레짐 16행 + 현재 달력 16행
- `global_audit_trial_count`: 784
- `unique_trial_fingerprint_count`: 784
- `research_family_audit`: 독립 재분류한 19개 가족
- `program_research_family_count`: 19
- `program_false_acceptance_budget`: 0.19

## SafetyEvidence

- `orders_submitted`: 0
- `capital_changed`: false
- `live_strategy_changed`: false
- `research_live_parity`: false
- `promotion_allowed`: false
