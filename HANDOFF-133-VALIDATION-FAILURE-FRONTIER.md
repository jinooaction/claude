# HANDOFF-133 — Validation Failure Frontier Progression

## 상태

#589가 main에 merge되어 `candidate-broad-frontier-expansion-validation-failures-22f38b8629eb`가 스펙 126으로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, 검증 실패 parent가 닫힌 뒤에도 대기로 물러서지 않고 다음 no-live 진단 후보를 자동으로 고르는 운영 계약이다.

핵심 결론은 이렇다. 막힌 검증 패키지 2개를 뭉뚱그려 "실패"로 두지 않고, 첫 후속 후보 `candidate-broad-validation-failure-command-replay-contract`로 전진하게 했다.

## 왜 했나

운영자는 "수단과 방법을 가리지 말라"와 "다각도로 폭넓게 사고하라"고 요구했다. 허용 가능한 해석은 안전장치를 우회하는 것이 아니라, 좁은 후보 목록과 막연한 대기 상태를 깨고 안전한 no-live 검토 축을 넓히는 것이다.

#582는 검증 실패 parent 후보를 만들었지만, parent가 released-work에 들어간 뒤 자동 루프가 다음 구체 후보 없이 기다릴 수 있었다. 그 상태는 앞으로도 같은 실패를 넓게 분해하지 못하게 만든다.

## 무엇을 고쳤나

- `specs/126-broad-validation-failure-frontier/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/autonomous_work_execution.py`가 `broad_validation_failure_frontier_map`을 JSON과 Markdown에 발행한다.
- 검증 실패 frontier는 네 축으로 나뉜다.
  - `candidate-broad-validation-failure-command-replay-contract`
  - `candidate-broad-validation-failure-data-readiness-contract`
  - `candidate-broad-validation-failure-package-kind-expansion-contract`
  - `candidate-broad-validation-failure-promotion-recheck-contract`
- parent 후보 `candidate-broad-frontier-expansion-validation-failures-22f38b8629eb`가 released-work에 있고 retryable `execution_failed` 패키지가 남아 있으면 첫 open child 후보를 선택한다.
- 첫 child가 released되면 두 번째 child `candidate-broad-validation-failure-data-readiness-contract`로 전진하는 회귀 테스트를 추가했다.
- `CLAUDE.md`와 `.specify/feature.json`은 최신 완료 스펙 126을 가리키게 맞췄다.

## 확인한 증거

- PR #589: `https://github.com/jinooaction/claude/pull/589`.
- 기능 커밋: `cfc28a9`.
- merge commit: `25b19625398cb6d9b325ab0f6d92c9566eea2d41`.
- GitHub PR quality gate: run `31500979164`, success.
- released-work run: `31501059269`, commit `25b1962`, released_count 45, 스펙 126 parent 후보 released 포함.
- autonomous-work run: `31501059038`, commit `25b1962`, selected_work `candidate-broad-validation-failure-command-replay-contract`, status `EXECUTION_READY`, blocked package count 2.
- deploy-on-merge run: `31501059251`, success.
- 로컬 focused 검증: `uv run pytest tests/unit/test_autonomous_work_execution.py -q` 45 passed.
- 로컬 전체 검증: `uv run pytest` 2728 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests` 통과.
- 기타 검증: `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.
- sidecar 재현: repo-root released-work scan 기준 parent가 닫힌 뒤 `candidate-broad-validation-failure-command-replay-contract`가 선택되고, command-replay 후보까지 released되면 data-readiness 후보로 전진한다.

## 안전 경계

이번 변경은 등급 2 운영 후보 확장이다.

브로커 API 호출, 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

현재 최신 autonomous-work selected_work는 `candidate-broad-validation-failure-command-replay-contract`다.

다음 작업은 candidate-result-executor와 candidate-packages 증거를 읽어 실패 명령, 종료 코드, 안전한 읽기 전용 재현 범위, 제한된 stdout/stderr 요약, 다음 진단 action을 기계 판독 계약으로 만드는 것이다. 같은 패키지를 무작정 재시도하거나 실거래를 여는 작업이 아니다.

이 후보까지 닫히면 다음 child는 `candidate-broad-validation-failure-data-readiness-contract`다. broad no-edge 축을 별도로 이어갈 때의 다음 후보는 `candidate-broad-no-edge-multi-horizon-signal-experiment`다.
