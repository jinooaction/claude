# 후보 결과 실행기 최신 실행

| 항목 | 값 |
|------|-----|
| schema_version | 1.0 |
| run_id | [REDACTED_ACCOUNT] |
| commit | 37829096639c7ef60c3df43bf899fce516667fc4 |
| timestamp_utc | 2026-09-26T13:23:08Z |
| overall_status | degraded |

## 한 줄 결론

후보 구현 공장이 만든 검증 패키지를 안전한 실행 결과로 바꾸고, 기계 판독 가능한 candidate result evidence를 발행했다.

## 집계

- `pass`: 0
- `fail`: 0
- `pending`: 0
- `blocked`: 2

## 진단 집계

- `execution_failed`: 2

## 후보별 결과

- `blocked` strategy_backtest: `candidate-1ed634d8bf6d` / `pkg-c9a284fa4235`
  - 사유: 후보 구현 공장에서 이미 blocked 상태로 표시한 패키지다.
  - 요약: 안전 또는 지원 범위 밖이라 실행하지 않았다.
  - 진단: `execution_failed` — 검증 명령이 비정상 종료했다.
  - 다음 행동: 종료 코드와 제한된 출력을 바탕으로 실패 원인을 더 좁힌다.
- `blocked` portfolio_backtest: `candidate-cc96b35062da` / `pkg-8aae8cb99874`
  - 사유: 후보 구현 공장에서 이미 blocked 상태로 표시한 패키지다.
  - 요약: 안전 또는 지원 범위 밖이라 실행하지 않았다.
  - 진단: `execution_failed` — 검증 명령이 비정상 종료했다.
  - 다음 행동: 종료 코드와 제한된 출력을 바탕으로 실패 원인을 더 좁힌다.

## 안전 문구

이 실행은 허용된 no-live 검증만 수행한다. 주문, 자본 사다리, live 전략 설정, whitelist, caps, 실거래 sentinel, 브로커 API를 변경하지 않는다.

## workflow metadata

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 37829096639c7ef60c3df43bf899fce516667fc4 |
| trigger | schedule |
| timestamp_utc | 2026-09-26T13:23:08Z |
| safety | no broker, no orders, no capital/live config/whitelist/caps/sentinel change |
