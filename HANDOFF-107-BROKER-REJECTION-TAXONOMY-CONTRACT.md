# HANDOFF 107 — 브로커 거부 분류 계약 (2026-07-07 KST)

main 코드 베이스라인: `8492aad`(PR #493). 이 작업은 스펙 102가 열어 둔
`candidate-broker-rejection-taxonomy-contract`를 완료 처리하고, KIS 브로커 거부 코드와 주문 재시도 금지
행동을 기계 판독 계약으로 고정한 등급 2 읽기 전용 운영 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/broker_rejection_taxonomy.py`
  - execution-quality, KIS smoke, rebalance-micro-gtaa, pipeline-liveness, released-work,
    capital-path readiness sidecar를 읽어 브로커 거부 분류 보고서를 만든다.
  - `APBK1672` 같은 KIS 주문 응답 거부 코드를 `kis_order_response_rejection`으로 분류한다.
  - quality gate를 `PASS`, `WAIT`, `FAIL`로 나누고 전체 상태를 `CONTRACT_READY`,
    `OBSERVATION_WAIT`, `BLOCKED`로 발행한다.
  - live intent loss 상태에서는 `NO_AUTO_RETRY`와 전략 검토·forward 토너먼트 증거 대기를 명시한다.
- `scripts/broker_rejection_taxonomy_probe.py`
  - repo-root 또는 manifest replay에서 JSON/Markdown 보고서를 출력한다.
- `tests/unit/test_broker_rejection_taxonomy.py`
  - KIS 오류 코드 분류, unknown fallback, stale/부족 증거 대기, safety boundary를 고정한다.
- `tests/integration/test_broker_rejection_taxonomy_probe.py`
  - CLI JSON/Markdown 출력과 manifest surface를 검증한다.
- `specs/103-broker-rejection-taxonomy-contract/`
  - SDD 산출물과 `completed_candidate_id: candidate-broker-rejection-taxonomy-contract` 완료 마커를 남겼다.

## 운영상 의미

- 최신 remote released-work sidecar는 `candidate-broker-rejection-taxonomy-contract`를 released로 읽는다.
- 최신 remote autonomous-work sidecar는 다음 실행 후보를 `candidate-execution-cost-basis-contract`로 선택한다.
- `APBK1672` 거부 2건은 브로커 주문 응답 거부로 분류되지만, KIS smoke 성공을 주문 재시도 허가로 해석하지 않는다.
- 현재 micro GTAA live intent gate는 `latest_intent_loss`라 live 주문을 막고 있다.
- 돈 경로는 계속 `PREVIEW_ONLY`이고 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #493 merge commit: `8492aad72ff1f3d96930c19cea6643046dd7e71f`
- PR #493 feature commit: `31cbfd5`
- 직전 main: `b92cbe5`(PR #492, 스펙 102 인계)
- PR #493 post-merge runs:
  - `Deploy on merge to main` run `28840419738`: success
  - `Released work ledger` run `28840419722`: success
  - `Autonomous work execution loop` run `28840419831`: success
- released-work sidecar:
  - timestamp `2026-07-07T03:57:58.221310Z`
  - `candidate-broker-rejection-taxonomy-contract` 포함
  - released count 24
- autonomous-work sidecar:
  - timestamp `2026-07-07T03:57:54Z`
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-execution-cost-basis-contract`
  - domain `execution_quality`
  - risk grade 2, safety impact 없음
- deploy status:
  - main commit의 `Deploy on merge to main` 체크와 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar 최신 run은 #493 배포의 직접 증거가 아니라 이전 schedule 실행 증거이므로 #493 배포
    근거로 쓰지 않는다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 브로커 거부 분류 계약

| 항목 | 값 |
|------|-----|
| completed candidate | `candidate-broker-rejection-taxonomy-contract` |
| next candidate | `candidate-execution-cost-basis-contract` |
| overall status | `CONTRACT_READY` |
| primary taxonomy key | `kis_order_response_rejection` |
| broker code | `APBK1672` |
| observed count | 2 |
| confidence | `HIGH` |
| recurrence risk | `OBSERVED_RECURRENT` |
| action category | `NO_AUTO_RETRY` |
| live intent reason | `latest_intent_loss` |

## 안전 경계

- 위험 등급: 2(읽기 전용 브로커 거부 분류 계약과 work packet 전진)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 주문 재시도: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #493 머지 전:

- `uv run pytest tests/unit/test_broker_rejection_taxonomy.py tests/integration/test_broker_rejection_taxonomy_probe.py tests/unit/test_autonomous_work_execution.py -q`
  -> 36 passed
- remote sidecar replay
  -> `overall_status=CONTRACT_READY`, taxonomy row `APBK1672`, action `NO_AUTO_RETRY`,
  next candidate `candidate-execution-cost-basis-contract`
- tasks 완료 상태 released-work local replay
  -> `candidate-broker-rejection-taxonomy-contract` released 확인
- tasks 완료 상태 autonomous-work local replay
  -> `candidate-execution-cost-basis-contract` selected work 확인
- `uv run pytest`
  -> 2533 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `git diff --check`
  -> 통과
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/check_pr_quality_gate.py .verify/pr-103-broker-rejection-taxonomy-contract.md`
  -> pr-quality-gate-ok
- PR 품질 관문
  -> success
- 머지 직전 `uv run pytest`
  -> 2533 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- 인계 갱신 전 `uv run pytest -q`
  -> 낡은 HANDOFF 때문에 하네스 2건만 실패
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run pytest -q`
  -> 2533 passed, 4 skipped

## 다음 세션 한 줄

스펙 103은 브로커 거부 분류를 `NO_AUTO_RETRY` 계약으로 닫았고, 자율 작업 후보는 이제
`candidate-execution-cost-basis-contract`로 전진한다.
