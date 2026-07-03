# HANDOFF 091 — 학습 장부 후보 재발굴 차단 (2026-07-03 KST)

main 코드 베이스라인: `753afb7`(PR #461). 이 작업은 자율 작업 실행 루프가 고른
`candidate-fa66202bf496`를 닫은 등급 2 운영 자동화 보정이다. 학습 장부가 이미 폐기·보류·운영자
검토로 판단한 후보가 다음 자율 성장 실행에서 다시 안전 자동 후보처럼 떠오르지 않게 했다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/evolution_loop.py`
  - `apply_learning_ledger`가 `rejected/discard`, `evidence_dependent/deferred/observe`,
    `operator_review` 결정을 후보 상태에 실제 반영한다.
  - 보류·운영자 검토 후보는 `safe_high_leverage_work`에서 빠지고, 다음 행동에는 ledger 사유,
    근거 패키지, 재검토 조건이 남는다.
  - 알 수 없는 ledger decision은 기존처럼 실패 개방으로 둔다.
- `tests/unit/test_evolution_loop.py`
  - evidence-dependent ledger entry가 `candidate-fa66202bf496`를 안전 자동 후보에서 빼는지 검증한다.
  - operator-review ledger entry가 후보를 운영자 검토 출력으로 보내고 자동 착수를 막는지 검증한다.
- `tests/integration/test_evolution_loop_probe.py`
  - `scripts/evolution_loop_probe.py --ledger-json` 실제 probe 경로에서 같은 억제가 재현되는지 검증한다.
- `specs/087-learning-ledger-candidate-memory/`
  - SDD 산출물, quickstart, contract, tasks를 남겼다.
  - 완료 marker: `completed_candidate_id: candidate-fa66202bf496`.

## 운영상 의미

- 학습 장부는 이제 단순 기록이 아니라 후보 선별 입력이다. 장부가 보류나 운영자 검토라고 말한 후보는
  `safe_high_leverage_work`로 자동 시작되지 않는다.
- `candidate-fa66202bf496` 자체는 released-work 장부에서 `released`, autonomous-work sidecar에서
  `RELEASED`로 닫혔다. 이 후보를 다시 새 작업으로 시작하지 않는다.
- 최신 autonomous-work sidecar는 실행 가능한 안전 후보가 없다고 본다. `selected_work`에 보이는
  `candidate-facf2fa31834`도 `CLOSED_RELEASED` 상태라 새 착수 후보가 아니다.
- 자율 성장 원본 backlog는 같은 후보를 `new`로 생성할 수 있다. 실제 착수 방지는 released-work와
  autonomous-work 실행 경로, 그리고 future ledger entry의 `apply_learning_ledger` 경로에서 확인한다.

## 배포 후 실제 실행 증거

- PR #461 merge commit: `753afb73b2e3926e536a3e0340d998491785a7bb`
- PR #461 feature commit: `f1d86f4359caf209e703d50f1df91958b81981e0`
- PR #461 post-merge runs:
  - `Deploy on merge to main` run `28632340034`: success
  - `Released work ledger` run `28632340016`: success
  - `Autonomous evolution loop` run `28632340021`: success
  - `Autonomous work execution loop` run `28632340035`: success
  - `Execution quality package` run `28632340008`: success
- 최신 sidecar 재확인:
  - released-work commit `753afb7`, `candidate-fa66202bf496` status `released`
  - autonomous-work commit `753afb7`, `candidate-fa66202bf496` status `RELEASED`, 실행 가능 후보 없음
  - autonomous-evolution commit `753afb7`, 원본 backlog에는 이 후보가 `new`로 생성됨
- KIS smoke sidecar 최신 성공은 2026-07-02 schedule run이므로 이번 merge의 직접 배포 증거가 아니다.
  이번 merge의 직접 배포 증거는 push:main에 붙은 deploy run `28632340034`다.

## 안전 경계

- 위험 등급: 2(운영 자동화 후보 판독 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #461 머지 전:

- `uv run pytest tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py -q`
  -> 39 passed
- quickstart ledger replay
  -> `candidate-fa66202bf496` status `evidence_dependent`, `safe_high_leverage_work`에는 없음
- `uv run pytest`
  -> 2450 passed, 4 skipped
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
- `uv run python scripts/released_work_probe.py --repo-root . --run-id local-087 --commit "$(git rev-parse HEAD)" --json-out /tmp/released_work_087.json --summary-out /tmp/released_work_087.md`
  -> `candidate-fa66202bf496` released

인계 브랜치에서:

- `uv run ruff check src tests`
  -> All checks passed
- `uv run pytest -q`는 처음에 2개 테스트가 실패했다. 원인은 `HANDOFF.md`가 아직 #459를 최신 main으로
  가리킨 것이며, 이 handoff가 고치는 낡은 HANDOFF 실패다.
- `HANDOFF.md`를 #461 main 기준으로 갱신한 뒤 `uv run python scripts/check_handoff_facts.py`
  -> OK
- `HANDOFF.md`를 #461 main 기준으로 갱신한 뒤 `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `HANDOFF.md`를 #461 main 기준으로 갱신한 뒤 `uv run pytest -q`
  -> 2450 passed, 4 skipped

## 다음 세션 한 줄

스펙 087의 `candidate-fa66202bf496`는 main과 sidecar에서 완료·억제 상태로 닫혔다. 현재 자율 작업 실행
sidecar에는 새로 바로 착수할 안전 후보가 없으므로, 다음 세션은 먼저 최신 sidecar와 열린 PR을 `/sync`로
확인한 뒤 새 후보가 생겼을 때 SDD 두께를 판단하면 된다.
