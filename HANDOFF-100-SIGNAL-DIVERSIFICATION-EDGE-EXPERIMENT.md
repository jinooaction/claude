# HANDOFF 100 — 신호 다변화 no-live 엣지 실험 계약 (2026-07-05 KST)

main 코드 베이스라인: `df8cc23`(PR #479). 이 작업은 스펙 095가 열어 둔
`candidate-signal-diversification-edge-experiment`를 완료 처리하고, forward track을 신호군으로 묶어
incumbent와 낮게 겹치는 no-live 실험 후보를 분리한 등급 2 운영 자동화 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/signal_diversification_edge_experiment.py`
  - forward 리더보드, money-path, released-work, learning ledger, pipeline-liveness 증거를 읽어
    `SignalDiversificationEdgeExperimentReport`를 만든다.
  - `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 분리한다.
  - 현재 최신 sidecar 기준 신호군 6개, forward 관측 16/20, 남은 관측 4개,
    incumbent `global_diversification`, 최저 겹침 후보 `broad_equity_timing`(겹침 0.0),
    money-path `PREVIEW_ONLY`를 보고한다.
  - broker, 주문, 자본, live 전략, whitelist/caps, 비밀값, 외부 유료 서비스는 건드리지 않는다.
- `scripts/signal_diversification_edge_experiment_probe.py`
  - 필요한 sidecar manifest를 출력한다.
  - sidecar 스냅샷 디렉터리나 현재 checkout의 spec 완료 마커를 입력으로 JSON/Markdown 보고서를 생성한다.
- `tests/unit/test_signal_diversification_edge_experiment.py`
  - 정상 sidecar 입력, 관측 대기, 입력 누락 차단, released-work closure 판정을 고정한다.
- `tests/integration/test_signal_diversification_edge_experiment_probe.py`
  - CLI manifest, JSON 출력, Markdown 출력 계약을 확인한다.
- `specs/096-signal-diversification-edge-experiment/`
  - SDD 산출물과 `completed_candidate_id: candidate-signal-diversification-edge-experiment` 완료 마커를 남겼다.

## 운영상 의미

- 최신 released-work sidecar는 스펙 096 완료 후보를 released로 기록한다.
- 최신 autonomous-work sidecar는 다음 실행 후보를
  `candidate-cost-adjusted-edge-experiment`로 선택한다.
- 새 후보는 "거래 비용 차감 no-live 엣지 실험 설계" 작업이다. 운영자 추가 질문 없이 새 브랜치나 worktree에서
  SDD 두께를 판단하고 구현, 검증, PR, 자동 머지 절차로 진행할 수 있다.
- 스펙 096 probe의 현재 판정은 `OBSERVATION_WAIT`다. 이것은 후보 작업이 미완료라는 뜻이 아니라,
  실제 forward 비교 가능성은 관측 20개 기준까지 4개가 더 필요하다는 뜻이다.
- 현재 낮은 겹침 제안 후보는 세 개다.
  - `broad_equity_timing`: incumbent와 겹침 0.0, `PROPOSED`
  - `risk_managed_beta`: incumbent와 겹침 0.25, `PROPOSED`
  - `wide_universe_allocation`: incumbent와 겹침 0.375, `PROPOSED`
- 후보 required inputs:
  - `automation/rebalance-paper-forward-last-run:LAST_RUN.md`
  - `automation/money-path-last-run:LAST_RUN.md`
  - `automation/released-work-last-run:released_work.json`
  - `automation/autonomous-evolution-last-run:learning_ledger.json`
  - `automation/pipeline-liveness-last-run:LAST_RUN.md`
- 돈 경로는 계속 `PREVIEW_ONLY`이고 money-path stage는 `BLOCKED`다. 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #479 merge commit: `df8cc23902373f67f4e87f582850cf8af58790ad`
- PR #479 feature commit: `999fbd2406392a3d043d285deb373b0d530853d1`
- PR #479 post-merge runs:
  - `Deploy on merge to main` run `28740023274`: success
  - `Released work ledger` run `28740023261`: success
  - `Autonomous work execution loop` run `28740023276`: success
- 최신 released-work sidecar:
  - commit `df8cc23902373f67f4e87f582850cf8af58790ad`
  - `candidate-signal-diversification-edge-experiment` status `released`
  - source file `specs/096-signal-diversification-edge-experiment/spec.md`
  - source field `completed_candidate_id`
  - released count 17
- 최신 autonomous-work sidecar:
  - commit `df8cc23902373f67f4e87f582850cf8af58790ad`
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-cost-adjusted-edge-experiment`
  - risk grade 2, safety impact 없음
  - 투자 엣지 frontier 지도: `forward_regime_edge=released`,
    `signal_diversification_edge=released`, `cost_adjusted_edge=open`
- 스펙 096 probe 최신 sidecar 재현:
  - `overall_status=OBSERVATION_WAIT`
  - forward max_n_obs 16, target_min_obs 20, remaining 4
  - family_count 6, track_count 7, forward_comparable_count 0
  - incumbent family `global_diversification`
  - largest family `broad_equity_timing`, share 0.285714
  - lowest overlap candidate `broad_equity_timing`, overlap 0.0
  - proposed candidates: `broad_equity_timing`, `risk_managed_beta`, `wide_universe_allocation`
  - money state: `PREVIEW_ONLY`, stage `BLOCKED`, `can_submit_real_orders=false`
- deploy status:
  - main commit의 `Deploy on merge to main` 체크는 success다.
  - 서버 audit_log와 GitHub Actions Summary 원문은 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar는 #479 배포의 직접 증거가 아니다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 안전 경계

- 위험 등급: 2(no-live 실험 계약과 probe 추가)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #479 머지 전:

- `uv run pytest tests/unit/test_signal_diversification_edge_experiment.py tests/integration/test_signal_diversification_edge_experiment_probe.py`
  -> 7 passed
- latest sidecar replay와 `--repo-root .`
  -> `overall_status=OBSERVATION_WAIT`, family_count 6, forward 16/20, remaining 4,
  money-path `PREVIEW_ONLY`, no-live safety PASS, released-work closure PASS
- released-work 로컬 재현
  -> `candidate-signal-diversification-edge-experiment` released
- autonomous-work 로컬 재현
  -> `candidate-cost-adjusted-edge-experiment` 선택
- `uv run pytest -q`
  -> 2482 passed, 4 skipped
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
- 머지 직전 `uv run pytest -q`
  -> 2482 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run ruff check src tests`
  -> All checks passed
- `uv run pytest -q`
  -> 2482 passed, 4 skipped

## 다음 세션 한 줄

스펙 096은 신호 다변화 no-live 엣지 실험 계약 후보를 완료 처리했고, 실제 forward 비교 가능성은 관측
20개 기준까지 4개가 더 필요하다. 자율 작업 실행 루프의 다음 실행 후보는
`candidate-cost-adjusted-edge-experiment`다.
