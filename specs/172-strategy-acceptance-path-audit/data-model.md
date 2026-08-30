# 데이터 모델

## ForwardGateCalibration

- `verdict`: `CALIBRATED | UNDERPOWERED | CALIBRATION_FAILED`
- `required.minimum_detection_rate`: 0.80
- `planted_edge.*.paper_acceptance_rate`, `live_acceptance_rate`
- `checks`: 오탐, 상대 개선, paper/live 절대 검출력 검사

## StrategyAcceptancePathAudit

- `historical_gate_summary`: 8개 관문, 통과 수, 실패 목록, 역사 판정
- `calibration_coverage`: 직접 교정 관문, 미교정 관문, `PARTIAL_COVERAGE`
- `forward_power`: 교정 판정, 표본 수, 심은 신호, paper/live 검출력
- `conclusion`: 역사적 유망성·연구 합격·현재 실자본 적격성을 분리한 상태
- `safety`: 주문·자본·승격·라이브 변경 금지

## RegimeForwardObservation

- 후보·기준 지문, `frozen_through`, `n_obs`, `minimum_observations`
- 능동수익 PSR과 `OBSERVATION_WAIT` 상태
- `promotion_allowed=false`, `orders_submitted=0`, `capital_changed=false`

## StableParallelResearchCandidate

- ID 지문 입력: 기준 후보 ID, 전진 트랙, 역사 판정, 계약 버전
- 제외 입력: `n_obs`, PSR의 시시각각 값, 관찰 버킷
- 상태: 출시 전 `EXECUTION_READY`, 출시 후 미발행
