# HANDOFF 096 — 자율 후보 고갈 뒤 frontier 발굴 후보 폐쇄 (2026-07-04 KST)

main 코드 베이스라인: `b004d2f`(PR #471). 이 작업은
`candidate-autonomous-frontier-discovery`를 구현해 기존 macro 후보 3개가 모두 닫힌 뒤
released 후보를 새 착수 후보처럼 보여주지 않고 frontier 발굴 후보를 발행하게 한 등급 2 운영
자동화 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/autonomous_work_execution.py`
  - `FRONTIER_DISCOVERY_CANDIDATE_ID`와 frontier discovery work packet을 추가했다.
  - 기존 macro 후보 3개가 모두 released 또는 이미 후보 목록에 있을 때만 frontier 후보를 만든다.
  - 일반 실행 후보, 운영자 승인 필요 후보, 기존 macro 후보가 있으면 frontier 후보는 끼어들지 않는다.
- `tests/unit/test_autonomous_work_execution.py`
  - macro 후보가 모두 닫힌 뒤 frontier 후보가 선택되는 회귀 테스트를 추가했다.
  - 일반 실행 후보가 있을 때 frontier 후보가 가리지 않는 회귀 테스트를 추가했다.
- `specs/092-frontier-candidate-discovery/`
  - SDD 산출물과 `completed_candidate_id: candidate-autonomous-frontier-discovery` 완료 마커를 남겼다.
  - released-work가 모든 tasks 완료 뒤 이 frontier 후보를 released 후보로 기록한다.

## 운영상 의미

- 최신 sidecar 입력만 재생하면 `candidate-autonomous-frontier-discovery`가 `EXECUTION_READY`로 선택된다.
- main 머지 뒤에는 같은 스펙 092 산출물의 완료 마커가 frontier 후보도 released-work로 닫았다.
- 따라서 최신 autonomous-work sidecar에는 새 `EXECUTION_READY` 후보가 없다. `selected_work=candidate-fd04772a23c5`는 닫힌 released 후보이며 새 착수 후보가 아니다.
- 다음 세션은 이 상태를 "작업 누락"이 아니라 "frontier 후보까지 처리된 뒤 다시 후보 고갈 상태"로 읽어야 한다. 새 작업을 하려면 후보 소스 재생성 또는 더 거시적인 후보 발굴 루프를 새 후보로 잡아야 한다.
- 돈 경로는 계속 `PREVIEW_ONLY`다.

## 배포 후 실제 실행 증거

- PR #471 merge commit: `b004d2f9373e24cf5adea36c52ad6a25f77a5dc8`
- PR #471 feature commit: `d90bd71`
- PR #471 post-merge runs:
  - `Deploy on merge to main` run `28689000449`: success
  - `Released work ledger` run `28689000437`: success
  - `Autonomous work execution loop` run `28689000427`: success
- 최신 released-work sidecar:
  - commit `b004d2f`
  - released count 13
  - `candidate-autonomous-frontier-discovery` status `released`
  - source file `specs/092-frontier-candidate-discovery/contracts/frontier-candidate-discovery.md`
- 최신 autonomous-work sidecar:
  - commit `b004d2f`
  - `overall_status=RELEASED`
  - ranked 후보 0개, suppressed 후보 10개
  - `selected_work=candidate-fd04772a23c5`, status `RELEASED`
- deploy status:
  - main commit의 `Deploy on merge to main` 체크 `deploy` job은 success다.
  - 서버 audit_log와 GitHub Actions Summary 원문은 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke 최신 sidecar는 success지만 commit `55ec2da` 기준 schedule run이라 #471 직접 증거는 아니다.

## 안전 경계

- 위험 등급: 2(자율 작업 실행 보고서의 다음 후보 선택 표면 변경)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #471 머지 전:

- `uv run pytest tests/unit/test_autonomous_work_execution.py -q`
  -> 16 passed
- `uv run pytest tests/integration/test_autonomous_work_execution_probe.py -q`
  -> 7 passed
- 최신 sidecar replay
  -> `selected_work.candidate_id=candidate-autonomous-frontier-discovery`, `status=EXECUTION_READY`, `risk_grade=2`, `safety_impact=[]`
- 같은 sidecar에 `--repo-root .`를 더한 완료 마커 적용 뒤 관찰
  -> `selected_work.candidate_id=candidate-fd04772a23c5`, `status=RELEASED`
- `uv run python scripts/released_work_probe.py --repo-root . --json`
  -> `candidate-autonomous-frontier-discovery` released
- `uv run pytest`
  -> 2463 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `git diff --cached --check`
  -> pass
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- PR 품질 관문
  -> success

인계 브랜치에서:

- `uv run pytest -q`는 처음에 2개 테스트가 실패했다. 원인은 `HANDOFF.md`가 아직 #471 이전 main을
  가리킨 것이며, 이 handoff가 고치는 낡은 HANDOFF 실패다.
- 이 handoff 갱신 뒤 `uv run python scripts/check_handoff_facts.py`
  -> OK
- 이 handoff 갱신 뒤 `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- 이 handoff 갱신 뒤 `uv run ruff check src tests`
  -> All checks passed
- 이 handoff 갱신 뒤 `uv run pytest -q`
  -> 2463 passed, 4 skipped

## 다음 세션 한 줄

스펙 092는 후보 고갈 뒤 frontier 발굴 후보를 만들고 그 후보까지 released-work로 닫았다. 최신
autonomous-work에는 새 `EXECUTION_READY` 후보가 없으므로 다음 세션은 `/sync` 뒤 후보 소스 재생성
또는 더 거시적인 후보 발굴 루프를 새 작업으로 잡아야 한다.
