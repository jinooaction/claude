# HANDOFF 088 — 오래된 증거와 성과 실패 분리 (2026-07-02 KST)

main 코드 베이스라인: `e77a42c`(PR #451). 최신 인계 베이스라인은 `4daf5d7`(PR #453)이고, 남았던 sidecar 순서 위험은 `Capital path readiness` workflow_dispatch run `28584170609`와 최신 schedule run `28584438033`으로 닫혔다. 이 작업은 자율 작업 실행 루프가 고른 `candidate-6ee3370e933d`를 처리한 등급 2 운영 보정이다. 오래된 증거, 완료 후보 잔향, sidecar 신선도 문제를 전략 성과 실패나 새 작업 후보처럼 보이지 않게 `capital-path-readiness` 보고서의 `observability_issues`로 분리했다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/capital_path_readiness.py`
  - `ReadinessObservabilityIssue`와 `observability_issues` JSON 필드를 추가했다.
  - `released-work`가 완료로 기록한 후보가 evolution backlog나 promotion 목록에 남으면 우선 후보에서 제외하고 `released_candidate_echo` 관측 이슈로 기록한다.
  - `pipeline-liveness`의 non-OK check는 `pipeline_liveness` 관측 이슈로 기록한다. 이 이슈는 money-path readiness, live money status, 기존 게이트를 바꾸지 않는다.
- `scripts/capital_path_readiness_probe.py`
  - manifest가 `released-work`와 `pipeline-liveness` sidecar를 수집한다.
- `.github/workflows/capital-path-readiness.yml`
  - 관련 parser 변경이 main에 들어오면 workflow가 다시 실행되도록 path filter를 보강했다.
- `specs/084-stale-evidence-failure-separation/`
  - SDD 산출물과 `completed_candidate_id: candidate-6ee3370e933d` 계약을 남겼다.

## 운영상 의미

- 완료된 후보가 upstream backlog에 남아 있어도 더 이상 “다음 작업 후보”처럼만 보이지 않는다.
- sidecar 지연이나 누락은 성과 실패가 아니라 관측 품질 문제로 분리된다.
- 다음 실제 자율 작업 선택은 `autonomous-work-execution`이 최종 권위다. #451 뒤 이 루프는 `candidate-6ee3370e933d`를 `RELEASED`로 억제하고 `candidate-facf2fa31834`를 선택했다.
- 같은 main push 안에서 `capital-path-readiness`가 `released-work`보다 먼저 실행될 수 있던 순서 위험은 #452 뒤 수동 workflow_dispatch run `28584170609`와 최신 schedule run `28584438033`으로 재검증했다. 최신 capital-path-readiness sidecar도 이제 `candidate-6ee3370e933d`를 priority가 아니라 suppressed와 `released-candidate-echo` 관측 이슈로 기록한다.

## 배포 후 실제 실행 증거

- PR #451 merge commit: `e77a42c4631daae2bcd422a1b40d2175e419caeb`
- feature commit: `96fc2b5b7d2a6ed90746ae6882aa6f7a47f13644`
- `Deploy on merge to main` run `28576674026`: success, commit `e77a42c`
- `Capital path readiness` run `28576674262`: success, commit `e77a42c`
- `Released work ledger` run `28576674252`: success, commit `e77a42c`
- `Autonomous work execution loop` run `28576674094`: success, commit `e77a42c`
- PR #452 handoff merge commit: `b92bee062609d37daadfb09c4bc433ea8417bd28`
- `Capital path readiness` workflow_dispatch run `28584170609`: success, commit `b92bee0`
- PR #453 handoff merge commit: `4daf5d7eebf9dfad906a87589b859186e7efa9a1`
- `Capital path readiness` schedule run `28584438033`: success, commit `b92bee0`

최신 `origin/automation/capital-path-readiness-last-run:capital_path_readiness.json`:

- `run_id=28584438033`
- `commit=b92bee062609d37daadfb09c4bc433ea8417bd28`
- `readiness_state=ACCUMULATING_EDGE`
- `priority_candidates=["candidate-facf2fa31834"]`
- `suppressed_candidates`에 `candidate-fd04772a23c5`, `candidate-e481b0309206`, `candidate-dff4f9344b02`, `candidate-6ee3370e933d` 포함
- `observability_issues`에 `released-candidate-echo` 4건 포함

최신 `origin/automation/released-work-last-run:released_work.json`:

- `run_id=28576674252`
- `commit=e77a42c4631daae2bcd422a1b40d2175e419caeb`
- `candidate-6ee3370e933d` -> `released`
- source: `specs/084-stale-evidence-failure-separation/contracts/capital-path-observability.md`

최신 `origin/automation/autonomous-work-execution-last-run:autonomous_work_execution.json`:

- `run_id=28576674094`
- `commit=e77a42c4631daae2bcd422a1b40d2175e419caeb`
- `candidate-6ee3370e933d`는 `RELEASED`, `CLOSED_RELEASED`
- 다음 선택 후보: `candidate-facf2fa31834`
- title: 공개 데이터 수집·교차 검증 확장
- autonomy level: `CODEX_AUTONOMOUS_START`

## 안전 경계

- 위험 등급: 2(운영 자동화 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 이 변경은 이미 발행된 sidecar를 읽고 자기 sidecar 보고 형식만 보강한다.

## 검증

PR #451 머지 전:

- `uv run pytest tests/unit/test_capital_path_readiness.py tests/integration/test_capital_path_readiness_probe.py` -> 10 passed
- 실제 sidecar dry-run -> 완료 후보 3건이 priority에서 suppressed와 `released-candidate-echo`로 분리됨
- `uv run pytest` -> 2435 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR 품질 관문 -> success

handoff 갱신 전 #451 main 기준:

- `uv run pytest -q` -> 2433 passed, 4 skipped, 2 failed
- 실패 원인: 코드 회귀가 아니라 `HANDOFF.md`가 아직 `f874b64`를 가리켜 `agent_harness_probe` 단위 테스트가 stale HANDOFF를 잡음
- #452 HANDOFF 갱신 뒤 `check_handoff_facts.py`와 strict 하네스는 다시 통과했고, 이번 sidecar 위험 정리도 같은 검증을 다시 통과했다.

sidecar 순서 위험 해소 재검증:

- `Capital path readiness` workflow_dispatch run `28584170609` -> success, 최신 sidecar에서 `candidate-6ee3370e933d`가 priority에서 빠지고 `released-candidate-echo`로 기록됨
- `Capital path readiness` schedule run `28584438033` -> success, 최신 sidecar에서 같은 결론 유지
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- `uv run ruff check src tests` -> All checks passed
- `uv run pytest` -> 2435 passed, 4 skipped

## 다음 세션 한 줄

스펙 084는 완료됐고 남은 sidecar 순서 위험도 닫혔다. 오래된 증거와 완료 후보 잔향은 이제 `capital-path-readiness.observability_issues`로 분리되고, `candidate-6ee3370e933d`는 `released-work`와 최신 capital-path-readiness 양쪽에서 완료 후보로 억제되어 다음 실제 착수 후보는 `candidate-facf2fa31834`다.
