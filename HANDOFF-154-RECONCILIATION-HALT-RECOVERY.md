# HANDOFF-154 - 정합성 halt 조건부 자동 복구

## 상태

PR #644가 `main`에 병합됐고 production 배포, KIS smoke, 새 정합성 검사, halt 복구,
후속 money-path 재평가가 모두 성공했다. 현재 정합성은 `OK`, halt는 없고 293달러
자본 경로는 `REAL_ORDER_PATH_ARMED`다.

전략 체결은 아직 0건, 전략 손익은 0달러다. 다음 자동 주문 후보 시각은
`2026-08-24T15:00:00Z`이며 그때도 모든 기존 안전 게이트를 통과해야 한다.

## 무엇을 고쳤나

- `reconcile-recover`가 KIS에서 보유·현금을 새로 읽고 전략 측정 계약과 복구 준비도를
  다시 계산한다.
- 이유가 `reconciliation mismatch:`인 동일한 halt만 해제한다. 검사 중 halt가 바뀌면
  해제를 거부한다.
- 해제 감사 기록 실패 시 원래 halt 파일을 복원한다.
- root 소유 고정 SSH helper와 자동 workflow가 KIS smoke 뒤 복구를 실행한다.
- money-path는 최신 복구 sidecar가 없거나 36시간을 넘거나 halt가 남으면 실주문 가능
  상태를 보고하지 않는다.
- 기존 수동 release workflow의 무조건 `resume`과 임의 원격 셸을 제거했다.

## 생산 증거

- 기능 커밋: `d089022`.
- main 머지: `68eab4e`, PR #644.
- 배포: run `32556975350`, 성공.
- KIS smoke: run `32556975347`, 성공, exit 0, commit `68eab4e`.
- 자동 복구: run `32557022009`, `RECOVERED`.
- 정합성: `OK`.
- 측정 품질: `VALID`.
- halt: 실행 전 존재, 실행 뒤 없음, 해제 true.
- 복구 주문: 0건.
- money-path: run `32557042951`, `REAL_ORDER_PATH_ARMED`, `can_submit_real_orders=true`.
- 다음 예약: `2026-08-24T15:00:00Z`.

## 검증

- `uv run pytest`: 2904 passed, 6 skipped.
- `uv run ruff check src tests`: 통과.
- 변경 경로 집중 검증: 130 passed.
- 셸 구문, YAML 파싱, `git diff --check`: 통과.
- `uv run python scripts/agent_harness_probe.py --strict`: OK 14/14.
- `uv run python scripts/check_handoff_facts.py`: OK.
- PR 품질 관문과 GitHub 검사: 통과.

## 안전 경계

자동 복구는 정합성 오류 halt만 대상으로 한다. 수동·손실·서킷브레이커 halt는 자동
해제하지 않는다. whitelist, 포지션 한도, 자본 293달러, 손실 예산 20%, 정규장,
현금 1% 여유, production 기계 승인, 서명·nonce, 추가 전용 감사 로그는 유지된다.

## 다음 세션 판단

현재 코드를 더 바꾸기보다 `2026-08-24T15:00:00Z` 예약 실행을 관찰한다. 주문 계획이
없거나 어느 게이트가 차단하면 강제로 주문하지 않는다. 주문이 실제 접수되면 체결 동기화,
전략 범위 손익, 열린 주문, 새 정합성 결과를 함께 확인한다. 체결·양의 손익 전에는 수익을
냈다고 보고하지 않는다.
