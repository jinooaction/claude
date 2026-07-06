# HANDOFF 103 — 공개 데이터 입력 품질 계약 (2026-07-06 KST)

main 코드 베이스라인: `c3803cd`(PR #485). 이 작업은 스펙 098이 열어 둔
`candidate-public-data-input-quality-contract`를 완료 처리하고, 공개 데이터 입력 품질을
다음 투자 후보의 연구 입력으로 쓸 수 있는지 기계 판독 계약으로 닫은 등급 2 데이터 품질 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/public_data_input_quality.py`
  - public-data summary, regime.json, regime_timeline.csv, regime-stratify, pipeline-liveness,
    released-work, capital-path readiness 증거를 읽어 `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`
    상태로 판정한다.
  - evidence surface와 quality gate를 JSON/Markdown으로 발행한다.
  - public-data 발행 완전성, 교차검증 품질, 레짐 타임라인 커버리지, sidecar 생존성 게이트를 분리한다.
  - broker, 주문, 자본, live 전략, whitelist/caps, 비밀값, 외부 유료 서비스는 건드리지 않는다.
- `scripts/public_data_input_quality_probe.py`
  - repo-root 또는 manifest 기반으로 기존 sidecar 파일을 읽어 보고서를 출력한다.
- `tests/unit/test_public_data_input_quality.py`
  - 정상, summary 누락, 교차검증 실패, liveness 대기, 낮은 regime-stratify 관측, malformed regime을 고정했다.
- `tests/integration/test_public_data_input_quality_probe.py`
  - manifest replay와 표준 sidecar layout 읽기를 검증한다.
- `tests/unit/test_autonomous_work_execution.py`
  - `candidate-public-data-input-quality-contract`가 released되면
    `candidate-regime-timeline-coverage-contract`로 전진하는 회귀 테스트를 추가했다.
- `specs/099-public-data-input-quality-contract/`
  - SDD 산출물과 `completed_candidate_id: candidate-public-data-input-quality-contract` 완료 마커를 남겼다.

## 운영상 의미

- 최신 released-work sidecar는 스펙 099 완료 후보를 released로 기록한다.
- 최신 autonomous-work sidecar는 다음 실행 후보를
  `candidate-regime-timeline-coverage-contract`로 선택한다.
- 새 후보는 "레짐 타임라인 커버리지 계약" 작업이다. 운영자 추가 질문 없이 새 브랜치나 worktree에서
  SDD 두께를 판단하고 구현, 검증, PR, 자동 머지 절차로 진행할 수 있다.
- 데이터 증거 frontier 지도 현재 상태:
  - 공개 데이터 입력 품질: released
  - 레짐 타임라인 커버리지: open, `candidate-regime-timeline-coverage-contract`
  - 데이터 증거 생존성: open, `candidate-data-evidence-liveness-contract`
- 공개 데이터 입력 품질 계약 최신 판정:
  - `overall_status=CONTRACT_READY`
  - public-data 11/11개 발행
  - 교차검증 5개 PASS, 최소 overlap 13일
  - regime timeline 2372행
  - regime-stratify total return 751일
  - collect-public-data와 regime-stratify liveness OK
- 돈 경로는 계속 `PREVIEW_ONLY`이고 capital readiness는 `LIVE_BLOCKED`다. 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #485 merge commit: `c3803cdfea88442d4c8556b85a6f7c2724b7ba77`
- PR #485 feature commit: `14259585020b0b25037e5b1210edca5c73aa80e8`
- PR #485 post-merge runs:
  - `Deploy on merge to main` run `28791708696`: success
  - `Released work ledger` run `28791708832`: success
  - `Autonomous work execution loop` run `28791708758`: success
- 최신 released-work sidecar:
  - commit `c3803cdfea88442d4c8556b85a6f7c2724b7ba77`
  - released count 20
  - `candidate-public-data-input-quality-contract` status `released`
  - source file `specs/099-public-data-input-quality-contract/spec.md`
  - source field `completed_candidate_id`
- 최신 autonomous-work sidecar:
  - commit `c3803cdfea88442d4c8556b85a6f7c2724b7ba77`
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-regime-timeline-coverage-contract`
  - risk grade 2, safety impact 없음
  - data evidence map: 공개 데이터 입력 품질 released, 레짐 타임라인 커버리지 open, 데이터 증거 생존성 open
- deploy status:
  - main commit의 `Deploy on merge to main` 체크와 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar는 #485 배포의 직접 증거가 아니다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 안전 경계

- 위험 등급: 2(읽기 전용 공개 데이터 입력 품질 계약과 work packet 전진 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #485 머지 전:

- `uv run pytest tests/unit/test_public_data_input_quality.py tests/integration/test_public_data_input_quality_probe.py tests/unit/test_autonomous_work_execution.py`
  -> 32 passed
- latest sidecar replay
  -> 스펙 099 probe `overall_status=CONTRACT_READY`, public-data 11/11, 교차검증 5개 PASS,
  timeline 2372행, stratified return 751일, liveness OK
- released-work 로컬 재현
  -> `candidate-public-data-input-quality-contract` released
- autonomous-work 로컬 재현
  -> `candidate-regime-timeline-coverage-contract` selected work
- `uv run pytest`
  -> 2500 passed, 4 skipped
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
  -> 2500 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- HANDOFF 갱신 전 `uv run pytest -q`
  -> 2 failed, 2498 passed, 4 skipped. 실패 2건은 낡은 HANDOFF main 커밋 행 때문에 strict harness가 의도적으로 막은 것이다.
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run pytest -q`
  -> 2500 passed, 4 skipped

## 다음 세션 한 줄

스펙 099는 공개 데이터 입력 품질 후보를 `CONTRACT_READY` 계약과 완료 마커로 닫았고, 자율 작업 실행 루프의 다음 실행 후보는
레짐 라벨 결측·관측 수·전망적 조인 품질을 검증하는 `candidate-regime-timeline-coverage-contract`다.
