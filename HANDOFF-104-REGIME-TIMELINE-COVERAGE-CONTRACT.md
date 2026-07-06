# HANDOFF 104 — 레짐 타임라인 커버리지 계약 (2026-07-06 KST)

main 코드 베이스라인: `48314cd`(PR #487). 이 작업은 스펙 099가 열어 둔
`candidate-regime-timeline-coverage-contract`를 완료 처리하고, 레짐 타임라인의 라벨 커버리지,
레짐별 관측 수, 전망적 조인 품질을 기계 판독 계약으로 닫은 등급 2 데이터 품질 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/regime_timeline_coverage.py`
  - `regime_timeline.csv`, `regime-stratify`, `pipeline-liveness`, `released-work` 증거를 읽어
    `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED` 상태로 판정한다.
  - 타임라인 날짜 순서, canonical label 존재, 레짐별 joined return 관측 하한, d+1 전망적 조인,
    sidecar 생존성, 완료 후보 장부 반영 여부를 quality gate로 분리한다.
  - broker, 주문, 자본, live 전략, whitelist/caps, 비밀값, 외부 유료 서비스는 건드리지 않는다.
- `scripts/regime_timeline_coverage_probe.py`
  - repo-root 또는 manifest 기반으로 기존 sidecar 파일을 읽어 JSON/Markdown 보고서를 출력한다.
- `tests/unit/test_regime_timeline_coverage.py`
  - 정상 타임라인, 라벨 누락, 중복 날짜, 순서 오류, 희귀 레짐 관측 대기, malformed stratify,
    count mismatch, forward join 실패, released-work closure를 고정했다.
- `tests/integration/test_regime_timeline_coverage_probe.py`
  - repo-root mode와 manifest replay를 검증한다.
- `tests/unit/test_autonomous_work_execution.py`
  - `candidate-regime-timeline-coverage-contract`가 released되면
    `candidate-data-evidence-liveness-contract`로 전진하는 회귀 테스트를 추가했다.
- `specs/100-regime-timeline-coverage-contract/`
  - SDD 산출물과 `completed_candidate_id: candidate-regime-timeline-coverage-contract` 완료 마커를 남겼다.
  - 이 인계 브랜치에서 T018/T023을 완료 체크로 닫아 released-work가 스펙 100을 완료 후보로 읽을 수 있게 했다.

## 운영상 의미

- 최신 실제 sidecar 증거를 재현하면 스펙 100 계약은 `OBSERVATION_WAIT`다.
- 이것은 실패가 아니라 rare regime 관측 부족을 정직하게 분리한 상태다.
  타임라인 자체와 d+1 전망적 조인은 통과했고, `RISK_OFF` joined return 관측이 일부 section에서 7일이라
  추가 관측을 기다린다.
- 이 인계 브랜치의 완료 체크 상태 기준으로 `released_work_probe.py --repo-root .`는
  `candidate-regime-timeline-coverage-contract`를 released로 기록한다.
- 같은 상태에서 `autonomous_work_execution_probe.py --repo-root .`를 재현하면 다음 실행 후보는
  `candidate-data-evidence-liveness-contract`다.
- `released-work-ledger`와 `autonomous-work-execution` workflow는 `specs/**/tasks.md` main push에서
  다시 실행되므로, 이 인계 PR 병합 뒤 remote sidecar도 같은 전진 결론을 발행해야 한다.
- 돈 경로는 계속 `PREVIEW_ONLY`이고 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #487 merge commit: `48314cd8c622340f4a7879a92d48a1cbb0e25ed5`
- PR #487 feature commit: `7a2ba581238ef191af0d8c493a769d98499bfd1f`
- 직전 main: `9ed61b8`(PR #486, 스펙 099 인계)
- PR #487 post-merge runs:
  - `Deploy on merge to main` run `28799231896`: success
  - `Released work ledger` run `28799231124`: success
  - `Autonomous work execution loop` run `28799231156`: success
- 코드 PR post-merge sidecar 주의:
  - #487 코드 PR 시점에는 T018/T023이 아직 인계 전 미완료라 remote released-work가 스펙 100을 완료 후보로 읽지 않았다.
  - 이 인계 브랜치가 그 체크 상태를 닫고, 로컬 released-work/autonomous-work 재현에서 다음 후보 전진을 확인했다.
- deploy status:
  - main commit의 `Deploy on merge to main` 체크와 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar는 #487 배포의 직접 증거가 아니다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 현재 계약 판정

- `overall_status=OBSERVATION_WAIT`
- timeline: 2372행, 2017-01-03부터 2026-07-02까지 날짜 순서 정상
- canonical label counts:
  - `RISK_ON=1414`
  - `CAUTION=894`
  - `RISK_OFF=64`
- quality gates:
  - `timeline_shape=PASS`
  - `timeline_label_coverage=PASS`
  - `forward_join_quality=PASS`
  - `sidecar_liveness=PASS`
  - `stratified_observation_floor=WAIT`
- sparse sections:
  - `GLOBAL-TREND (3자산 SPY·IEF·GLD — 라이브 지정 전략):RISK_OFF`
  - `GLOBAL-TREND-WIDE (11 슬리브 — 계획 ③ 후보):RISK_OFF`
- released-work local replay:
  - `candidate-regime-timeline-coverage-contract`
  - spec `100-regime-timeline-coverage-contract`
  - source `specs/100-regime-timeline-coverage-contract/spec.md`
  - status `released`
- autonomous-work local replay:
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-data-evidence-liveness-contract`
  - title `데이터 증거 생존성 계약`
  - risk grade 2
  - safety impact 0

## 안전 경계

- 위험 등급: 2(읽기 전용 레짐 타임라인 커버리지 계약과 work packet 전진 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #487 머지 전:

- `uv run pytest tests/unit/test_regime_timeline_coverage.py tests/integration/test_regime_timeline_coverage_probe.py tests/unit/test_autonomous_work_execution.py`
  -> 36 passed
- latest sidecar replay
  -> 스펙 100 probe `overall_status=OBSERVATION_WAIT`, timeline 2372행,
  label counts `RISK_ON=1414`, `CAUTION=894`, `RISK_OFF=64`, forward join PASS,
  stratified observation floor WAIT
- `uv run pytest`
  -> 2512 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- PR 품질 관문
  -> success
- 머지 직전 `uv run pytest`
  -> 2512 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- `uv run python scripts/released_work_probe.py --repo-root . --json`
  -> `candidate-regime-timeline-coverage-contract` released 확인
- `uv run python scripts/autonomous_work_execution_probe.py --evidence-dir <latest-sidecars> --repo-root . --json`
  -> `candidate-data-evidence-liveness-contract` selected work 확인
- latest sidecar replay with local released-work override
  -> `overall_status=OBSERVATION_WAIT`, timeline 2372행, label coverage PASS, forward join PASS,
  observation floor WAIT, completed candidate released true, next candidate `candidate-data-evidence-liveness-contract`
- `uv run pytest -q`
  -> 2512 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)

## 다음 세션 한 줄

스펙 100은 레짐 타임라인 커버리지를 읽기 전용 계약으로 닫았고, 희귀 `RISK_OFF` 관측 부족은
`OBSERVATION_WAIT`로 남기되 자율 작업 후보는 `candidate-data-evidence-liveness-contract`로 전진한다.
