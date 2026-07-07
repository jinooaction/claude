# HANDOFF 108 — 체결 비용 기준 계약 (2026-07-07 KST)

main 코드 베이스라인: `fa5b3d9`(PR #495). 이 작업은 스펙 103이 열어 둔
`candidate-execution-cost-basis-contract`를 완료 처리하고, accepted/fill 체결 비용 기준의 충분성과
관측 대기 상태를 기계 판독 계약으로 닫은 등급 2 체결 품질 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/execution_cost_basis.py`
  - execution-quality, KIS smoke, rebalance-micro-gtaa, money-path, pipeline-liveness,
    released-work, capital-path readiness 증거를 읽어 `CONTRACT_READY`, `OBSERVATION_WAIT`,
    `BLOCKED` 상태로 판정한다.
  - `execution_quality.execution_cost_basis`가 없으면 장애가 아니라 관측 대기로 두고,
    accepted/fill 수만 있고 측정 가능한 비용 기준이 없으면 ready로 과장하지 않는다.
  - broker, 주문, 자본, live 전략, whitelist/caps, 비밀값, 외부 유료 서비스는 건드리지 않는다.
- `scripts/execution_cost_basis_probe.py`
  - repo-root 또는 manifest 기반으로 기존 sidecar 파일을 읽어 JSON/Markdown 보고서를 출력한다.
- `tests/unit/test_execution_cost_basis.py`
  - ready cost basis, missing cost basis block, accepted sample without measurable basis,
    missing execution-quality, missing money-path를 고정했다.
- `tests/integration/test_execution_cost_basis_probe.py`
  - repo-root mode와 manifest replay를 검증한다.
- `tests/unit/test_autonomous_work_execution.py`
  - `candidate-execution-cost-basis-contract`가 released되면
    `candidate-broker-diagnostic-liveness-contract`로 전진하는 회귀 테스트를 추가했다.
- `specs/104-execution-cost-basis-contract/`
  - SDD 산출물과 `completed_candidate_id: candidate-execution-cost-basis-contract` 완료 마커를 남겼다.

## 운영상 의미

- 최신 실제 sidecar 증거를 재현하면 스펙 104 계약은 `OBSERVATION_WAIT`다.
- 이것은 실패가 아니라 비용 기준 관측 부족을 정직하게 분리한 상태다.
  필수 sidecar는 모두 parse되지만 `execution-quality`에 `execution_cost_basis` 블록이 없고,
  money-path accepted/fill 표본은 0건이다.
- `money-path.live_money_state.status=PREVIEW_ONLY`이고 `can_submit_real_orders=false`라
  이 계약은 새 표본을 만들기 위해 실주문을 시도하지 않는다.
- remote released-work sidecar는 `candidate-execution-cost-basis-contract`를 released로 기록했고,
  remote autonomous-work sidecar는 다음 실행 후보를
  `candidate-broker-diagnostic-liveness-contract`로 전진시켰다.
- 돈 경로는 계속 `PREVIEW_ONLY`이고 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #495 merge commit: `fa5b3d9d6afe0aa21f121c8640d0a0d5c78eeb46`
- PR #495 feature commit: `2fca88c37b330661cabd3df0d0df41f0a02ca73d`
- 직전 main: `da56a02`(PR #494, 스펙 103 인계)
- PR #495 post-merge runs:
  - `Deploy on merge to main` run `28847751730`: success
  - `Released work ledger` run `28847751712`: success
  - `Autonomous work execution loop` run `28847751752`: success
- released-work sidecar:
  - `released_count=25`
  - `candidate-execution-cost-basis-contract` released 확인
- autonomous-work sidecar:
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-broker-diagnostic-liveness-contract`
  - title `브로커 진단 생존성 계약`
  - risk grade 2
  - safety impact 없음
- deploy status:
  - main commit의 `Deploy on merge to main` 체크와 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar는 #495 배포의 직접 증거가 아니라 이전 schedule 실행 증거다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 현재 계약 판정

- `overall_status=OBSERVATION_WAIT`
- `cost_basis_state=COST_BASIS_OBSERVATION_WAIT`
- `execution_quality_has_cost_basis=false`
- `accepted_or_filled_orders=0`
- `measurable_fills=0`
- `live_money_status=PREVIEW_ONLY`
- `can_submit_real_orders=false`
- quality gates:
  - `required_evidence_parse=PASS`
  - `execution_cost_basis_observability=WAIT`
  - `accepted_fill_cost_basis=WAIT`
  - `money_path_context=PASS`
  - `safety_boundary=PASS`

## 안전 경계

- 위험 등급: 2(읽기 전용 체결 비용 기준 계약과 work packet 전진 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #495 머지 전:

- `uv run pytest tests/unit/test_execution_cost_basis.py tests/integration/test_execution_cost_basis_probe.py tests/unit/test_autonomous_work_execution.py`
  -> 37 passed
- latest remote sidecar replay
  -> 스펙 104 probe `overall_status=OBSERVATION_WAIT`,
  `execution_quality_has_cost_basis=false`, accepted/fill 0건,
  money-path `PREVIEW_ONLY`, next candidate `candidate-broker-diagnostic-liveness-contract`
- `uv run pytest`
  -> 2541 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- PR 품질 관문
  -> success
- 머지 직전 `uv run pytest`
  -> 2541 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- `uv run python scripts/released_work_probe.py --repo-root . --json`
  -> `candidate-execution-cost-basis-contract` released 확인
- `uv run python scripts/autonomous_work_execution_probe.py --evidence-dir <latest-sidecars> --repo-root . --json`
  -> `candidate-broker-diagnostic-liveness-contract` selected work 확인
- `uv run pytest -q`
  -> handoff 갱신 전 stale `HANDOFF.md` 때문에 하네스 2건 실패
  -> handoff 갱신 후 2541 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)

## 다음 세션 한 줄

스펙 104는 체결 비용 기준을 읽기 전용 계약으로 닫았고, 현재 실제 비용 기준은
`OBSERVATION_WAIT`로 남기되 자율 작업 후보는 `candidate-broker-diagnostic-liveness-contract`로 전진한다.
