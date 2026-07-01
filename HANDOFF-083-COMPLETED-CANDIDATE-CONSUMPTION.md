# HANDOFF 083 — 완료 후보 소비 장부와 차순위 자동 선택 (2026-07-02 KST)

main 코드 베이스라인: `c8beb25`(PR #437). 스펙 079는 이미 구현·머지·인계된 자율 작업 후보를 `released-work` 장부로 소비하고, `autonomous-work-execution`이 같은 후보를 반복 선택하지 않고 다음 수익 후보로 이동하게 하는 읽기 전용 운영 루프다. PR #437은 PR #436 뒤 발견된 `released-work` sidecar publish token 누락을 보정했다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/released_work.py`
  - 완료된 Speckit 작업의 `tasks.md`가 전부 체크됐는지 확인한다.
  - `selected_work_candidate`, `released_candidate_id`, `completed_candidate_id`처럼 명시적 완료 필드만 후보 ID로 인정한다.
  - 일반 본문에 지나가는 `candidate-*` 언급은 완료 처리하지 않는다.
- `scripts/released_work_probe.py`
  - 저장소를 스캔해 `released_work.json`과 `LAST_RUN.md`를 만든다.
- `.github/workflows/released-work-ledger.yml`
  - 매일 09:05 UTC와 main push 때 `automation/released-work-last-run` sidecar를 발행한다.
- `src/auto_invest/analytics/autonomous_work_execution.py`
  - `released-work` evidence를 읽어 완료 후보를 `RELEASED`로 표시한다.
  - `learning_ledger`의 거절·실패 억제는 그대로 유지하고, 완료·출시 억제는 별도 장부로 분리한다.
- `scripts/autonomous_work_execution_probe.py`
  - `--repo-root`를 받으면 현재 checkout의 완료 스펙을 직접 스캔한다. 그래서 `released-work` sidecar 첫 발행 전 짧은 지연에도 같은 후보를 다시 고르지 않는다.

## 운영상 의미

- 스펙 078에서 완료된 `candidate-fd04772a23c5`는 더 이상 다음 작업 후보로 반복 선택되지 않는다.
- 최신 sidecar 조합과 현재 repo scan 기준 로컬 smoke 결과:
  - `candidate-fd04772a23c5` → `RELEASED`
  - 다음 선택 후보 → `candidate-e481b0309206`
  - 제목 → `레짐·성과 분석을 후보 점수화 입력으로 승격`
- 다음 세션은 "왜 다시 돈 경로 정렬 후보를 고르지 않나?"를 `released-work` 장부에서 확인하면 된다.
- 거절 후보와 완료 후보는 의미가 다르다. 실패·거절은 `learning_ledger`, 구현·머지 완료는 `released-work`가 담당한다.

## 배포 후 실제 실행 증거

- PR #436 merge commit: `1a9a5182ff78fb4bd2dfa1a89a486ed23535206a`
- `Deploy on merge to main` run `28555267958`: success, commit `1a9a518`
- `Autonomous work execution loop` run `28555267985`: success, commit `1a9a518`
- `Pipeline liveness watchdog` run `28555267972`: success, commit `1a9a518`
- PR #437 merge commit: `c8beb2561b0c328f0d56dc11e4d2cf91784b2867`
- `Deploy on merge to main` run `28555565031`: success, commit `c8beb25`
- `Released work ledger` run `28555267975`: failure. 원인은 publish step이 `set -u` 상태에서 env로 주입되지 않은 `${GITHUB_TOKEN}`을 직접 참조한 것이다.
- `Released work ledger` run `28555565017`: success, commit `c8beb25`
  - `overall_status=OK`
  - `released_count=1`
  - `candidate-fd04772a23c5=released`
  - 근거 파일 `specs/078-money-gate-alignment-loop/contracts/money-gate-alignment.md`
- `Pipeline liveness watchdog` dispatch run `28555617349`: success, commit `c8beb25`, `overall=OK`, `released-work=OK`

## 안전 경계

- 위험 등급: 2(운영 자동화 추가)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그, 외부 유료 서비스 변경: 없음
- workflow는 저장소 문서와 automation sidecar만 읽고, 자기 sidecar 브랜치만 갱신한다.
- 배포 성공은 dry-run worker 코드 반영이다. 실거래 전환이나 실제 주문을 의미하지 않는다.

## 검증

PR #436 머지 전:

- `uv run pytest tests/unit/test_released_work.py tests/unit/test_autonomous_work_execution.py tests/integration/test_released_work_probe.py tests/integration/test_autonomous_work_execution_probe.py -q` -> 18 passed
- 관련 `ruff check` -> All checks passed
- 최신 automation sidecar + repo scan local smoke -> `candidate-fd04772a23c5 RELEASED`, selected `candidate-e481b0309206`
- `uv run pytest` -> 2402 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- `uv run python scripts/check_handoff_facts.py` -> OK
- PR 품질 관문 -> success, mergeable clean, merge 방식으로 main에 병합

후속 publish token 보정:

- `uv run pytest tests/integration/test_released_work_probe.py -q` -> 2 passed
- `uv run ruff check tests/integration/test_released_work_probe.py` -> All checks passed
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- `uv run pytest` -> 2402 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- PR #437 품질 관문 -> success, mergeable clean, merge 방식으로 main에 병합
- #437 merge 후 `Released work ledger` run `28555565017`, deploy run `28555565031`, pipeline liveness dispatch run `28555617349` 모두 success

## 다음 세션 한 줄

스펙 079 이후 자율 작업 실행 루프는 완료된 `candidate-fd04772a23c5`를 `RELEASED`로 소비하고, 차순위 수익 후보 `candidate-e481b0309206`로 자동 이동한다. `released-work` sidecar publish token 누락은 #437에서 보정됐고, 최신 sidecar와 pipeline liveness는 둘 다 OK다.
