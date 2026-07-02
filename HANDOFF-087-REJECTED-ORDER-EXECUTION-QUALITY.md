# HANDOFF 087 — 주문 거부·체결 품질 손익 관측 (2026-07-02 KST)

main 코드 베이스라인: `f874b64`(PR #449). 스펙 083 기능 베이스라인은 `b4fa316`(PR #448)이다. 이 작업은 자율 작업 실행 루프가 고른 `candidate-dff4f9344b02`를 처리한 등급 2 운영 보정이다. 이미 발행된 sidecar만 읽어 주문 거부, 브로커 오류 코드, KIS smoke, live gate 상태를 하나의 실행 품질 증거 패키지로 묶었고, #449에서 생존 감시가 보고서 자체 발행 시각을 freshness로 읽게 보정했다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/execution_quality.py`
  - `opportunity_monitor.json`, `opportunity_history.json`, micro GTAA `LAST_RUN.md`, KIS smoke `LAST_RUN.md`를 읽어 `ExecutionQualityReport`를 만든다.
  - 브로커 거부 주문 수, 파싱된 KIS 오류 코드, KIS smoke 실패율, live gate 상태, 안전 불변식을 JSON과 Markdown으로 남긴다.
- `scripts/execution_quality_probe.py`
  - workflow manifest, JSON 출력, Markdown 요약 출력을 지원한다.
- `.github/workflows/execution-quality.yml`
  - `automation/execution-quality-last-run`에 `LAST_RUN.md`와 `execution_quality.json`을 발행한다.
  - 주문, 자본, whitelist, caps, live 전략, 비밀값, 외부 유료 서비스는 변경하지 않는다.
- `src/auto_invest/analytics/evolution_loop.py`
  - `candidate-dff4f9344b02` evidence refs에 `execution-quality`, `rebalance-micro-gtaa`, `kis-smoke`를 연결했다.
  - 실행 품질 sidecar가 없거나 오래되면 후보를 과신하지 않고 `sidecar_freshness` 의존으로 낮춘다.
- `src/auto_invest/analytics/pipeline_liveness.py`
  - `execution-quality` sidecar를 비핵심 감시 대상으로 등록했다.
  - 후속 보정에서 `LAST_RUN.md` 안쪽 JSON의 입력 증거 시각보다 workflow metadata의 발행 시각을 freshness로 우선 읽게 했다.
- `specs/083-rejected-order-execution-quality/`
  - SDD 산출물, quickstart, 계약, tasks를 남겼다.
  - 계약서에 `completed_candidate_id: candidate-dff4f9344b02`를 기록해 `released-work`가 반복 선택을 막게 했다.

## 운영상 의미

- 자율 성장 루프는 주문 거부를 단순 로그가 아니라 반복 관측 가능한 실행 품질 증거로 본다.
- 현재 발행된 실행 품질 sidecar의 종합 판정은 `OBSERVE`다. live gate는 `latest_intent_loss` 때문에 실주문을 막고 있으며, 새 live 표본은 자동으로 쌓이지 않는다.
- 브로커 거부 관측은 `APBK1672` 2건으로 파싱됐고, KIS smoke는 최근 성공 상태다.
- `released-work`는 `candidate-dff4f9344b02`를 `released`로 소비했다. 자율 작업 실행 루프는 같은 후보를 다시 고르지 않고 다음 후보 `candidate-6ee3370e933d`(`오래된 증거와 성과 실패 분리`)를 선택했다.
- #448 직후 같은 push에서 자율 성장 루프가 실행 품질 sidecar보다 약간 먼저 돌아 `execution-quality`를 stale로 본 기록이 있었다. #449 뒤 최신 자율 성장 sidecar는 `오래되었거나 누락된 증거: 없음`으로 회복됐다.

## 배포 후 실제 실행 증거

- PR #448 merge commit: `b4fa3164bab2eebcc4cd42f7ff502ae5027aa820`
- PR #449 merge commit: `f874b642de0f19b779278ee3a6b986ff4213b024`
- `Deploy on merge to main` run `28573162272`: success, commit `b4fa316`
- `Execution quality package` run `28573162279`: success, commit `b4fa316`
- `Pipeline liveness watchdog` run `28573162215`: success, commit `b4fa316`
- `Pipeline liveness watchdog` workflow_run `28573180853`: success, commit `b4fa316`
- `Released work ledger` run `28573162227`: success, commit `b4fa316`
- `Autonomous work execution loop` run `28573162293`: success, commit `b4fa316`
- `Candidate result executor` run `28573162239`: success, commit `b4fa316`
- #449 후속 runs: deploy `28574000074`, execution-quality `28574000181`, pipeline-liveness push `28574000145`, pipeline-liveness workflow_run `28574020426`, autonomous evolution `28574000146`, autonomous work `28574000140`, candidate result executor `28574000112` 모두 success, commit `f874b64`
- deploy success는 dry-run worker 코드 반영이다. 서버 `audit_log`는 이 컨테이너에서 직접 확인하지 못했다.

최신 `origin/automation/execution-quality-last-run:LAST_RUN.md`:

- `run_id=28574000181`
- `commit=f874b642de0f19b779278ee3a6b986ff4213b024`
- `overall_status=OBSERVE`
- `monitor_verdict=INSUFFICIENT_DATA`
- `latest_signal=INTENT_LOSS`
- `cumulative_pnl_usd=-1.14`
- `rejected_orders=2`, `parsed_broker_errors=2`, `kis_msg_codes={"APBK1672": 2}`
- KIS smoke: `state=success`, `exit=0`, `tests_total=4`, `tests_failed=0`, `smoke_error_rate=0.0000`
- 안전 문구: 주문 없음, 자본 변경 없음, whitelist/caps 변경 없음, live 전략 변경 없음

최신 `origin/automation/pipeline-liveness-last-run:LAST_RUN.md`:

- `run_id=28574020426`
- `commit=f874b642de0f19b779278ee3a6b986ff4213b024`
- `overall=OK`
- `execution-quality`: `status=OK`, `timestamp_utc=2026-07-02T07:45:40Z`, `age_hours=0.0`
- 모든 핵심 sidecar 신선

최신 `origin/automation/released-work-last-run:released_work.json`:

- `run_id=28573162227`
- `candidate-dff4f9344b02` -> `released`
- source: `specs/083-rejected-order-execution-quality/contracts/execution-quality.md`
- reason: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록됨

최신 `origin/automation/autonomous-work-execution-last-run:autonomous_work_execution.json`:

- `selected_work=candidate-6ee3370e933d`
- title: 오래된 증거와 성과 실패 분리
- `candidate-dff4f9344b02`는 `CLOSED_RELEASED`, `status=RELEASED`
- start guidance: 이미 구현·머지·인계된 후보이므로 다시 착수하지 않는다

최신 `origin/automation/candidate-implementation-results:LAST_RUN.md`:

- `run_id=28574000112`
- `overall_status=degraded`
- execution_quality `candidate-dff4f9344b02`는 no-live 검증 pass
- 기존 strategy_backtest와 portfolio_backtest 패키지 2건은 blocked로 남아 있다. 이번 스펙 083의 새 실패가 아니라 별도 관찰 지점이다.

## 안전 경계

- 위험 등급: 2(운영 자동화 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- `execution-quality`는 이미 발행된 evidence branch만 읽는 보고 패키지다.
- KIS smoke는 최신 sidecar 기준 성공이지만 #448 이후 새 KIS smoke workflow 실행은 아니다. 브로커 생존 참고이지 배포 검증 표면은 아니다.

## 검증

PR #448 머지 전:

- `uv run pytest tests/unit/test_execution_quality.py tests/integration/test_execution_quality_probe.py` -> 7 passed
- `uv run pytest tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py` -> 33 passed
- `uv run pytest tests/unit/test_pipeline_liveness.py tests/integration/test_pipeline_liveness_probe.py` -> 30 passed
- focused quickstart 묶음 -> 70 passed
- `uv run ruff check src tests` -> All checks passed
- `uv run pytest` -> 2431 passed, 4 skipped
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR 품질 관문 통과

후속 liveness timestamp 보정:

- `uv run pytest tests/unit/test_pipeline_liveness.py tests/integration/test_pipeline_liveness_probe.py` -> 32 passed
- 로컬 sidecar probe에서 `execution-quality.timestamp_utc=2026-07-02T07:29:37Z`, `age_hours=0.01`, `status=OK` 확인
- `uv run ruff check src tests` -> All checks passed
- `uv run pytest` -> 2433 passed, 4 skipped
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR #449 품질 관문 -> success
- #449 post-merge deploy, execution-quality, pipeline-liveness, autonomous evolution, autonomous work, candidate result executor runs -> success

## 다음 세션 한 줄

스펙 083은 완료됐다. 실행 품질 sidecar는 주문 거부 2건과 KIS smoke 성공을 읽기 전용으로 묶어 발행했고, pipeline-liveness도 그 sidecar를 보고서 자체 시각으로 신선하게 본다. `candidate-dff4f9344b02`는 `released-work`에 소비되어 다음 실제 착수 후보는 `candidate-6ee3370e933d`다.
