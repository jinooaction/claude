# HANDOFF 095 — 자율 성장 목적 함수와 탐색 예산 보정 (2026-07-03 KST)

main 코드 베이스라인: `944d2dc`(PR #469). 이 작업은
`candidate-autonomous-growth-objective-calibration`을 구현해 자율 작업 실행 보고서에 목적 함수,
탐색 예산, 중단 조건, 반복 학습 지표를 남기게 한 등급 2 운영 자동화 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/autonomous_work_execution.py`
  - `objective_calibration` 보고서 블록을 추가했다.
  - 후보별 `growth_leverage`, `evidence_readiness`, `validation_cost_fit`, `safety_margin`,
    `learning_value`와 총점을 결정론적으로 계산한다.
  - `max_ranked_candidates=10`, `max_parallel_candidates=1`, `max_validation_minutes=90`,
    handoff refresh, PR 품질 관문 필요 여부를 JSON과 Markdown에 발행한다.
  - 안전 표면 후보는 낮은 safety margin을 받지만 기존 operator-approval gate는 그대로 유지한다.
- `tests/unit/test_autonomous_work_execution.py`,
  `tests/integration/test_autonomous_work_execution_probe.py`
  - 목적 함수 보정 블록의 결정론, 선택 후보 정합성, 안전 표면 감점, probe JSON/Markdown 출력을
    회귀 테스트로 고정했다.
- `specs/091-autonomous-growth-objective-calibration/`
  - SDD 산출물과 `completed_candidate_id: candidate-autonomous-growth-objective-calibration`
    완료 마커를 남겼다.
  - released-work가 모든 tasks 완료 뒤 이 후보를 released 후보로 기록한다.

## 운영상 의미

- 다음 세션은 왜 특정 후보가 선택됐는지 priority score만 보지 않고, 성장 기여도·증거 준비도·검증 비용·안전 여유·학습 가치로 재현할 수 있다.
- Codex는 한 번에 후보 1개를 PR과 HANDOFF까지 닫는 예산 계약을 sidecar에서 읽을 수 있다.
- 목적 함수 보정은 보고와 검증 계약이다. 이번 변경은 기존 후보 ranking 핵심 순서를 바꾸지 않았고 돈 경로는 계속 `PREVIEW_ONLY`다.
- 최신 released-work sidecar는 `candidate-autonomous-growth-objective-calibration`을 released 처리했다.
- 최신 autonomous-work sidecar는 `objective_calibration` 블록을 발행한다. 다만 모든 macro 후보가 released된 뒤라 최신 `overall_status`는 `RELEASED`이고 `selected_work`는 닫힌 후보 `candidate-fd04772a23c5`다. 이것은 새 착수 후보가 아니라 실행 후보 고갈 신호로 읽어야 한다.

## 배포 후 실제 실행 증거

- PR #469 merge commit: `944d2dc952784dbfcb38390acaca796aaef26180`
- PR #469 feature commit: `eb11416`
- PR #469 post-merge runs:
  - `Deploy on merge to main` run `28662665531`: success
  - `Released work ledger` run `28662665530`: success
  - `Autonomous work execution loop` run `28662665589`: success
- 최신 released-work sidecar:
  - commit `944d2dc`
  - `candidate-autonomous-growth-objective-calibration` status `released`
  - source file `specs/091-autonomous-growth-objective-calibration/contracts/autonomous-growth-objective-calibration.md`
- 최신 autonomous-work sidecar:
  - commit `944d2dc`
  - `objective_version=autonomous-growth-objective-v1`
  - `max_parallel_candidates=1`, `max_ranked_candidates=10`, `max_validation_minutes=90`
  - `overall_status=RELEASED`; 새 `EXECUTION_READY` 후보 없음
- deploy status:
  - deploy job success
  - 서버 audit_log와 GitHub Actions Summary 원문은 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke 최신 sidecar는 success지만 commit `55ec2da` 기준 schedule run이라 #469 직접 증거는 아니다.

## 안전 경계

- 위험 등급: 2(운영 자동화 보고 계약과 다음 세션 판단 표면 변경)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #469 머지 전:

- `uv run pytest tests/unit/test_autonomous_work_execution.py -q`
  -> 14 passed
- `uv run pytest tests/integration/test_autonomous_work_execution_probe.py -q`
  -> 7 passed
- 최신 sidecar replay with repo-root override
  -> `objective_calibration.selected_candidate_id=candidate-autonomous-growth-objective-calibration`
  -> `max_parallel_candidates=1`, `ranked_count=1`, `released_count=8`
- `uv run python scripts/released_work_probe.py --repo-root . --json`
  -> `candidate-autonomous-growth-objective-calibration` released
- `uv run pytest`
  -> 2461 passed, 4 skipped
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

인계 브랜치에서:

- `uv run ruff check src tests`
  -> All checks passed
- `uv run pytest -q`는 처음에 2개 테스트가 실패했다. 원인은 `HANDOFF.md`가 아직 #467을 최신
  main으로 가리킨 것이며, 이 handoff가 고치는 낡은 HANDOFF 실패다.
- 이 handoff 갱신 뒤 `uv run python scripts/check_handoff_facts.py`
  -> OK
- 이 handoff 갱신 뒤 `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- 이 handoff 갱신 뒤 `uv run pytest -q`
  -> 2461 passed, 4 skipped

## 다음 세션 한 줄

스펙 091은 자율 성장 목적 함수와 탐색 예산을 sidecar 계약으로 고정했고, 최신 released-work가 해당
후보를 완료로 닫았다. 최신 autonomous-work에는 새 `EXECUTION_READY` 후보가 없으므로 다음 세션은
`/sync` 후 실행 후보 고갈 상태를 확인하고, 필요하면 다음 macro 후보 발굴 또는 후보 소스 재확장을
새 작업으로 잡으면 된다.
