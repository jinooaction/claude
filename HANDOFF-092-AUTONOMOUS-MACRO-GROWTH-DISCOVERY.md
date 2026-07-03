# HANDOFF 092 — 거시 자율 성장 후보 발굴기 (2026-07-03 KST)

main 코드 베이스라인: `927beb0`(PR #463). 이 작업은 자율 작업 실행 루프가 모든 일반 후보를
완료·억제로 닫은 뒤에도 "다음에 할 일 없음"으로 멈추지 않고, 닫힌 큐 상태 자체를 거시 성장
후보로 승격하게 만든 등급 2 운영 자동화 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/autonomous_work_execution.py`
  - released-work와 learning-ledger 적용 뒤 일반 work packet에 `EXECUTION_READY`,
    `OPERATOR_APPROVAL_REQUIRED`, `BLOCKED`가 없는지 확인한다.
  - 남은 일반 후보가 모두 `RELEASED` 또는 `SUPPRESSED`이면 순차 거시 후보를 만든다.
  - 일반 실행 가능 후보, pipeline/capital 복구 후보, 운영자 승인 필요 후보가 있으면 거시 후보를
    만들지 않는다.
  - 첫 후보는 `candidate-macro-growth-discovery`, 이 후보가 released-work에 있으면 다음 후보
    `candidate-evolution-source-diversification`을 선택한다.
- `tests/unit/test_autonomous_work_execution.py`
  - 닫힌 큐가 `candidate-macro-growth-discovery`를 선택하는지 검증한다.
  - 부트스트랩 후보가 released되면 다음 후보 `candidate-evolution-source-diversification`으로
    넘어가는지 검증한다.
  - operator approval 후보를 거시 후보가 가리지 않는지 검증한다.
- `tests/integration/test_autonomous_work_execution_probe.py`
  - 실제 `scripts/autonomous_work_execution_probe.py` 경로에서도 닫힌 큐가 거시 후보를 발행하는지
    검증한다.
- `specs/088-autonomous-macro-growth-discovery/`
  - SDD 산출물, quickstart, contract, tasks를 남겼다.
  - 완료 marker: `completed_candidate_id: candidate-macro-growth-discovery`.

## 운영상 의미

- 자율 루프가 정적 후보 목록을 모두 소비한 상태를 "할 일 없음"으로 남기지 않는다.
- `candidate-macro-growth-discovery` 자체는 released-work 장부에서 `released`로 닫혔다.
- 최신 autonomous-work sidecar는 다음 자율 후보를
  `candidate-evolution-source-diversification`으로 본다. 이 후보의 목표는 upstream evolution 후보
  생성을 정적 템플릿 밖 증거, sidecar 나이, 반복 실패 유형, 관찰 병목으로 확장하는 것이다.
- 이 변경은 작업 패킷 생성만 바꾼다. 주문, 자본, live 전략, whitelist/caps, 비밀값, 헌법,
  커널 목록은 바꾸지 않았다.

## 배포 후 실제 실행 증거

- PR #463 merge commit: `927beb02a2385b06d6d3f860ce5cf5fa27aa051f`
- PR #463 feature commit: `bca541587def11bd7b5fca8e796af44ff0725cbd`
- PR #463 post-merge runs:
  - `Deploy on merge to main` run `28637783776`: success
  - `Released work ledger` run `28637783779`: success
  - `Autonomous work execution loop` run `28637783763`: success
- 최신 sidecar 재확인:
  - released-work commit `927beb0`, released_count 9, `candidate-macro-growth-discovery` status `released`
  - autonomous-work commit `927beb0`, selected `candidate-evolution-source-diversification`,
    status `EXECUTION_READY`, ranked_count 1, suppressed_count 9
- Deploy run 로그에는 deploy correlation id `3def9820731ee47dd07ded917b858b34`와
  `auto-invest-deploy.service` 성공 종료가 남았다.
- KIS smoke sidecar 최신 성공은 2026-07-02 schedule run이므로 이번 merge의 직접 배포 증거가 아니다.
  이번 merge의 직접 배포 증거는 push:main에 붙은 deploy run `28637783776`이다.

## 안전 경계

- 위험 등급: 2(운영 자동화 후보 선택 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #463 머지 전:

- `uv run pytest tests/unit/test_autonomous_work_execution.py tests/integration/test_autonomous_work_execution_probe.py -q`
  -> 18 passed
- quickstart probe replay
  -> `candidate-macro-growth-discovery`, `EXECUTION_READY`
- `uv run pytest`
  -> 2454 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `git diff --check`
  -> pass
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- PR 품질 관문
  -> success
- `uv run python scripts/released_work_probe.py --repo-root . --run-id local-088 --commit "$(git rev-parse HEAD)" --json-out /tmp/released_work_088.json --summary-out /tmp/released_work_088.md`
  -> `candidate-macro-growth-discovery` released
- `scripts/autonomous_work_execution_probe.py --repo-root .` 로컬 재현
  -> `candidate-evolution-source-diversification`, `EXECUTION_READY`

인계 브랜치에서:

- `uv run ruff check src tests`
  -> All checks passed
- `uv run pytest -q`는 처음에 2개 테스트가 실패했다. 원인은 `HANDOFF.md`가 아직 #461을 최신 main으로
  가리킨 것이며, 이 handoff가 고치는 낡은 HANDOFF 실패다.
- `HANDOFF.md`를 #463 main 기준으로 갱신한 뒤 `uv run python scripts/check_handoff_facts.py`
  -> OK
- `HANDOFF.md`를 #463 main 기준으로 갱신한 뒤 `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `HANDOFF.md`를 #463 main 기준으로 갱신한 뒤 `uv run pytest -q`
  -> 2454 passed, 4 skipped

## 다음 세션 한 줄

스펙 088은 `candidate-macro-growth-discovery`를 완료로 닫았고, 최신 자율 작업 실행 sidecar는 다음
자율 후보로 `candidate-evolution-source-diversification`을 선택한다. 다음 세션은 `/sync`로 열린 PR이
없는지 확인한 뒤 이 후보를 SDD 기준으로 이어가면 된다.
