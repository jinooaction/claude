# 후보 결과 실행기 최신 실행

| 항목 | 값 |
|------|-----|
| schema_version | 1.0 |
| run_id | [REDACTED_ACCOUNT] |
| commit | 758dda2534af38f444ac75361295fb49b489e234 |
| timestamp_utc | 2026-08-08T09:21:04Z |
| overall_status | degraded |

## 한 줄 결론

후보 구현 공장이 만든 검증 패키지를 안전한 실행 결과로 바꾸고, 기계 판독 가능한 candidate result evidence를 발행했다.

## 집계

- `pass`: 0
- `fail`: 2
- `pending`: 0
- `blocked`: 0

## 후보별 결과

- `fail` portfolio_backtest: `candidate-cc96b35062da` / `pkg-8aae8cb99874`
  - 사유: 전략 검증 출력이 엣지 없음 또는 실패를 보고했다.
  - 요약: 검증 결과가 전략 엣지 실패를 보고했다.
- `fail` strategy_backtest: `candidate-1ed634d8bf6d` / `pkg-c9a284fa4235`
  - 사유: 전략 검증 출력이 엣지 없음 또는 실패를 보고했다.
  - 요약: 검증 결과가 전략 엣지 실패를 보고했다.

## 안전 문구

이 실행은 허용된 no-live 검증만 수행한다. 주문, 자본 사다리, live 전략 설정, whitelist, caps, 실거래 sentinel, 브로커 API를 변경하지 않는다.

## workflow metadata

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 758dda2534af38f444ac75361295fb49b489e234 |
| trigger | schedule |
| timestamp_utc | 2026-08-08T09:21:12Z |
| safety | no broker, no orders, no capital/live config/whitelist/caps/sentinel change |
