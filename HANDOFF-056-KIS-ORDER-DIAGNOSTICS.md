# HANDOFF 056 — 스펙 059 KIS 주문 원인 확정 경로 복구 (2026-06-22)

main 베이스라인: `24c2947`(PR #378). 이전 수동 micro GTAA live 실행 run `27935469561`에서
`KIS` 해외주식 주문 API가 500을 돌려줬지만, 당시 로그는 브로커 응답 본문과 주문 전제를 충분히
보존하지 못했다. PR #378은 같은 실패가 다시 발생할 때 원인을 확정할 수 있도록 주문 전제 확인,
KIS 주문 payload 정합성, 마스킹된 브로커 진단 보존을 추가했다.

## 무엇이 바뀌었나

- `specs/059-kis-order-diagnostics/`: 문제 정의, 설계, 작업, 계약, 빠른 확인 문서를 추가했다.
- `.github/workflows/rebalance-micro-gtaa-canary.yml`: live 주문 전 `Pre-live order preflight`
  단계를 추가했다. 정규장 여부, dry-run 주문 계획의 매수 필요 현금, `KIS` 매수가능 현금을 읽기
  전용으로 확인하고, 1% 비용 완충을 포함해 조건 미달이면 live 주문 전 중단한다.
- `src/auto_invest/broker/overseas.py`: `KIS` 해외주식 주문 공식 샘플 필드
  `CTAC_TLNO`, `MGCO_APTM_ODNO`, `SLL_TYPE`, `ORD_SVR_DVSN_CD`를 포함하도록 주문 본문을 맞췄다.
- `src/auto_invest/broker/diagnostics.py`: `httpx` 주문 오류에서 상태 코드, URL, 응답 본문 미리보기,
  KIS 오류 코드·메시지를 마스킹해 구조화한다.
- `src/auto_invest/persistence/audit.py`: K4 감사 payload에
  `OrderRejectedByBrokerPayload.diagnostics` 선택 필드를 추가했다.
- `src/auto_invest/execution/order_router.py`: 브로커 거부 진단을 감사 로그, 상태 전이 사유,
  주문 결과 사유까지 전달한다.

## 현재 운영 상태

- micro GTAA 센티넬은 계속 `armed:true`, `capital_usd:1000`이다.
- PR #378에서는 실제 주문을 재시도하지 않았다. 주문 접수·체결은 새로 발생하지 않았다.
- 다음 `schedule` 또는 `workflow_dispatch` live 실행은 아래 순서를 통과해야 주문 단계에 도달한다.
  정규장 확인 → dry-run 주문 계획 → KIS 매수가능 현금 확인 → 1% 비용 완충 확인 → 손실 브레이커 →
  live 재조정.
- 조건 미달이면 sidecar의 "라이브 전 주문 전제 확인" 섹션과 `/tmp/micro_preflight.json` 내용이
  원인을 먼저 보여준다.
- 조건을 통과했는데도 `KIS`가 거부하면, 감사 payload와 주문 결과 사유에 마스킹된 브로커 응답
  진단이 남아야 한다.

## 검증

PR #378 머지 전:

- `uv run pytest tests/integration/test_broker_order_diagnostics.py tests/unit/test_micro_gtaa_canary.py`
  → 36 passed
- `uv run pytest tests/integration/test_broker_order_diagnostics.py tests/unit/test_micro_gtaa_canary.py tests/unit/test_audit_schema.py`
  → 41 passed
- `uv run pytest` → 2229 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `uv run python scripts/check_pr_quality_gate.py /tmp/pr378_body.md` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`

머지 후:

- main merge commit: `24c2947`
- deploy-on-merge run `27939601985` → success. 이 배포는 dry-run worker 반영 확인이며,
  micro GTAA live 주문 실행이 아니다.
- `KIS` smoke sidecar는 `2026-06-21T08:01:35Z` run `27898040482` 기준으로 오래된 성공 기록이다.
  #378 이후 주문 진단의 실서버 검증 증거로 보지 않는다.

이 handoff 갱신 직전:

- `uv run ruff check src tests` → All checks passed
- `uv run pytest -q` → stale `HANDOFF.md` 때문에 하네스 2건 실패
  (`HANDOFF` 마지막 main 커밋 행이 `75717a2`로 남아 있었음). 코드 실패가 아니라 인계 문서
  불일치였다.

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run pytest -q` → 2229 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 안전 경계

- 위험 등급: 4(돈 경로와 live 주문 전제에 닿음)
- K4 감사 터치: 커밋 `56dfec6`, `OrderRejectedByBrokerPayload.diagnostics` 선택 필드 추가
- 헌법 변경: 없음
- 커널 목록 변경: 없음
- 비밀값 추가·노출: 없음
- K1 캡·화이트리스트·손실 브레이커 완화: 없음
- 실제 주문 재시도: 없음
- 돈 이동: 없음
- 되돌림: PR #378을 되돌리면 preflight와 진단 보존이 제거된다. 단, `armed:true` 상태 자체는
  PR #376의 운영 승인 상태이므로 별도 판단이 필요하다.

## 다음 세션 한 줄

micro GTAA는 여전히 `armed:true`지만, 다음 live 시도는 정규장·매수가능 현금 preflight를 먼저
통과해야 한다. 실패하면 preflight 또는 마스킹된 KIS 진단을 보고 원인을 확정하고, 실제 주문 재시도는
별도 운영자 승인 범위와 현재 안전 경계를 다시 확인한 뒤 진행한다.
