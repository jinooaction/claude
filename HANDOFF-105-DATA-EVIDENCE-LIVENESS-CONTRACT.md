# HANDOFF 105 — 데이터 증거 생존성 계약 (2026-07-07 KST)

main 코드 베이스라인: `28bfbf1`(PR #489). 이 작업은 스펙 100이 열어 둔
`candidate-data-evidence-liveness-contract`를 완료 처리하고, `pipeline-liveness`의
`collect-public-data`와 `regime-stratify` 체크를 데이터 품질 후보 관점의 PASS/WAIT/FAIL 계약으로
분리한 등급 2 데이터 품질 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/data_evidence_liveness.py`
  - `public-data`, `regime-stratify`, `pipeline-liveness`, `released-work`,
    `capital-path-readiness` sidecar를 읽어 `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를
    판정한다.
  - registry 파싱, 필수 데이터 check 등록, check status, source timestamp 일치, source freshness,
    safety boundary를 quality gate로 분리한다.
  - `pipeline-liveness`가 깨졌거나 필수 check가 없으면 `BLOCKED`, registry는 살아 있고 데이터
    sidecar만 늦으면 `OBSERVATION_WAIT`로 분리한다.
  - broker, 주문, 자본, live 전략, whitelist/caps, 비밀값, 외부 유료 서비스는 건드리지 않는다.
- `scripts/data_evidence_liveness_probe.py`
  - repo-root 또는 manifest 기반으로 기존 sidecar 파일을 읽어 JSON/Markdown 보고서를 출력한다.
- `tests/unit/test_data_evidence_liveness.py`
  - ready, stale wait, missing pipeline, missing registration, missing source timestamp, timestamp mismatch,
    `last_success_utc` fallback, malformed pipeline JSON을 고정했다.
- `tests/integration/test_data_evidence_liveness_probe.py`
  - repo-root mode와 manifest replay를 검증한다.
- `tests/unit/test_autonomous_work_execution.py`
  - `candidate-data-evidence-liveness-contract`가 released되면
    `candidate-execution-quality-frontier-map`으로 전진하는 회귀 테스트를 추가했다.
- `specs/101-data-evidence-liveness-contract/`
  - SDD 산출물과 `completed_candidate_id: candidate-data-evidence-liveness-contract` 완료 마커를 남겼다.
  - post-merge HANDOFF 갱신을 released-work tasks 바깥에 두어, future handoff 작업 때문에 후보 release가
    막히지 않게 했다.

## 운영상 의미

- 최신 실제 sidecar 증거를 재현하면 스펙 101 계약은 `CONTRACT_READY`다.
- `collect-public-data`와 `regime-stratify`는 모두 pipeline-liveness에서 `OK`이고, 각각의
  pipeline timestamp가 source LAST_RUN timestamp와 일치한다.
- remote released-work sidecar는 `candidate-data-evidence-liveness-contract`를 released로 읽었다.
- remote autonomous-work sidecar는 다음 실행 후보를 `candidate-execution-quality-frontier-map`으로 선택했다.
- 돈 경로는 계속 `PREVIEW_ONLY`이고 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #489 merge commit: `28bfbf1f0a2f2a7d36823ab8a3aedc3fd0807aba`
- PR #489 feature commit: `646d2ea`
- 직전 main: `304d3cd`(PR #488, 스펙 100 인계)
- PR #489 post-merge runs:
  - `Deploy on merge to main` run `28820754814`: success
  - `Released work ledger` run `28820754885`: success
  - `Autonomous work execution loop` run `28820754816`: success
- released-work sidecar:
  - timestamp `2026-07-06T20:22:50.476149Z`
  - `candidate-data-evidence-liveness-contract` 포함
  - released count 22
- autonomous-work sidecar:
  - timestamp `2026-07-06T20:22:50Z`
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-execution-quality-frontier-map`
  - domain `execution_quality`
  - `data_evidence_liveness=released`
- deploy status:
  - main commit의 `Deploy on merge to main` 체크와 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar 최신 run은 #489 배포의 직접 증거가 아니라 이전 schedule 실행 증거이므로 #489 배포
    근거로 쓰지 않는다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 현재 계약 판정

- `overall_status=CONTRACT_READY`
- quality gates:
  - `pipeline_report_parse=PASS`
  - `data_check_registration=PASS`
  - `data_liveness_status=PASS`
  - `source_timestamp_consistency=PASS`
  - `source_freshness=PASS`
  - `safety_boundary=PASS`
- data checks:
  - `collect-public-data`
    - status `OK`
    - pipeline timestamp `2026-07-04T05:05:20Z`
    - source timestamp `2026-07-04T05:05:20Z`
    - source match `true`
  - `regime-stratify`
    - status `OK`
    - pipeline timestamp `2026-07-04T01:09:16Z`
    - source timestamp `2026-07-04T01:09:16Z`
    - source match `true`

## 안전 경계

- 위험 등급: 2(읽기 전용 데이터 증거 생존성 계약과 work packet 전진 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #489 머지 전:

- `uv run pytest tests/unit/test_data_evidence_liveness.py tests/integration/test_data_evidence_liveness_probe.py tests/unit/test_autonomous_work_execution.py`
  -> 36 passed
- latest sidecar replay
  -> 스펙 101 probe `overall_status=CONTRACT_READY`, 모든 gate PASS,
  `collect-public-data`와 `regime-stratify` source timestamp 일치
- released-work local replay
  -> `candidate-data-evidence-liveness-contract` released 확인
- autonomous-work local replay
  -> `candidate-execution-quality-frontier-map` selected work 확인
- `uv run pytest`
  -> 2523 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- PR 품질 관문
  -> success
- 머지 직전 `uv run pytest`
  -> 2523 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- main 기준 첫 `uv run pytest -q`
  -> HANDOFF stale 때문에 `test_agent_harness_probe.py` 2건 실패, 나머지 2521 passed, 4 skipped
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run ruff check src tests`
  -> All checks passed
- HANDOFF 갱신 뒤 `uv run pytest -q`
  -> 2523 passed, 4 skipped

## 다음 세션 한 줄

스펙 101은 데이터 증거 생존성을 `CONTRACT_READY` 계약으로 닫았고, 자율 작업 후보는 이제
`candidate-execution-quality-frontier-map`으로 전진한다.
