# HANDOFF 066 — micro GTAA intent-loss 다음 행동 안내 보정 (2026-06-28 KST)

main 베이스라인: `0b7c248`(PR #398). 운영자가 "돈 벌려면 무슨 작업을 해야 하는지"를 물은 뒤,
최신 micro GTAA 차단 표면을 다시 확인했다. 결론은 실주문 재개가 아니라 `latest_intent_loss`
차단의 의미를 정확히 읽는 것이었다. 이 작업은 돈 경로를 열지 않고, 차단 상태의 다음 행동 안내가
실제 동작과 일치하도록 보정한 등급 2 변경이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/opportunity_monitor.py`: `summarize_opportunity_history()`가
  `latest_signal`을 `_next_action()`에 넘긴다.
- `VERDICT_INSUFFICIENT_DATA`이면서 `latest_signal=INTENT_LOSS`이면, 이제 다음 행동은
  "다음 micro GTAA 실행에서 표본을 더 쌓습니다"가 아니다. 새 안내는 live gate가 실주문을 막고
  있어 새 live 표본은 자동으로 쌓이지 않으며, forward 토너먼트·재지정 증거를 기다리거나 별도
  전략 검토 후 재무장 여부를 판단하라는 내용이다.
- `tests/unit/test_opportunity_monitor.py`와 `tests/integration/test_opportunity_monitor_cli.py`가
  이 안내를 고정한다.
- `specs/065-micro-gtaa-intent-loss-gate/spec.md`에 `INTENT_LOSS` 차단 중 live 표본 자동 누적을
  안내하지 말라는 요구를 추가했다.

## 현재 운영 상태

- micro GTAA는 여전히 `armed:false`, `capital_usd:1000`이다.
- 최신 micro sidecar run `28274580272`는 `LIVE 스텝=skipped`, strategy-intent gate `ok=false`,
  `reason=latest_intent_loss`다.
- 최신 `opportunity_monitor.json`은 `verdict=INSUFFICIENT_DATA`, `latest_signal=INTENT_LOSS`,
  누적 의도 손익 `-1.14 USD`, 평가 실행 `1/1`, 평가 주문 `2/2`다.
- `auto-invest opportunity-monitor --history-json <latest history> --format json`을 최신 코드로
  재현하면 `next_action_ko`가 "새 live 표본은 자동으로 쌓이지 않습니다"로 나온다.
- 최신 money-path 재현은 `live_money_state.status=PREVIEW_ONLY`, `can_submit_real_orders=false`,
  stage `ACCUMULATING_EDGE`, forward 관측 `12/20`, 추정 첫 자본 2026-07-08 부근이다.
- 최신 코드로 `rebalance-paper-forward-last-run:LAST_RUN.md`를 다시 파싱하면 관측 품질은 `OK`다.
  그러나 비교 가능한 도전자는 0개라 `reassign-decide`는 `HOLD`가 정상이다.

## 안전 경계

- 위험 등급: 2(운영 안내 보정)
- 실제 주문 실행: 없음
- micro GTAA 재무장: 없음
- 자본 증액, 허용 종목 확대, live 전략 교체: 없음
- 주문 라우터, 포지션 한도, whitelist, 손실 브레이커, 감사 로그, 비밀값, K1/K2/K4/K5/K6 코드,
  헌법, 커널 목록 변경: 없음
- 이 변경은 live gate를 완화하지 않는다. `INTENT_LOSS` 차단은 그대로 유지된다.

## 검증

PR #398 머지 전:

- focused tests 14 통과:
  `tests/unit/test_opportunity_monitor.py`,
  `tests/integration/test_opportunity_monitor_cli.py`
- `uv run auto-invest opportunity-monitor --history-json /tmp/micro_opportunity_history_current.json --format json`
  → 새 `next_action_ko` 재현
- `uv run python scripts/forward_tournament_probe.py --from-sidecar /tmp/rebalance_paper_forward_LAST_RUN.md --json`
  → `observation_health=OK`, `comparable_count=0`
- `uv run auto-invest reassign-decide --leaderboard-json /tmp/rebalance_leaderboard_recomputed.json --execution-feedback-json /tmp/opportunity_monitor_current.json --format json`
  → `action=HOLD`, `observation_health=OK`, `challenger_key=null`
- `uv run python scripts/money_path_probe.py --sidecar-dir <tmp> --json`
  → `PREVIEW_ONLY`, `ACCUMULATING_EDGE`, `forward_n_obs=12`
- `uv run pytest` → 2286 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `git diff --check` → clean
- PR body quality gate → `pr-quality-gate-ok`
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)

머지 후 handoff 갱신 전:

- `uv run pytest -q`는 `HANDOFF.md`가 아직 #398 main commit을 모른다는 이유로
  하네스 관련 2건이 실패했다. 이는 코드 실패가 아니라 이 handoff 갱신이 해결해야 하는 stale
  handoff 상태다.

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- `uv run pytest -q` → 2286 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

micro GTAA는 여전히 `latest_intent_loss`로 실주문 차단 중이다. 차단 중에는 새 live 표본이 자동으로
쌓이지 않으므로, 다음 판단은 forward 관측 누적(현재 12/20)과 재지정 증거를 기다리거나 별도 전략
검토 후 재무장 여부를 결정하는 것이다.
