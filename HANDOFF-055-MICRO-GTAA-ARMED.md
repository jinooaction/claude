# HANDOFF 055 — 스펙 058 마이크로 GTAA 무장 및 수동 live 실행 (2026-06-22)

main 베이스라인: `75717a2`(PR #376). 운영자가 "마이크로 GTAA를 `capital_usd=1000`,
`armed=true`로 무장하고 수동 실행까지 승인한다"고 명시했고, 등급 4 돈 경로 승인 범위 안에서
센티넬 무장, main 머지, 수동 workflow 실행까지 완료했다.

## 무엇이 바뀌었나

- `automation/rebalance-micro-gtaa.request`: `armed:true`, `capital_usd:1000`, `run_seq:2`.
  note에 운영자 승인과 실행 의도를 남겼다.
- `tests/unit/test_micro_gtaa_canary.py`: 기본 비무장 센티넬 가정 대신 운영자 승인형 무장 상태를
  회귀 테스트로 고정했다.
- `specs/058-micro-gtaa-canary/contracts/micro-gtaa-canary.md`와
  `specs/058-micro-gtaa-canary/quickstart.md`: baseline default와 운영자 승인 activation을
  구분해 기록했다.

## 수동 live 실행 결과

- GitHub Actions run: `27935469561`
- 이벤트: `workflow_dispatch`
- 실행 커밋: `75717a289b2f015b12d260066f8eedae573669a8`
- 입력 자본: 1,000달러
- job 결론: `success`
- live 전 손실 브레이커: `tripped=false`, `reason="within loss limits"`

Dry-run 미리보기는 현재 신호와 정수주 조건에서 아래 주문을 계획했다.

- `IEF` 매수 1주, 미리보기 지정가 94.36달러
- `SPYM` 매수 3주, 미리보기 지정가 87.89달러
- `GLDM`은 주문 계획 없음

Live 재조정은 실제 주문 경로까지 들어갔지만, 브로커 접수는 되지 않았다.

- `IEF` 매수 1주, live 지정가 94.55달러, 상태 `REJECTED_BY_BROKER`
- `SPYM` 매수 3주, live 지정가 88.07달러, 상태 `REJECTED_BY_BROKER`
- 두 건 모두 사유는 `KIS` 해외주식 주문 엔드포인트
  `/uapi/overseas-stock/v1/trading/order`의 `500 Internal Server Error`

## 현재 계좌/측정 상태

sidecar `automation/rebalance-micro-gtaa-last-run` 기준:

- 주문 접수: 0건
- 체결: 0건
- `PORTFOLIO_NAV_SNAPSHOT seq=3651`
- 현금: 1,000달러
- 보유: 0개
- NAV: 1,000달러
- 판정: `INSUFFICIENT_DATA`(9/20 관측)

즉, "수동 실행과 실제 주문 시도"는 완료됐지만 "브로커 접수 또는 체결"은 0건이다.

## 현재 운영 상태

`armed:true`가 main에 남아 있다. 별도 비무장 PR이나 halt가 없으면
`.github/workflows/rebalance-micro-gtaa-canary.yml`의 평일 15:00 UTC 스케줄이 다음 실행에서
자동으로 live 재시도할 수 있다.

중단 방법:

- `automation/rebalance-micro-gtaa.request`를 `armed:false`로 되돌리는 PR
- 또는 운영 halt 파일을 설정해 live 주문 게이트를 막는 절차

반복 500이면 아래를 먼저 확인한다.

- 정규장 시간대에서 같은 오류가 반복되는지
- `KIS` 주문 API 자격·상품·거래소 파라미터가 해외주식 주문에서 거부되는지
- sidecar `automation/rebalance-micro-gtaa-last-run:LAST_RUN.md`와 해당 GitHub Actions run 로그

## 검증

PR #376 머지 전:

- `uv run pytest tests/unit/test_micro_gtaa_canary.py tests/unit/test_canary_portfolio_config.py`
  → 13 passed
- workflow YAML parse → `yaml-ok`
- `git diff --check` → 통과
- `uv run pytest` → 2222 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`

수동 실행 후 handoff 갱신 전:

- `uv run pytest -q`는 stale `HANDOFF.md` 때문에 하네스 2건 실패. 실패 원인은 요약표의
  `마지막 main 커밋` 행이 `f3d5085`로 남아 있었기 때문이다.
- `uv run ruff check src tests` → All checks passed

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run pytest -q` → 2222 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 안전 경계

- 위험 등급: 4(돈 경로 활성화 및 실제 주문 시도)
- Kernel 터치: 없음
- 헌법 변경: 없음
- 비밀값 추가: 없음
- K1/K2 코드 변경: 없음
- 주문 제한 완화: 없음
- 브로커 접수·체결: 0건
- 돈 이동: sidecar 기준 0
- 되돌림: `armed:false` PR 또는 halt 설정

## 다음 세션 한 줄

마이크로 GTAA는 `armed:true`로 main에 남아 있고 첫 수동 live 실행은 `KIS` 주문 API 500으로
접수·체결 0건이었다. 다음 15:00 UTC 스케줄이 자동 재시도할 수 있으므로, 새 작업 전 최신
sidecar와 실행 로그를 먼저 확인해야 한다.
