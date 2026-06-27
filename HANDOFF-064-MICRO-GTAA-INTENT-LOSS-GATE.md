# HANDOFF 064 — micro GTAA 손실 의도 실주문 차단 (2026-06-27 KST)

main 베이스라인: `6272178`(PR #394). 운영자가 "micro GTAA가 실행됐으면 오히려 돈을 잃었는데,
돈 잃을 게 뻔한 수행을 왜 해야 하냐"고 지적했다. 최신 거부 주문 기회손익은
`latest_signal=INTENT_LOSS`, 누적 의도 손익 `-1.14 USD`였다. 이 작업은 같은 전략 의도가
실주문으로 반복되지 않도록 돈 경로를 닫은 등급 4 변경이다.

## 무엇이 바뀌었나

- `automation/rebalance-micro-gtaa.request`: `armed:false`, `run_seq:3`으로 바꾸고, 최신 손실
  의도 신호 때문에 전략 검토 전까지 실주문을 중단한다는 note를 남겼다.
- `src/auto_invest/analytics/opportunity_monitor.py`: `assess_opportunity_live_gate`와 사람이 읽는
  렌더러를 추가했다. 최신 monitor의 `latest_signal=INTENT_LOSS` 또는 `verdict=STRATEGY_REVIEW`는
  live 주문 경로를 차단한다.
- `scripts/opportunity_live_gate.py`: GitHub Actions runner에서 최신
  `opportunity_monitor.json`을 읽어 intent-loss gate 결정을 JSON/text로 만든다.
- `.github/workflows/rebalance-micro-gtaa-canary.yml`: strategy-intent gate를 preflight 앞에 두고,
  preflight·손실 브레이커·live 주문 단계가 `steps.intent_gate.outputs.ok == 'true'`일 때만
  실행되도록 했다. 게이트 평가 자체가 실패하면 `gate_evaluation_unavailable`으로 fail-closed 한다.
- live가 실행되지 않은 run은 빈 opportunity 기록을 append하지 않는다. 그래서 이전 `INTENT_LOSS`
  신호가 `FLAT_OR_UNVALUED`로 덮이지 않는다.
- sidecar `LAST_RUN.md`와 Telegram 메시지에 strategy-intent gate 상태와 이유가 표시된다.
- `specs/065-micro-gtaa-intent-loss-gate/`: 목표, 비목표, 안전 경계, quickstart, tasks를 남겼다.

## 현재 운영 상태

- PR #394는 merge 방식으로 main에 머지됐다. main merge commit은 `6272178`, 구현 commit은
  `e98f7e9`다.
- #394 main push의 `Deploy on merge to main` run `28274580264`는 성공했다.
- 같은 main push의 `Money-path readiness` run `28274580263`도 성공했고,
  `live_money_state.status=PREVIEW_ONLY`, `can_submit_real_orders=false`를 보고했다.
- 같은 main push의 `Micro GTAA live canary rebalance` run `28274580272`도 성공했다.
  `Pre-live order preflight`, `Pre-live circuit breaker gate`, `LIVE rebalance — REAL MICRO ORDERS`는
  모두 skipped였다.
- 최신 micro GTAA sidecar는 `armed=false`, `LIVE 스텝=skipped`, `next_step=전략 의도 게이트
  차단(latest_intent_loss) — 전략 검토 전까지 실주문 0건`을 보여 준다.
- 최신 intent gate 결정은 `ok=false`, `reason=latest_intent_loss`, `latest_signal=INTENT_LOSS`,
  `cumulative_pnl_usd=-1.14`, `latest_run_id=28253047287`이다.
- KIS smoke sidecar의 최신 run은 아직 `28237830957` / commit `f76aa07` 기준이다. 즉 #394 직후
  새 KIS smoke sidecar는 확인하지 못했다. 다만 #394 배포 run 자체는 성공했다.

## 안전 경계

- 위험 등급: 4(돈 경로 변경)
- 방향: 실제 주문 가능성을 줄이는 변경이다.
- 실제 주문 실행: 없음. post-merge micro GTAA run에서도 live 주문 단계는 skipped였다.
- 자본, 허용 종목, 포지션 한도, 주문 라우터, 손실 브레이커, K1/K2/K4/K5/K6 코드, 헌법,
  커널 목록 변경: 없음
- 비밀값 출력: 없음
- strategy-intent gate는 주문을 허용하는 게이트가 아니다. 손실 의도 신호가 있을 때 live 전 단계로
  차단하는 추가 방어선이다.
- missing/unreadable monitor는 positive approval이 아니다. 다만 monitor 자체가 없는 경우 이 새
  게이트만으로 추가 차단하지 않고 기존 무장·정규장·현금·손실 브레이커 게이트가 계속 적용된다.

## 검증

PR #394 머지 전:

- focused tests 30 통과:
  `tests/unit/test_opportunity_monitor.py`,
  `tests/integration/test_opportunity_monitor_cli.py`,
  `tests/unit/test_micro_gtaa_canary.py`,
  `tests/unit/test_micro_gtaa_telegram_alerts.py`
- broader focused tests 105 통과:
  `tests/unit/test_money_path.py`,
  `tests/integration/test_money_path_probe.py`,
  `tests/unit/test_micro_gtaa_canary.py`,
  `tests/unit/test_opportunity_monitor.py`,
  `tests/integration/test_opportunity_monitor_cli.py`,
  `tests/unit/test_micro_gtaa_telegram_alerts.py`
- `uv run pytest` → 2283 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `git diff --check` → clean
- GitHub Actions YAML parse → OK
- workflow `run` block `bash -n` → OK
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- 최신 sidecar monitor 직접 판정:
  `python3 scripts/opportunity_live_gate.py --monitor-json <(git show origin/automation/rebalance-micro-gtaa-last-run:opportunity_monitor.json) --format text`
  → `ok=False`, `reason=latest_intent_loss`, `cumulative_pnl_usd=-1.14`

머지 직전:

- `uv run pytest` → 2283 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

머지 후:

- `Deploy on merge to main` run `28274580264` → success
- `Money-path readiness` run `28274580263` → success, `PREVIEW_ONLY`
- `Micro GTAA live canary rebalance` run `28274580272` → success, live order step skipped

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- `uv run pytest -q` → 2283 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

micro GTAA는 현재 `armed:false`이며 최신 손실 의도 신호 때문에 실주문 0건 상태다. 다시 무장하려면
단순 재시도가 아니라 strategy review / forward 증거를 보고 별도 등급 4 절차로 판단해야 한다.
