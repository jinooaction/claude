# Contract: macro strategy factory evidence

## Required top-level fields

- 기존 strategy factory 계약 전체
- `macro_data`
- `exploratory_replay`
- `research_live_parity`

## Macro data contract

- `source_commit`, `generated_at_utc`, `first_date`, `last_date`
- `series`: DGS2, DGS10, CPIAUCNS, SAHMREALTIME, VIX
- 각 계열의 최초·최종 날짜, 행 수, 결측 수, 최신 나이, 교차검증 상태
- `development_window`: 1990-01-01~2006-12-31
- `holdout_window`: 2007-01-01 이후

## Trial accounting contract

- `production_trial_count`: 256
- `exploratory_trial_count`: 192
- `current_trial_count`: 64
- `multiplicity_trial_count`: 정확히 512
- 192개 재생 중 하나라도 없거나 지문이 다르면 `research_canary_eligible=false`

## Decision contract

- 기존 스펙 150 관문을 숫자까지 그대로 포함
- 추가 관문: `macro_data_complete`, `publication_lag_safe`, `realtime_labor_safe`,
  `exploratory_replay_complete`, `research_live_parity`, `live_data_freshness`
- 모든 관문을 통과했을 때만 `selected_candidate_id`, `selected_deploy_config`,
  `selected_strategy_fingerprint`를 발행

## Live fail-closed contract

- 거시 자료가 없거나 7일보다 오래되면 브로커 호출 전 차단
- 오류 때문에 자동 전량청산하지 않음
- 손실 halt·정합성 오류·주문 상태 불명은 기존 더 높은 우선순위로 처리
- 이 증거만으로 자본을 바꾸지 않으며 기존 강화 캐너리와 자본 사다리가 필요
