# HANDOFF 097 — 거시 후보 지도와 후보 재생성 루프 (2026-07-04 KST)

main 코드 베이스라인: `7438f38`(PR #473). 이 작업은 자율 작업 실행 루프가 frontier 후보까지
released-work로 닫힌 뒤에도 멈추지 않도록, 거시 후보 지도와 다음 frontier 후보 재생성 단계를
추가한 등급 2 운영 자동화 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/autonomous_work_execution.py`
  - `macro_candidate_map`을 보고서 JSON과 Markdown에 추가했다.
  - `candidate-macro-candidate-map-regenerator` 완료 후보를 추가했다.
  - 이 regenerator가 released-work로 닫히면 첫 지도 기반 후보
    `candidate-investment-edge-frontier-map`을 `EXECUTION_READY`로 발행한다.
  - 기존 regular, repair, operator approval, blocked 후보 우선순위는 유지했다.
- `tests/unit/test_autonomous_work_execution.py`
  - frontier release 뒤 regenerator 후보가 선택되는 회귀 테스트를 추가했다.
  - regenerator release 뒤 투자 엣지 후보가 선택되는 회귀 테스트를 추가했다.
  - 거시 후보 지도 JSON/Markdown 결정론 테스트를 추가했다.
- `tests/integration/test_autonomous_work_execution_probe.py`
  - probe JSON과 Markdown에 `macro_candidate_map`이 유지되는지 확인한다.
- `specs/093-macro-candidate-map-regenerator/`
  - SDD 산출물과 `completed_candidate_id: candidate-macro-candidate-map-regenerator` 완료 마커를 남겼다.

## 운영상 의미

- 최신 released-work sidecar는 스펙 093 완료 후보를 released로 기록한다.
- 최신 autonomous-work sidecar는 다음 실행 후보를 `candidate-investment-edge-frontier-map`으로 선택한다.
- 이 후보는 "투자 엣지 frontier 지도와 실험 후보 재생성" 작업이다. 운영자 추가 질문 없이 새 브랜치나
  worktree에서 SDD 두께를 판단하고 구현, 검증, PR, 자동 머지 절차로 진행할 수 있다.
- 후보는 위험 등급 2, 안전 영향 없음, 읽기 전용 작업 패킷이다.
- 돈 경로는 계속 `PREVIEW_ONLY`다. 실주문, 자본 배분, live 전략 변경은 전혀 하지 않았다.

## 배포 후 실제 실행 증거

- PR #473 merge commit: `7438f384cd191aa68605fc1e544ca7d886f04300`
- PR #473 feature commit: `23704a2f9cf7b9518323e4c27a2fbddceb59f5bf`
- PR #473 post-merge runs:
  - `Deploy on merge to main` run `28705183202`: success
  - `Released work ledger` run `28705183167`: success
  - `Autonomous work execution loop` run `28705183168`: success
- 최신 released-work sidecar:
  - commit `7438f384cd191aa68605fc1e544ca7d886f04300`
  - released count 14
  - `candidate-macro-candidate-map-regenerator` status `released`
  - source file `specs/093-macro-candidate-map-regenerator/data-model.md`
- 최신 autonomous-work sidecar:
  - commit `7438f384cd191aa68605fc1e544ca7d886f04300`
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-investment-edge-frontier-map`
  - risk grade 2, safety impact 없음
  - ranked 후보 1개, suppressed 후보 10개
  - 거시 후보 지도 첫 행: `investment_edge`, `exhausted`, 추천 후보 `candidate-investment-edge-frontier-map`
- deploy status:
  - main commit의 `Deploy on merge to main` 체크 `deploy` job은 success다.
  - 서버 audit_log와 GitHub Actions Summary 원문은 이 컨테이너에서 직접 확인하지 못한다.
  - deploy-audit sidecar는 2026-06-18 수동 실행이 최신이라 #473 직접 증거가 아니다.
  - KIS smoke sidecar 최신 run은 commit `bd03341` 기준 schedule 실행이라 #473 직접 증거가 아니다.

## 안전 경계

- 위험 등급: 2(자율 작업 실행 보고서의 다음 후보 선택 표면 변경)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #473 머지 전:

- `uv run pytest tests/unit/test_autonomous_work_execution.py tests/integration/test_autonomous_work_execution_probe.py -q`
  -> 26 passed
- `uv run python scripts/released_work_probe.py --repo-root . --json`
  -> `candidate-macro-candidate-map-regenerator` released
- 최신 sidecar replay와 `--repo-root .`
  -> `selected_work.candidate_id=candidate-investment-edge-frontier-map`,
  `status=EXECUTION_READY`, `risk_grade=2`, `safety_impact=[]`
- `uv run pytest`
  -> 2466 passed, 4 skipped
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

- `uv run pytest -q`는 처음에 2개 테스트가 실패했다. 원인은 `HANDOFF.md`가 아직 #473 이전 main을
  가리킨 것이며, 이 handoff가 고치는 낡은 HANDOFF 실패다.
- 이 handoff 갱신 뒤 `uv run python scripts/check_handoff_facts.py`
  -> OK
- 이 handoff 갱신 뒤 `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- 이 handoff 갱신 뒤 `uv run ruff check src tests`
  -> All checks passed
- 이 handoff 갱신 뒤 `uv run pytest -q`
  -> 2466 passed, 4 skipped

## 다음 세션 한 줄

스펙 093은 후보 고갈 상태를 거시 후보 지도로 바꾸고, 다음 실행 후보를
`candidate-investment-edge-frontier-map`으로 재생성했다. 다음 세션은 `/sync` 뒤 이 후보를 목표 스킬로
이어 받아 투자 엣지 frontier 지도와 첫 no-live 실험 후보를 만들면 된다.
