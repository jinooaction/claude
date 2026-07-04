# HANDOFF 098 — 투자 엣지 frontier 지도와 no-live 실험 후보 전진 (2026-07-04 KST)

main 코드 베이스라인: `02e7d6e`(PR #475). 이 작업은 스펙 093이 열어 둔
`candidate-investment-edge-frontier-map`을 완료 처리하고, 투자 엣지 영역 안쪽의 첫 no-live 실험 후보
`candidate-forward-regime-edge-experiment`로 자율 작업 루프가 전진하게 한 등급 2 운영 자동화 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/autonomous_work_execution.py`
  - 보고서 JSON과 Markdown에 `investment_edge_frontier_map`을 추가했다.
  - `candidate-investment-edge-frontier-map`이 released-work로 닫히면
    `candidate-forward-regime-edge-experiment`를 `EXECUTION_READY`로 발행한다.
  - 후속 투자 엣지 후보로 신호 다변화, 비용 차감 no-live 실험 후보를 지도에 남겼다.
  - 기존 regular, repair, operator approval, blocked 후보 우선순위는 유지했다.
- `scripts/autonomous_work_execution_probe.py`
  - `rebalance-paper-forward`, `edge-autoarm`, `money-path` sidecar를 읽기 전용 입력으로 추가했다.
- `tests/unit/test_autonomous_work_execution.py`
  - 투자 엣지 frontier 지도 JSON/Markdown 결정론 테스트를 추가했다.
  - 투자 엣지 후보 완료 뒤 no-live 실험 후보로 전진하는 회귀 테스트를 추가했다.
- `tests/integration/test_autonomous_work_execution_probe.py`
  - probe manifest와 출력 계약이 새 투자 엣지 지도 필드를 포함하는지 확인한다.
- `specs/094-investment-edge-frontier-map/`
  - SDD 산출물과 `completed_candidate_id: candidate-investment-edge-frontier-map` 완료 마커를 남겼다.

## 운영상 의미

- 최신 released-work sidecar는 스펙 094 완료 후보를 released로 기록한다.
- 최신 autonomous-work sidecar는 다음 실행 후보를 `candidate-forward-regime-edge-experiment`로 선택한다.
- 이 후보는 "forward 레짐 엣지 no-live 실험 설계" 작업이다. 운영자 추가 질문 없이 새 브랜치나 worktree에서
  SDD 두께를 판단하고 구현, 검증, PR, 자동 머지 절차로 진행할 수 있다.
- 후보 required inputs:
  - `automation/rebalance-paper-forward-last-run:LAST_RUN.md`
  - `automation/money-path-last-run:LAST_RUN.md`
  - `automation/released-work-last-run:released_work.json`
  - `automation/autonomous-evolution-last-run:learning_ledger.json`
  - `automation/pipeline-liveness-last-run:LAST_RUN.md`
- 후보는 위험 등급 2, 안전 영향 없음, 읽기 전용 작업 패킷이다.
- 돈 경로는 계속 `PREVIEW_ONLY`이고 money-path stage는 `BLOCKED`다. 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #475 merge commit: `02e7d6e3e444c7be67ada2cf11c4127b9dd1b6bc`
- PR #475 feature commit: `f18b8af7a84a6bbb45b64bcc70e9da58f356c91f`
- PR #475 post-merge runs:
  - `Deploy on merge to main` run `28706285176`: success
  - `Released work ledger` run `28706285172`: success
  - `Autonomous work execution loop` run `28706285171`: success
- 최신 released-work sidecar:
  - commit `02e7d6e3e444c7be67ada2cf11c4127b9dd1b6bc`
  - `candidate-investment-edge-frontier-map` status `released`
  - source file `specs/094-investment-edge-frontier-map/spec.md`
  - source field `completed_candidate_id`
- 최신 autonomous-work sidecar:
  - commit `02e7d6e3e444c7be67ada2cf11c4127b9dd1b6bc`
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-forward-regime-edge-experiment`
  - risk grade 2, safety impact 없음
  - 투자 엣지 frontier 지도 첫 행: `forward_regime_edge`, `open`,
    추천 후보 `candidate-forward-regime-edge-experiment`
- deploy status:
  - main commit의 `Deploy on merge to main` 체크 `deploy` job은 success다.
  - 서버 audit_log와 GitHub Actions Summary 원문은 이 컨테이너에서 직접 확인하지 못한다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 안전 경계

- 위험 등급: 2(자율 작업 실행 보고서의 다음 후보 선택 표면 변경)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #475 머지 전:

- `uv run pytest tests/unit/test_autonomous_work_execution.py tests/integration/test_autonomous_work_execution_probe.py`
  -> 28 passed
- latest sidecar replay와 `--repo-root .`
  -> release 전 `selected_work.candidate_id=candidate-investment-edge-frontier-map`
- `uv run python scripts/released_work_probe.py --repo-root . --json`
  -> `candidate-investment-edge-frontier-map` released
- latest sidecar replay와 `--repo-root .`
  -> release 후 `selected_work.candidate_id=candidate-forward-regime-edge-experiment`,
  `status=EXECUTION_READY`, required inputs에 forward paper, money-path, released-work, learning ledger,
  pipeline-liveness 포함
- `uv run pytest`
  -> 2468 passed, 4 skipped
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
- 머지 직전 `uv run pytest`
  -> 2468 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- `uv run pytest -q`는 처음에 2개 테스트가 실패했다. 원인은 `HANDOFF.md`가 아직 #475 이전 main을
  가리킨 것이며, 이 handoff가 고치는 낡은 HANDOFF 실패다.
- 이 handoff 갱신 뒤 `uv run python scripts/check_handoff_facts.py`
  -> OK
- 이 handoff 갱신 뒤 `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- 이 handoff 갱신 뒤 `uv run ruff check src tests`
  -> All checks passed
- 이 handoff 갱신 뒤 `uv run pytest -q`
  -> 2468 passed, 4 skipped

## 다음 세션 한 줄

스펙 094는 투자 엣지 frontier 후보를 완료 처리했고, 자율 작업 실행 루프의 다음 실행 후보는
`candidate-forward-regime-edge-experiment`다. 다음 세션은 `/sync` 뒤 이 후보를 목표 스킬로 이어 받아
레짐별 forward edge no-live 실험 계약과 검증 기준을 만들면 된다.
