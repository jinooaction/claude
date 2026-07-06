# HANDOFF 102 — 데이터 증거 frontier 지도 (2026-07-06 KST)

main 코드 베이스라인: `6aa85c6`(PR #483). 이 작업은 스펙 097이 열어 둔
`candidate-data-evidence-frontier-map`을 완료 처리하고, 공개 데이터·레짐 층화·파이프라인 생존성 증거를
다음 데이터 입력 품질 후보로 분해한 등급 2 운영 자동화 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/autonomous_work_execution.py`
  - `data_evidence_frontier_map`을 JSON과 Markdown 보고서에 추가했다.
  - 공개 데이터 입력 품질, 레짐 타임라인 커버리지, 데이터 증거 생존성 3개 영역을 안정적인 후보 id와
    required inputs로 발행한다.
  - `candidate-data-evidence-frontier-map`이 released-work로 닫힌 뒤 첫 후보
    `candidate-public-data-input-quality-contract`를 선택한다.
  - public-data와 regime-stratify sidecar 요약을 읽기 전용 증거 표면으로 파싱한다.
  - broker, 주문, 자본, live 전략, whitelist/caps, 비밀값, 외부 유료 서비스는 건드리지 않는다.
- `scripts/autonomous_work_execution_probe.py`
  - `automation/public-data`와 `automation/regime-stratify-last-run`을 manifest에 추가했다.
- `tests/unit/test_autonomous_work_execution.py`
  - 데이터 증거 frontier 지도 발행, 완료 후보 닫힘, 첫 입력 품질 후보 선택, public-data/regime-stratify 파싱을 고정했다.
- `tests/integration/test_autonomous_work_execution_probe.py`
  - probe manifest가 새 sidecar 입력을 포함하는지 확인한다.
- `specs/098-data-evidence-frontier-map/`
  - SDD 산출물과 `completed_candidate_id: candidate-data-evidence-frontier-map` 완료 마커를 남겼다.

## 운영상 의미

- 최신 released-work sidecar는 스펙 098 완료 후보를 released로 기록한다.
- 최신 autonomous-work sidecar는 다음 실행 후보를
  `candidate-public-data-input-quality-contract`로 선택한다.
- 새 후보는 "공개 데이터 입력 품질 계약" 작업이다. 운영자 추가 질문 없이 새 브랜치나 worktree에서
  SDD 두께를 판단하고 구현, 검증, PR, 자동 머지 절차로 진행할 수 있다.
- 데이터 증거 frontier 지도는 현재 세 영역을 모두 open으로 본다.
  - 공개 데이터 입력 품질: `candidate-public-data-input-quality-contract`
  - 레짐 타임라인 커버리지: `candidate-regime-timeline-coverage-contract`
  - 데이터 증거 생존성: `candidate-data-evidence-liveness-contract`
- 첫 후보 required inputs:
  - `automation/public-data:LAST_RUN.md`
  - `automation/public-data:summary.json`
  - `automation/public-data:regime.json`
  - `automation/public-data:regime_timeline.csv`
  - `automation/regime-stratify-last-run:LAST_RUN.md`
  - `automation/pipeline-liveness-last-run:LAST_RUN.md`
  - `automation/released-work-last-run:released_work.json`
  - `automation/capital-path-readiness-last-run:capital_path_readiness.json`
- 돈 경로는 계속 `PREVIEW_ONLY`이고 money-path stage는 `BLOCKED`다. 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #483 merge commit: `6aa85c6f91a40f000ff3297928b3d346c4811124`
- PR #483 feature commit: `3e6d8e62d62536353817acdff6daf0d2ed0b5114`
- PR #483 post-merge runs:
  - `Deploy on merge to main` run `28786862434`: success
  - `Released work ledger` run `28786862491`: success
  - `Autonomous work execution loop` run `28786862604`: success
- 최신 released-work sidecar:
  - commit `6aa85c6f91a40f000ff3297928b3d346c4811124`
  - `candidate-data-evidence-frontier-map` status `released`
  - source file `specs/098-data-evidence-frontier-map/spec.md`
  - source field `completed_candidate_id`
- 최신 autonomous-work sidecar:
  - commit `6aa85c6f91a40f000ff3297928b3d346c4811124`
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-public-data-input-quality-contract`
  - risk grade 2, safety impact 없음
  - public-data summary: `overall_ok=True, published=11`
  - regime-stratify summary: `total_return_days=751`
  - data evidence map: 공개 데이터 입력 품질, 레짐 타임라인 커버리지, 데이터 증거 생존성 모두 open
- deploy status:
  - main commit의 `Deploy on merge to main` 체크와 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar는 #483 배포의 직접 증거가 아니다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 안전 경계

- 위험 등급: 2(읽기 전용 데이터 품질 후보 지도와 work packet 보고서 확장)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #483 머지 전:

- `uv run pytest tests/unit/test_autonomous_work_execution.py tests/integration/test_autonomous_work_execution_probe.py`
  -> 30 passed
- latest sidecar replay와 `--repo-root .`
  -> `candidate-data-evidence-frontier-map` 선택, public-data parse ok, regime-stratify parse ok
- released-work 로컬 재현
  -> `candidate-data-evidence-frontier-map` released
- autonomous-work 로컬 재현
  -> `candidate-public-data-input-quality-contract` 선택
- `uv run pytest`
  -> 2491 passed, 4 skipped
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
  -> 2491 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- HANDOFF 갱신 전 `uv run pytest -q`
  -> 2 failed, 2489 passed, 4 skipped. 실패 2건은 낡은 HANDOFF main 커밋 행 때문에 strict harness가 의도적으로 막은 것이다.
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run pytest -q`
  -> 2491 passed, 4 skipped

## 다음 세션 한 줄

스펙 098은 데이터 증거 frontier 후보를 완료 처리했고, 자율 작업 실행 루프의 다음 실행 후보는
public-data와 regime evidence를 검증 게이트로 묶는 `candidate-public-data-input-quality-contract`다.
