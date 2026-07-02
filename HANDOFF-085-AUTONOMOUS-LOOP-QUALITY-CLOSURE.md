# HANDOFF 085 — 자율 루프 품질 폐쇄 (2026-07-02 KST)

main 코드 베이스라인: `649a8df`(PR #444). 스펙 081은 자율 성장 루프의 마지막 운영상 흠을 닫는 등급 2 보정이다. 다음 Codex 세션이 안전 후보를 다시 해석하지 않고 바로 작업 절차로 들어갈 수 있게 하고, sidecar 시점 차이를 장애와 분리하며, operator-status 뒤 pipeline-liveness 후속 감시 경로를 만든다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/autonomous_work_execution.py`
  - `WorkPacket`에 `autonomy_level`, `start_guidance_ko`, `completion_gates`를 추가했다.
  - 위험 등급 2 이하이고 안전 경계 영향이 없는 후보는 `CODEX_AUTONOMOUS_START`로 표시한다.
  - 주문, 자본, 비밀값, 헌법, live 전략, 외부 유료 서비스 표면을 건드리는 후보는 자동 착수로 표시하지 않는다.
- `src/auto_invest/analytics/money_gate_alignment.py`
  - sidecar 관측 수가 `14/20`과 `15/20`처럼 다르더라도 모두 관측 부족 대기라면 `ALIGNED_WAITING`을 유지한다.
  - 시점 차이는 `SNAPSHOT_SKEW` 정보성 이슈로 기록해 다음 aligned run에서 수렴 여부를 확인하게 한다.
- `.github/workflows/pipeline-liveness.yml`
  - `Operator mobile alerts` workflow 완료 뒤 `pipeline-liveness`가 다시 실행될 수 있는 `workflow_run` 트리거를 추가했다.
- `specs/081-autonomous-loop-quality-closure/`
  - 문제 정의, 안전 경계, 데이터 계약, quickstart, tasks를 남겼다.

## 운영상 의미

- 다음 세션은 `automation/autonomous-work-execution-last-run` 하나에서 선택 후보, 자율 착수 가능 여부, 착수 안내, 완료 관문을 읽는다.
- `CODEX_AUTONOMOUS_START`는 Codex가 기존 SDD·검증·PR·자동 머지 절차를 시작해도 된다는 뜻이다. 시스템이 스스로 코드를 작성하거나 PR을 만드는 새 실행자를 뜻하지 않는다.
- 돈 경로 관측 수 차이는 더 이상 장애처럼 보이지 않는다. 현재는 `PREVIEW_ONLY` 상태에서 전진 관측을 더 쌓는 정렬된 대기 상태다.
- `operator-status`가 새로 발행된 뒤 `pipeline-liveness`가 한 번 더 돌 수 있어, 다음 세션이 오래된 "미발행 예정" 상태를 읽을 가능성을 줄였다.

## 배포 후 실제 실행 증거

- PR #444 merge commit: `649a8dfb45fc8881b6e728f9dfab8ec6a27e8799`
- `Deploy on merge to main` run `28564456852`: success, commit `649a8df`
- `Autonomous work execution loop` run `28564456840`: success, commit `649a8df`
- `Money gate alignment loop` run `28564456849`: success, commit `649a8df`
- `Pipeline liveness watchdog` run `28564456858`: success, commit `649a8df`
- deploy 로그:
  - `systemctl start exit=0`
  - unit sync exit `0`
  - `auto-invest-deploy.service: Deactivated successfully`

최신 `origin/automation/autonomous-work-execution-last-run:LAST_RUN.md`:

- `overall_status=EXECUTION_READY`
- `selected_work=candidate-e481b0309206`
- `title_ko=레짐·성과 분석을 후보 점수화 입력으로 승격`
- `autonomy_level=CODEX_AUTONOMOUS_START`
- `risk_grade=2`
- `start_guidance_ko=운영자 추가 질문 없이 새 worktree 또는 브랜치에서 SDD 두께를 판단하고 구현, 검증, PR, 자동 머지 절차로 진행할 수 있다.`
- `completion_gates=관련 focused pytest, uv run pytest, uv run ruff check src tests, HANDOFF 사실 검증, strict 하네스, PR 품질 관문, 필요한 HANDOFF 갱신`

최신 `origin/automation/money-gate-alignment-last-run:LAST_RUN.md`:

- `overall_status=ALIGNED_WAITING`
- `live_money_status=PREVIEW_ONLY`
- `readiness_state=ACCUMULATING_EDGE`
- `capital_ladder_stage=ACCUMULATING_EDGE`
- `SNAPSHOT_SKEW` 관측값: `14-15/20 (money-path=14, edge-autoarm=15, rebalance-paper-forward=15)`
- `WAITING` 관측값: `14-15/20 (money-path=14, edge-autoarm=15, rebalance-paper-forward=15)`

최신 `origin/automation/pipeline-liveness-last-run:LAST_RUN.md`:

- `overall=OK`
- `operator-status=OK`
- `autonomous-work-execution=OK`
- `money-gate-alignment=OK`
- 핵심 sidecar 모두 신선

## 안전 경계

- 위험 등급: 2(운영 자동화 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 새 필드는 작업 패킷의 해석 가능성을 높이는 보고 계약이다. 코드 자동 수정, PR 자동 생성, live money actor는 추가하지 않았다.
- 배포 성공은 dry-run worker 코드 반영이다. 실거래 전환이나 실제 주문을 의미하지 않는다.

## 검증

PR #444 머지 전:

- `uv run pytest tests/unit/test_autonomous_work_execution.py tests/unit/test_money_gate_alignment.py tests/unit/test_pipeline_liveness.py tests/integration/test_autonomous_work_execution_probe.py tests/integration/test_money_gate_alignment_probe.py tests/integration/test_pipeline_liveness_probe.py -q` -> 53 passed
- `uv run pytest` -> 2417 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- `uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md` -> OK
- `uv run python scripts/check_pr_quality_gate.py /tmp/pr-081-body.md` -> OK
- `git diff --check` -> OK
- PR 품질 관문 run `28564427030`: success

머지 후:

- deploy run `28564456852`: success
- autonomous work execution run `28564456840`: success
- money gate alignment run `28564456849`: success
- pipeline liveness run `28564456858`: success
- 최신 sidecar에서 `CODEX_AUTONOMOUS_START`, `SNAPSHOT_SKEW`, `overall=OK` 확인

## 다음 세션 한 줄

스펙 081은 자율 루프가 고른 안전 후보를 다음 Codex 세션이 바로 시작할 수 있게 만들고, 관측 수 시점 차이와 pipeline-liveness 지연을 운영상 해석 가능한 상태로 닫았다. 현재 다음 후보는 `candidate-e481b0309206`, 돈 경로는 `PREVIEW_ONLY`, 파이프라인 생존 상태는 `OK`다.
