# 후보 구현 공장 최신 실행

| 항목 | 값 |
|------|-----|
| schema_version | 1.0 |
| run_id | [REDACTED_ACCOUNT] |
| commit | f91cc8c94b1f67877bb10fa8011ec58023189983 |
| timestamp_utc | 2026-08-22T16:06:05Z |
| overall_status | degraded |

## 한 줄 결론

`BACKTEST_REQUIRED` 후보를 그냥 대기시키지 않고 후보별 검증 패키지와 `promotion_evidence` 보강 경로로 변환했다. 결과 증거가 없는 후보는 통과로 위조하지 않고 실행 대기 상태로 남겼다.

## 집계

- `ready`: 0
- `pending`: 0
- `blocked`: 2
- `evidence_passed`: 0

## 후보별 패키지

- `blocked` strategy_backtest: micro GTAA 의도 손익 재검토와 대체 전략 연구 (`candidate-1ed634d8bf6d`)
  - 차단/대기: 기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다.
  - 첫 명령: `uv run auto-invest portfolio-walk-forward --portfolio deploy/micro-gtaa-live-portfolio.toml --trailing-years 5 --history-root /tmp/candidate_result_history/micro-gtaa/hist --db data/candidate-factory/candidate-1ed634d8bf6d.db --halt-path data/candidate-factory/candidate-1ed634d8bf6d.halt.flag --json`
- `blocked` portfolio_backtest: 비상관 포트폴리오 후보 비교력 강화 (`candidate-cc96b35062da`)
  - 차단/대기: 기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다.
  - 첫 명령: `uv run auto-invest portfolio-walk-forward --portfolio deploy/global-trend-wide-portfolio.toml --trailing-years 5 --history-root /tmp/candidate_result_history/global-trend-wide/hist --db data/candidate-factory/candidate-cc96b35062da-wide.db --halt-path data/candidate-factory/candidate-cc96b35062da.halt.flag --json`

## 안전 문구

이 실행은 검증 패키지와 후보 JSON만 만든다. 주문, 자본 사다리, live 전략 설정, whitelist, caps, 실거래 sentinel, 브로커 API를 변경하지 않는다.

## workflow metadata

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | f91cc8c94b1f67877bb10fa8011ec58023189983 |
| trigger | push |
| timestamp_utc | 2026-08-22T16:06:05Z |
| safety | no broker, no orders, no capital/live config/whitelist/caps/sentinel change |
