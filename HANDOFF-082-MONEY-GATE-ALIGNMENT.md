# HANDOFF 082 — 돈 경로 게이트 정렬 루프 (2026-07-01 KST)

main 코드 베이스라인: `09b528a`(PR #434). 스펙 078은 money-path, 자본 준비도, edge-autoarm, reassign, forward, pipeline, 자율 작업 실행, KIS smoke sidecar를 한 번에 대조해 돈 경로 불일치와 다음 안전 행동을 `automation/money-gate-alignment-last-run`에 발행하는 읽기 전용 운영 루프다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/money_gate_alignment.py`
  - 입력 sidecar 8개를 `GateSurface`로 정규화한다.
  - money-path와 capital-path-readiness의 live 상태, 자본 사다리, blocker를 최우선 근거로 삼는다.
  - edge-autoarm, reassign, forward 관측이 같은 대기 상태인지 확인해 `ALIGNED_WAITING`을 산출한다.
  - sidecar 누락·파싱 실패·서로 다른 live 상태는 `UNKNOWN`, `BLOCKED`, `MISALIGNED`로 fail-closed 처리한다.
- `scripts/money_gate_alignment_probe.py`
  - `--manifest`로 소비 sidecar 목록을 제공한다.
  - workflow와 로컬 smoke가 같은 코어를 호출해 JSON/Markdown 보고서를 만든다.
- `.github/workflows/money-gate-alignment.yml`
  - 매일 09:20 UTC와 main push 때 실행된다.
  - automation sidecar 브랜치를 읽고 `automation/money-gate-alignment-last-run`만 발행한다.
- `src/auto_invest/analytics/pipeline_liveness.py`
  - `money-gate-alignment`를 비핵심 보고 sidecar로 감시 대상에 등록했다.
- `specs/078-money-gate-alignment-loop/`
  - 스펙, 계획, 작업 목록, 데이터 모델, 계약, quickstart를 남겼다.

## 운영상 의미

- 다음 세션은 돈 경로 상태를 여러 sidecar에서 손으로 맞추기 전에 `money-gate-alignment`를 먼저 본다.
- 현재 최신 판정은 장애가 아니라 정렬된 대기 상태다.
  - 종합 상태: `ALIGNED_WAITING`
  - 실제 돈 상태: `PREVIEW_ONLY`
  - 자본 준비도: `ACCUMULATING_EDGE`
  - 자본 사다리: `ACCUMULATING_EDGE`
  - blocker: `전진 관측 부족: 14/20 (통계적 유의까지 더 쌓여야 함).`
  - 선택 후보: `candidate-fd04772a23c5`
- 현재 정렬 이슈는 `WAITING forward_observation`이다. 기대값은 `EDGE_CONFIRMED`, 관측값은 `14/20`이다.
- 다음 행동은 전진 관측을 계속 누적하고, 최소 관측 이후 기존 자본 사다리로만 승격하는 것이다.

## 배포 후 실제 실행 증거

- PR #434 merge commit: `09b528a900f884c42135a39a03436c685375ab5f`
- `Deploy on merge to main` run `28526440236`: success, commit `09b528a`
- `Money gate alignment loop` run `28526440247`: success, commit `09b528a`
- 최신 `origin/automation/money-gate-alignment-last-run:LAST_RUN.md`
  - run `28526440247`, trigger `push`, timestamp `2026-07-01T14:51:36Z`
  - `overall_status=ALIGNED_WAITING`
  - `live_money_status=PREVIEW_ONLY`
  - `readiness_state=ACCUMULATING_EDGE`
  - `capital_ladder_stage=ACCUMULATING_EDGE`
  - `blocking_gate=전진 관측 부족: 14/20 (통계적 유의까지 더 쌓여야 함).`
  - `selected_work_candidate=candidate-fd04772a23c5`
  - 입력 증거 8개 모두 `present=true`, `parse_status=ok`
- `Pipeline liveness`는 main push 직후 병렬 실행에서 새 sidecar보다 먼저 돌 수 있었다. 같은 main commit으로 workflow dispatch run `28526482569`을 재실행했고 최신 liveness sidecar는 `overall=OK`, `money-gate-alignment=OK`다.
- 최신 `KIS smoke` sidecar run `28523981341`은 commit `996ce56` 기준 success다. #434 뒤 실행은 아니므로 스펙 078 배포 증거가 아니라 최근 읽기 전용 브로커 생존 확인으로만 본다.

## 안전 경계

- 위험 등급: 2(운영 자동화 추가)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그, 외부 유료 서비스 변경: 없음
- workflow 안전 계약 테스트가 `KIS_`, `ssh `, live rebalance, 주문 제출, PR 생성, main 직접 push 문자열 부재를 확인한다.
- 배포 성공은 dry-run worker 코드 반영이다. 실거래 전환이나 실제 주문을 의미하지 않는다.

## 검증

PR #434 머지 전:

- `uv run pytest tests/unit/test_money_gate_alignment.py tests/integration/test_money_gate_alignment_probe.py`
  -> 10 passed
- `uv run ruff check src/auto_invest/analytics/money_gate_alignment.py scripts/money_gate_alignment_probe.py tests/unit/test_money_gate_alignment.py tests/integration/test_money_gate_alignment_probe.py`
  -> All checks passed
- `uv run pytest tests/integration/test_pipeline_liveness_probe.py tests/integration/test_capital_path_readiness_probe.py tests/integration/test_autonomous_work_execution_probe.py`
  -> 12 passed
- 관련 ruff -> All checks passed
- 최신 sidecar local smoke -> `ALIGNED_WAITING`, `PREVIEW_ONLY`, `ACCUMULATING_EDGE`, `WAITING forward_observation`, 입력 sidecar 8개 `ok`
- `uv run pytest` -> 2394 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `git diff --check` -> OK
- `uv run python scripts/check_pr_quality_gate.py /tmp/pr_body_078.md` -> OK
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR 품질 관문 -> success, mergeable clean, merge 방식으로 main에 병합
- 머지 직전 전체 테스트와 린트를 다시 실행해 같은 결과를 확인했다.

머지 후:

- deploy run `28526440236`: success
- money gate alignment run `28526440247`: success
- latest money gate sidecar verification -> `ALIGNED_WAITING`, `PREVIEW_ONLY`, `ACCUMULATING_EDGE`, `WAITING forward_observation`, 입력 sidecar 8개 `ok`
- pipeline liveness 재실행 run `28526482569`: success, latest sidecar `overall=OK`, `money-gate-alignment=OK`

## 다음 세션 한 줄

스펙 078은 돈 경로 관련 sidecar들이 같은 결론을 말하는지 자동으로 대조한다. 현재 결론은 실거래 준비가 아니라 `PREVIEW_ONLY` 상태에서 전진 관측 `14/20`을 더 쌓는 정렬된 대기 상태다.
