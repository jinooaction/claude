# 자동 전략 공장 최신 실행

- 판정: **NO_FACTORY_EDGE**
- 묶음: `strategy-factory-e676a1d58b7e`
- 탐색 순번: 3
- 완료 시도: 64/64
- 누적 다중검정 시도: 256
- 잠정 최고 후보: `factory-trend_inverse_vol-001ad6d2e302`
- DSR: 0.999192
- PBO: 0.738095
- PSR: 0.629816

## 관문

| 관문 | 상태 | 현재 | 기준 |
|---|:---:|---:|---:|
| complete_trials | PASS | 64 | 64 |
| holdout_months | PASS | 235 | 120 |
| dsr | PASS | 0.999192 | 0.95 |
| pbo | FAIL | 0.738095 | 0.1 |
| psr_vs_benchmark | FAIL | 0.629816 | 0.95 |
| segment_win_rate | FAIL | 0.5 | 0.6 |
| sharpe_superiority | FAIL | 0.087475 | 0.2 |
| calmar_superiority | PASS | 0.718944 | 0.480138 |
| drawdown_defense | PASS | 13.718736 | 13.815058 |
| cost_50bps_positive | PASS | 4.29847145 | 0.0 |

> 이 실행은 주문·자본 변경을 하지 않는다. 모든 관문을 통과한 경우에만 별도 연구 캐너리 심사를 요청한다.

## workflow metadata

| 항목 | 값 |
|---|---|
| run_id | [REDACTED_ACCOUNT] |
| commit | f91cc8c94b1f67877bb10fa8011ec58023189983 |
| timestamp_utc | 2026-08-22T16:10:56Z |
| identical_batch_suppressed | false |
| safety | no broker API, no orders, no capital change |
