# 데이터 모델

## AccountingFactorMonth

- `month`: `YYYY-MM`, 엄격 증가·중복 금지
- `market_excess`, `size`, `value`, `profitability`, `investment`, `cash`: 월 단순수익
- 필수 열: `Mkt-RF`, `SMB`, `HML`, `RMW`, `CMA`, `RF`
- 결측 표식 `-99.99`, `-999`와 비유한 값은 금지

## AccountingFactorBundle

- `development_rows`: 2015년 보관본의 1963-07~2013-12
- `embargo_rows`: 2014-01~2014-12, 선택·판정 미사용
- `holdout_rows`: 최신본의 2015-01 이후 최신 완결 월
- `archive_digest`, `current_digest`, URL, 행 수, 첫/마지막 월
- `common_development_months`, `revised_development_months`, 최대 절대 수정폭
- `point_in_time_constituents=false`, `history_revision_limited=true`

## AccountingFactorPolicy

- `hml_weight`, `rmw_weight`, `cma_weight`: 합계 1인 고정 비음수 가중치
- `sleeve_scale`: `0.5 | 1.0`
- `annual_cost_bps`: 기본 150, 스트레스 300·500
- `return_contract`: `RF + scale * weighted(HML,RMW,CMA) - annual_cost/12`

## AccountingFactorCandidate

- `candidate_id`: `accounting-factor-{profile}-{scale}-{digest}`
- `trial_index`: 1~16
- `policy`: `AccountingFactorPolicy`
- `strategy_fingerprint`: 정책·분할·자료 계약의 SHA-256
- `live_expressible=false`, `live_blocker`: 종목·수량·공매도·체결 계약 없음

## AccountingFactorTrialRecord

- 후보 ID·지문·상태
- 개발 월별 비용 후 현금 초과수익
- 개발 연환산 샤프와 10개 시간 조각 샤프
- 홀드아웃 PSR과 개발 선택 여부
- `holdout_inspected_after_selection=true`

## AccountingFactorDecision

- `verdict`: `FACTORY_EDGE | PAPER_CHALLENGER | NO_FACTORY_EDGE`
- `provisional_best_candidate_id`: 개발 승자
- `selected_candidate_id`: 역사 전체 관문 승자 또는 `null`
- `selected_deploy_config`: 항상 `null`
- `research_canary_eligible=false`, `promotion_allowed=false`
- `gates`: 자료·교정·장부·PBO·PSR·경제성·시간·집중·낙폭·비용·위약
- `next_strategy_family`: `post-earnings-announcement-drift-after-recalibration`

## ProgramAudit

- `audit_records`: 이전 784행 + 현재 16행
- `global_audit_trial_count`: 800
- `unique_trial_fingerprint_count`: 800
- `research_family_audit`: 독립 재분류한 20개 가족
- `program_false_acceptance_bound`: 0.20

## SafetyEvidence

- `orders_submitted`: 0
- `capital_changed`: false
- `live_strategy_changed`: false
- `research_live_parity.passed`: false
- `promotion_allowed`: false
