# Contract: strategy-factory evidence

## Required top-level fields

- `schema_version`
- `batch_id`, `timestamp_utc`, `code_commit`, `data_fingerprint`
- `candidate_count`, `complete_trial_count`
- `candidates[]`, `trial_records[]`
- `decision`
- `safety`

## Decision contract

- `verdict`: `FACTORY_EDGE` or `NO_FACTORY_EDGE`
- `selected_candidate_id`: only present for `FACTORY_EDGE`
- `gates[]`: every gate has `gate_id`, `passed`, `actual`, `required`
- `research_canary_eligible`: true only when every gate passes and 64 complete trials exist
- `selected_deploy_config`, `selected_strategy_fingerprint`

## Fail-closed rules

- 후보나 시도 수가 64가 아니면 `NO_FACTORY_EDGE`.
- DSR/PBO/PSR가 계산 불가면 `NO_FACTORY_EDGE`.
- 자료·코드·전략 지문이 없으면 `NO_FACTORY_EDGE`.
- 배포 설정을 파싱할 수 없거나 전략 지문이 다르면 `research_canary_eligible=false`.
- 이 계약만으로 주문하지 않으며 별도 강화 캐너리·정합성·자본 사다리 증거가 필요하다.
