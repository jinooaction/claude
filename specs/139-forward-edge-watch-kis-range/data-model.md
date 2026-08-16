# Data Model

## OrderExecutionRange

- `start_date_yyyymmdd`: 필수 시작일
- `end_date_yyyymmdd`: 선택 종료일, 없으면 시작일
- 불변식: 종료일은 시작일 이상

## ForwardEdgeWatch

- `historical_verdict`: `HOLDOUT_EDGE` 여부
- `status`: `FORWARD_VALIDATION` 또는 `FORWARD_EDGE_READY`
- `track_key`, `n_obs`, `psr_vs_benchmark`, `threshold`, `passed`
- 미달 출력: `wait-for-globalfixed-forward-edge`, `OBSERVATION_WAIT`
- 통과 출력: `candidate-globalfixed-promotion-recheck`, `EXECUTION_READY`

두 출력 모두 주문·자본 변경 권한은 없다.
