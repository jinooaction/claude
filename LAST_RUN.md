# 후보 결과 실행기 최신 실행

| 항목 | 값 |
|------|-----|
| schema_version | 1.0 |
| run_id | [REDACTED_ACCOUNT] |
| commit | 4a5f43add677155382487f23a8a47debd2daa378 |
| timestamp_utc | 2026-09-05T12:04:18Z |
| overall_status | degraded |

## 한 줄 결론

후보 구현 공장이 만든 검증 패키지를 안전한 실행 결과로 바꾸고, 기계 판독 가능한 candidate result evidence를 발행했다.

## 집계

- `pass`: 0
- `fail`: 1
- `pending`: 1
- `blocked`: 0

## 진단 집계

- `insufficient_pass_evidence`: 1
- `mixed_horizon_evidence`: 1

## 후보별 결과

- `pending` strategy_backtest: `candidate-1ed634d8bf6d` / `pkg-c9a284fa4235`
  - 사유: 장기와 최근 전략 증거가 섞여 있어 추가 forward 검증이 필요하다.
  - 요약: 통과 증거를 보존하고 실패 축만 대기 상태로 분리했다.
  - 진단: `insufficient_pass_evidence` — 실행 출력에 통과 verdict가 충분히 없다.
  - 다음 행동: 검증 명령이 명확한 pass/fail verdict와 핵심 통계를 내도록 보강한다.
- `fail` portfolio_backtest: `candidate-cc96b35062da` / `pkg-8aae8cb99874`
  - 사유: 모든 필수 전략 증거 축이 엣지 없음 또는 실패를 보고했다.
  - 요약: 장기·최근·전진 검증이 모두 실패했다.

## 안전 문구

이 실행은 허용된 no-live 검증만 수행한다. 주문, 자본 사다리, live 전략 설정, whitelist, caps, 실거래 sentinel, 브로커 API를 변경하지 않는다.

## workflow metadata

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 4a5f43add677155382487f23a8a47debd2daa378 |
| trigger | schedule |
| timestamp_utc | 2026-09-05T12:04:26Z |
| safety | no broker, no orders, no capital/live config/whitelist/caps/sentinel change |
