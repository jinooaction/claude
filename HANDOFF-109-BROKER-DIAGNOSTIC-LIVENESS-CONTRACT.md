# HANDOFF 109 — 브로커 진단 생존성 계약 (2026-07-08 KST)

main 코드 베이스라인: `8d39235`(PR #497). 이 작업은 스펙 104가 열어 둔
`candidate-broker-diagnostic-liveness-contract`를 완료 처리하고, KIS smoke와 execution-quality의
broker smoke가 함께 살아 있는지 기계 판독 계약으로 닫은 등급 2 체결 품질 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/broker_diagnostic_liveness.py`
  - KIS smoke, execution-quality, pipeline-liveness, released-work, capital-path readiness 증거를 읽어
    `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED` 상태로 판정한다.
  - standalone KIS smoke 실패, 키 무효, smoke exit 비정상, 관련 pipeline critical 상태는 blocked로 둔다.
  - standalone KIS smoke는 건강하지만 execution-quality의 embedded broker smoke가 부족하면 장애가 아니라
    observation wait로 둔다.
  - broker API, 주문, 자본, live 전략, whitelist/caps, 비밀값, 외부 유료 서비스는 건드리지 않는다.
- `scripts/broker_diagnostic_liveness_probe.py`
  - repo-root 또는 manifest 기반으로 기존 sidecar 파일을 읽어 JSON/Markdown 보고서를 출력한다.
- `tests/unit/test_broker_diagnostic_liveness.py`
  - ready, embedded smoke 대기, missing evidence, KIS smoke 실패, pipeline critical, pipeline wait를 고정했다.
- `tests/integration/test_broker_diagnostic_liveness_probe.py`
  - repo-root mode와 manifest replay를 검증한다.
- `tests/unit/test_autonomous_work_execution.py`
  - `candidate-broker-diagnostic-liveness-contract`가 released되면
    `candidate-agent-ops-frontier-map`으로 전진하는 회귀 테스트를 추가했다.
- `specs/105-broker-diagnostic-liveness-contract/`
  - SDD 산출물과 `completed_candidate_id: candidate-broker-diagnostic-liveness-contract` 완료 마커를 남겼다.

## 운영상 의미

- 최신 실제 sidecar 증거를 재현하면 스펙 105 계약은 `CONTRACT_READY`다.
- `diagnostic_state=BROKER_DIAGNOSTIC_LIVE`이며 standalone KIS smoke, embedded broker smoke,
  관련 pipeline 상태가 모두 PASS다.
- 이것은 브로커 진단 경로가 관측 가능하다는 뜻이지 실주문 제출, 접수, 체결을 뜻하지 않는다.
- remote released-work sidecar는 `candidate-broker-diagnostic-liveness-contract`를 released로 기록했고,
  remote autonomous-work sidecar는 다음 실행 후보를 `candidate-agent-ops-frontier-map`으로 전진시켰다.
- 돈 경로는 계속 `PREVIEW_ONLY`이고 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #497 merge commit: `8d39235e6bcd7e2fb05ba147b5684256714694ae`
- PR #497 feature commit: `e99a78259d3f204c86faf3341c47d08b9c46f9a1`
- 직전 main: `a0d9be2`(PR #496, 스펙 104 인계)
- PR #497 post-merge runs:
  - `Deploy on merge to main` run `28904652073`: success
  - `Released work ledger` run `28904652098`: success
  - `Autonomous work execution loop` run `28904652137`: success
- released-work sidecar:
  - `released_count=26`
  - `candidate-broker-diagnostic-liveness-contract` released 확인
- autonomous-work sidecar:
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-agent-ops-frontier-map`
  - title `운영 체계 frontier 지도와 자율 루프 후보 재생성`
  - risk grade 2
  - safety impact 없음
- deploy status:
  - main commit의 `Deploy on merge to main` 체크와 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar는 #497 배포의 직접 증거가 아니라 이전 schedule 실행 증거다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 현재 계약 판정

- `overall_status=CONTRACT_READY`
- `diagnostic_state=BROKER_DIAGNOSTIC_LIVE`
- `completed_candidate_id=candidate-broker-diagnostic-liveness-contract`
- `next_candidate_id=candidate-agent-ops-frontier-map`
- quality gates:
  - `required_evidence_parse=PASS`
  - `kis_smoke_liveness=PASS`
  - `execution_quality_broker_smoke=PASS`
  - `pipeline_broker_diagnostic_liveness=PASS`
  - `safety_boundary=PASS`

## 안전 경계

- 위험 등급: 2(읽기 전용 브로커 진단 생존성 계약과 work packet 전진 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #497 머지 전:

- `uv run pytest tests/unit/test_broker_diagnostic_liveness.py tests/integration/test_broker_diagnostic_liveness_probe.py tests/unit/test_autonomous_work_execution.py`
  -> 40 passed
- latest remote sidecar replay
  -> 스펙 105 probe `overall_status=CONTRACT_READY`,
  `diagnostic_state=BROKER_DIAGNOSTIC_LIVE`, all gates PASS,
  next candidate `candidate-agent-ops-frontier-map`
- `uv run python scripts/released_work_probe.py --repo-root . --json`
  -> `candidate-broker-diagnostic-liveness-contract` released 확인
- `uv run python scripts/autonomous_work_execution_probe.py --evidence-dir <latest-sidecars> --repo-root . --json`
  -> `candidate-agent-ops-frontier-map` selected work 확인
- `uv run pytest`
  -> 2551 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- PR 품질 관문
  -> success
- 머지 직전 `uv run pytest`
  -> 2551 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- `uv run python scripts/broker_diagnostic_liveness_probe.py --repo-root <latest-sidecar-fixture> --format json`
  -> `CONTRACT_READY`, `BROKER_DIAGNOSTIC_LIVE`,
  `candidate-agent-ops-frontier-map` 확인
- `uv run pytest -q`
  -> 2551 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `git diff --check`
  -> 통과

## 다음 세션 한 줄

스펙 105는 브로커 진단 생존성을 읽기 전용 계약으로 닫았고, 현재 진단 경로는
`CONTRACT_READY`로 확인됐으며 자율 작업 후보는 `candidate-agent-ops-frontier-map`으로 전진한다.
