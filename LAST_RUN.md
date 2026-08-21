# 마이크로 GTAA 라이브 캐너리 — 최신 실행

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| timestamp_utc | 2026-08-21T15:36:02Z |
| armed | false |
| capital_usd | [REDACTED]|
| blocked | false |
| event | schedule |
| LIVE 스텝 | skipped (success=실주문 실행 / skipped=미실행) |
| warning_drawdown_pct | 3 |
| hard_stop_drawdown_pct | 5 |

> 드라이런 미리보기만(armed=false) — 실주문 0건.

## 계좌 전체 재배치 상태
| 항목 | 값 |
|------|-----|
| account_wide_enabled | ? |
| execution_side_requested | ? |
| execution_side_effective | unknown |
| purchasable_cash_usd | ? |
| required_cash_usd | ? |
| planned_buy_notional_usd | ? |
| planned_sell_notional_usd | ? |
| next_step | 전략 의도 게이트 차단(latest_intent_loss) — 전략 검토 전까지 실주문 0건 |

## 라이브 전 전략 의도 게이트
```json
{
  "schema_version": 1,
  "as_of_utc": "2026-08-21T15:35:55Z",
  "ok": false,
  "reason": "latest_intent_loss",
  "blocking_reasons": [
    "latest_intent_loss"
  ],
  "verdict": "INSUFFICIENT_DATA",
  "latest_signal": "INTENT_LOSS",
  "cumulative_pnl_usd": "-1.14",
  "latest_run_id": "[REDACTED_ACCOUNT]",
  "policy_ko": "최신 거부 주문 기회손익이 손실 방향(INTENT_LOSS)이거나 누적 판정이 STRATEGY_REVIEW이면 micro GTAA 실주문을 차단합니다.",
  "next_action_ko": "실주문을 멈추고 forward 토너먼트·전략 검토 증거를 확인합니다.",
  "safety_note_ko": "이 게이트는 실주문을 차단만 합니다. 주문 재시도, 전략 교체, 자본 변경을 직접 수행하지 않습니다."
}
```

## 드라이런 미리보기
```json
```

## 라이브 전 손실 브레이커
```json
(미실행)
```

## 라이브 전 주문 전제 확인
```json
(미실행)
```

## 라이브 재조정 결과
```json
(미실행)
```

## 거부 주문 기회손익
기준: 양수=거부 주문이 체결됐으면 현재 더 유리, 음수=거부가 결과적으로 유리. 수수료·세금·환율·실제 체결 가능성 제외.

| 항목 | 값 |
|------|-----|
| as_of_utc | ? |
| rejected_count | 0 |
| valued_count | 0 |
| total_opportunity_pnl_usd | +0.00 |
| buy_opportunity_pnl_usd | +0.00 |
| sell_opportunity_pnl_usd | +0.00 |
| mark_fetch_error | not evaluated |

```json
{"schema_version":1,"as_of_utc":"","definition":"unavailable","rejected_count":0,"valued_count":0,"missing_mark_symbols":[],"mark_fetch_error":"not evaluated","total_opportunity_pnl_usd":"+0.00","buy_opportunity_pnl_usd":"+0.00","sell_opportunity_pnl_usd":"+0.00","rows":[]}
```

## 거부 주문 누적 평가
기준: 음수=전략 의도가 손실이었을 가능성, 양수=거부 때문에 이익을 놓쳤을 가능성.
단일 신호로 주문 재시도·전략 교체·자본 변경을 하지 않는다.

| 항목 | 값 |
|------|-----|
| verdict | INSUFFICIENT_DATA (표본 부족) |
| latest_signal | INTENT_LOSS |
| cumulative_pnl_usd | -1.14 |
| valued_runs | 1/1 |
| valued_orders | 2/2 |
| streak_loss_gain | 1 / 0 |
| latest_run | [REDACTED_ACCOUNT] |
| next_action | 최신 손실 의도 신호가 실주문을 막고 있어 새 live 표본은 자동으로 쌓이지 않습니다. forward 토너먼트·재지정 증거를 기다리거나 별도 전략 검토 후 재무장 여부를 판단합니다. |

```json
{
  "schema_version": 1,
  "as_of_utc": "2026-08-21T15:36:02Z",
  "definition": "positive intended_order_mark_pnl_usd means rejected orders would currently look favorable; negative means rejection avoided a worse mark-to-current outcome. This is diagnostic, not accounting PnL.",
  "verdict": "INSUFFICIENT_DATA",
  "verdict_label_ko": "표본 부족",
  "latest_signal": "INTENT_LOSS",
  "interpretation_ko": "최신 신호는 보이지만 자동 전략 판단을 내리기에는 표본이 부족합니다.",
  "next_action_ko": "최신 손실 의도 신호가 실주문을 막고 있어 새 live 표본은 자동으로 쌓이지 않습니다. forward 토너먼트·재지정 증거를 기다리거나 별도 전략 검토 후 재무장 여부를 판단합니다.",
  "safety_note_ko": "이 신호는 관찰·검토 입력입니다. 주문 재시도, 전략 교체, 자본 변경을 직접 수행하지 않습니다.",
  "thresholds": {
    "min_valued_reports": 2,
    "strategy_review_loss_usd": "-5.00",
    "execution_review_gain_usd": "+5.00",
    "streak_threshold": 2
  },
  "counts": {
    "records": 1,
    "valued_records": 1,
    "rejected_orders": 2,
    "valued_orders": 2
  },
  "cumulative": {
    "total_intended_order_mark_pnl_usd": "-1.14",
    "buy_intended_order_mark_pnl_usd": "-1.14",
    "sell_intended_order_mark_pnl_usd": "+0.00"
  },
  "streaks": {
    "intent_loss": 1,
    "intent_gain": 0
  },
  "latest": {
    "run_id": "[REDACTED_ACCOUNT]",
    "run_url": "https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT]",
    "recorded_at_utc": "2026-06-26T17:03:12Z",
    "opportunity_as_of_utc": "2026-06-26T17:03:11Z",
    "rejected_count": 2,
    "valued_count": 2,
    "total_intended_order_mark_pnl_usd": "-1.14",
    "latest_signal": "INTENT_LOSS"
  },
  "strategy_loop_input": {
    "target": "specs/055-autonomous-reassignment",
    "effect": "evidence_only_no_gate_override"
  }
}
```

## 측정 로그
```
refused command: cd /opt/auto-invest &&        /usr/local/bin/uv run auto-invest nav-snapshot --mode live --capital 1000 --db data/auto_invest.db --env-file .env --snapshot --format json;        /usr/local/bin/uv run auto-invest forward-verdict --mode live --portfolio deploy/micro-gtaa-live-portfolio.toml --db data/auto_invest.db --format json
```
