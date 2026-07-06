# HANDOFF 101 — 비용 차감 no-live 엣지 실험 계약 (2026-07-06 KST)

main 코드 베이스라인: `49c4331`(PR #481). 이 작업은 스펙 096이 열어 둔
`candidate-cost-adjusted-edge-experiment`를 완료 처리하고, forward 성과를 execution-quality와 함께 읽어
비용 스트레스 후보와 실제 비용 근거 부족을 분리한 등급 2 운영 자동화 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/cost_adjusted_edge_experiment.py`
  - forward 리더보드, execution-quality, money-path, released-work, learning ledger, pipeline-liveness 증거를 읽어
    `CostAdjustedEdgeExperimentReport`를 만든다.
  - `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 분리한다.
  - 현재 최신 sidecar 기준 비용 스트레스 후보 21개, forward 관측 16/20, 남은 관측 4개,
    50bps 스트레스 기준 최상위 `multiasset`(비용 차감 수익률 1.342695%),
    execution-quality `latest_signal=INTENT_LOSS`, 브로커 거부 2건, KIS 코드 `APBK1672` 2건,
    `cost_basis_complete=false`, money-path `PREVIEW_ONLY`를 보고한다.
  - broker, 주문, 자본, live 전략, whitelist/caps, 비밀값, 외부 유료 서비스는 건드리지 않는다.
- `scripts/cost_adjusted_edge_experiment_probe.py`
  - 필요한 sidecar manifest를 출력한다.
  - sidecar 스냅샷 디렉터리나 현재 checkout의 spec 완료 마커를 입력으로 JSON/Markdown 보고서를 생성한다.
- `tests/unit/test_cost_adjusted_edge_experiment.py`
  - 정상 sidecar 입력, 관측 대기, 비용 기준 대기, 입력 누락 차단, pipeline critical 차단을 고정한다.
- `tests/integration/test_cost_adjusted_edge_experiment_probe.py`
  - CLI manifest, JSON 출력, Markdown 출력 계약을 확인한다.
- `specs/097-cost-adjusted-edge-experiment/`
  - SDD 산출물과 `completed_candidate_id: candidate-cost-adjusted-edge-experiment` 완료 마커를 남겼다.

## 운영상 의미

- 최신 released-work sidecar는 스펙 097 완료 후보를 released로 기록한다.
- 최신 autonomous-work sidecar는 다음 실행 후보를
  `candidate-data-evidence-frontier-map`으로 선택한다.
- 새 후보는 "데이터 증거 frontier 지도와 입력 품질 후보 재생성" 작업이다. 운영자 추가 질문 없이 새 브랜치나
  worktree에서 SDD 두께를 판단하고 구현, 검증, PR, 자동 머지 절차로 진행할 수 있다.
- 스펙 097 probe의 현재 판정은 `OBSERVATION_WAIT`다. 이것은 후보 작업이 미완료라는 뜻이 아니라,
  실제 forward 비교 가능성은 관측 20개 기준까지 4개가 더 필요하고 실제 체결 비용·회전율 기준도 아직
  부족하다는 뜻이다.
- 후보 required inputs:
  - `automation/rebalance-paper-forward-last-run:LAST_RUN.md`
  - `automation/execution-quality-last-run:LAST_RUN.md`
  - `automation/money-path-last-run:LAST_RUN.md`
  - `automation/released-work-last-run:released_work.json`
  - `automation/autonomous-evolution-last-run:learning_ledger.json`
  - `automation/pipeline-liveness-last-run:LAST_RUN.md`
- 돈 경로는 계속 `PREVIEW_ONLY`이고 money-path stage는 `BLOCKED`다. 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #481 merge commit: `49c4331aefc3cbe0f1fff3c412c1f926bbd27cfe`
- PR #481 feature commit: `e50e0c715512921b0f739e544965ba2918a44bf5`
- PR #481 post-merge runs:
  - `Deploy on merge to main` run `28784829389`: success
  - `Released work ledger` run `28784829439`: success
  - `Autonomous work execution loop` run `28784829374`: success
- 최신 released-work sidecar:
  - commit `49c4331aefc3cbe0f1fff3c412c1f926bbd27cfe`
  - `candidate-cost-adjusted-edge-experiment` status `released`
  - source file `specs/097-cost-adjusted-edge-experiment/data-model.md`
  - source field `completed_candidate_id`
  - released count 18
- 최신 autonomous-work sidecar:
  - commit `49c4331aefc3cbe0f1fff3c412c1f926bbd27cfe`
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-data-evidence-frontier-map`
  - risk grade 2, safety impact 없음
  - next action: 공개 데이터, regime, pipeline-liveness, public-data sidecar의 빈 영역을 지도화해 다음 데이터 품질 후보 생성
- 스펙 097 probe 최신 sidecar 재현:
  - `overall_status=OBSERVATION_WAIT`
  - forward max_n_obs 16, target_min_obs 20, remaining 4
  - cost stress candidates 21
  - best 50bps track `multiasset`, adjusted return 1.342695%
  - execution latest_signal `INTENT_LOSS`, cumulative_pnl_usd -1.14
  - rejected_orders 2, parsed_broker_errors 2, KIS code `APBK1672` 2건
  - `cost_basis_complete=false`, `cost-basis-completeness=WAIT`
  - money state: `PREVIEW_ONLY`, stage `BLOCKED`, `can_submit_real_orders=false`
- deploy status:
  - main commit의 `Deploy on merge to main` 체크와 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar는 #481 배포의 직접 증거가 아니다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 안전 경계

- 위험 등급: 2(no-live 실험 계약과 probe 추가)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #481 머지 전:

- `uv run pytest tests/unit/test_cost_adjusted_edge_experiment.py tests/integration/test_cost_adjusted_edge_experiment_probe.py`
  -> 7 passed
- latest sidecar replay와 `--repo-root .`
  -> `overall_status=OBSERVATION_WAIT`, forward 16/20, remaining 4, cost stress candidates 21,
  best 50bps `multiasset`, execution `INTENT_LOSS`, cost-basis completeness WAIT,
  money-path `PREVIEW_ONLY`, no-live safety PASS, released-work closure PASS
- released-work 로컬 재현
  -> `candidate-cost-adjusted-edge-experiment` released
- autonomous-work 로컬 재현
  -> `candidate-data-evidence-frontier-map` 선택
- `uv run pytest`
  -> 2489 passed, 4 skipped
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
  -> 2489 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- HANDOFF 갱신 전 `uv run pytest -q`
  -> 2 failed, 2487 passed, 4 skipped. 실패 2건은 낡은 HANDOFF main 커밋 행 때문에 strict harness가 의도적으로 막은 것이다.
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run ruff check src tests`
  -> All checks passed
- `uv run pytest -q`
  -> 2489 passed, 4 skipped

## 다음 세션 한 줄

스펙 097은 비용 차감 no-live 엣지 실험 계약 후보를 완료 처리했고, 현재 비용 차감 판정은
forward 관측 4개와 실제 체결 비용·회전율 근거가 더 필요한 `OBSERVATION_WAIT`다. 자율 작업 실행 루프의
다음 실행 후보는 `candidate-data-evidence-frontier-map`이다.
