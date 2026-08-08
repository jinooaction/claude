# 자율 전략 재지정 — 최신 실행 (스펙 055 / 헌법 X.5)

forward 토너먼트 챔피언이 5중 게이트를 전부 통과하면 라이브 전략을 자동 교체한다.
결정/실행은 테스트된 src 모듈(decide_reassignment + build_reassignment)이 한다.
fail-closed: 도전자 없음·다중검정 미통과·캐너리 PASS 아님 → 재지정 0.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| timestamp_utc | 2026-08-08T02:24:12Z |
| trigger | schedule |
| **결정(action)** | **HOLD** |
| incumbent → challenger | global → ? |
| 챔피언 설정 | (도전자 없음) |
| ④ 캐너리 verdict | (미실행 — 도전자 없음/데이터 없음) |
| 라이브 거부 주문 누적 verdict | INSUFFICIENT_DATA |
| 라이브 설정 변경 | false |
| PR | (없음 — 변경 없음) |
| 머지 | n/a |

## 의미

🏠 **유지** — 도전자 없음 또는 다중검정 보정 미통과(운 좋은 우승 가능). 현 전략이 최선/미확정.

- 사유: 도전자 없음(엣지 확정 + 사과 대 사과로 incumbent 를 앞선 트랙 부재) — 현 전략 유지.

## 5중 게이트 결정 JSON
```json
{"schema_version": "1.2", "action": "HOLD", "incumbent_key": "global", "challenger_key": null, "canary_verdict": null, "observation_health": "OK", "observation_note": "모든 후보가 최소 관측을 충족. 관측 수 차이는 참고 정보로만 표시: trend, globalfixed, notrend.", "execution_feedback": {"source": "rejected_order_opportunity_monitor", "effect": "evidence_only_no_gate_override", "verdict": "INSUFFICIENT_DATA", "verdict_label_ko": "표본 부족", "latest_signal": "INTENT_LOSS", "interpretation_ko": "최신 신호는 보이지만 자동 전략 판단을 내리기에는 표본이 부족합니다.", "next_action_ko": "최신 손실 의도 신호가 실주문을 막고 있어 새 live 표본은 자동으로 쌓이지 않습니다. forward 토너먼트·재지정 증거를 기다리거나 별도 전략 검토 후 재무장 여부를 판단합니다.", "cumulative": {"buy_intended_order_mark_pnl_usd": "-1.14", "sell_intended_order_mark_pnl_usd": "+0.00", "total_intended_order_mark_pnl_usd": "-1.14"}, "counts": {"records": 1, "rejected_orders": 2, "valued_orders": 2, "valued_records": 1}, "latest": {"latest_signal": "INTENT_LOSS", "opportunity_as_of_utc": "2026-06-26T17:03:11Z", "recorded_at_utc": "2026-06-26T17:03:12Z", "rejected_count": 2, "run_id": "[REDACTED_ACCOUNT]", "run_url": "https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT]", "total_intended_order_mark_pnl_usd": "-1.14", "valued_count": 2}}, "reason": "도전자 없음(엣지 확정 + 사과 대 사과로 incumbent 를 앞선 트랙 부재) — 현 전략 유지.", "gates": {"observation_quality_ok": true, "challenger_confirmed": false, "multiplicity_robust": false, "canary_pass": false}, "wrote_files": false}
```

## 라이브 거부 주문 누적 평가 JSON

이 신호는 재지정 결정의 읽기 전용 실행 피드백이다. 기존 5중 게이트를 우회하지 않는다.
```json
{
  "as_of_utc": "2026-07-28T16:14:44Z",
  "counts": {
    "records": 1,
    "rejected_orders": 2,
    "valued_orders": 2,
    "valued_records": 1
  },
  "cumulative": {
    "buy_intended_order_mark_pnl_usd": "-1.14",
    "sell_intended_order_mark_pnl_usd": "+0.00",
    "total_intended_order_mark_pnl_usd": "-1.14"
  },
  "definition": "positive intended_order_mark_pnl_usd means rejected orders would currently look favorable; negative means rejection avoided a worse mark-to-current outcome. This is diagnostic, not accounting PnL.",
  "interpretation_ko": "최신 신호는 보이지만 자동 전략 판단을 내리기에는 표본이 부족합니다.",
  "latest": {
    "latest_signal": "INTENT_LOSS",
    "opportunity_as_of_utc": "2026-06-26T17:03:11Z",
    "recorded_at_utc": "2026-06-26T17:03:12Z",
    "rejected_count": 2,
    "run_id": "[REDACTED_ACCOUNT]",
    "run_url": "https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT]",
    "total_intended_order_mark_pnl_usd": "-1.14",
    "valued_count": 2
  },
  "latest_signal": "INTENT_LOSS",
  "next_action_ko": "최신 손실 의도 신호가 실주문을 막고 있어 새 live 표본은 자동으로 쌓이지 않습니다. forward 토너먼트·재지정 증거를 기다리거나 별도 전략 검토 후 재무장 여부를 판단합니다.",
  "safety_note_ko": "이 신호는 관찰·검토 입력입니다. 주문 재시도, 전략 교체, 자본 변경을 직접 수행하지 않습니다.",
  "schema_version": 1,
  "strategy_loop_input": {
    "effect": "evidence_only_no_gate_override",
    "target": "specs/055-autonomous-reassignment"
  },
  "streaks": {
    "intent_gain": 0,
    "intent_loss": 1
  },
  "thresholds": {
    "execution_review_gain_usd": "+5.00",
    "min_valued_reports": 2,
    "strategy_review_loss_usd": "-5.00",
    "streak_threshold": 2
  },
  "verdict": "INSUFFICIENT_DATA",
  "verdict_label_ko": "표본 부족"
}
```

## ④ 하드닝 캐너리 결과 JSON
```json
(도전자 없음 또는 캐너리 미실행)
```

## forward 토너먼트 리더보드 JSON (읽기 전용)
```json
{
  "adjusted_dsr_threshold": null,
  "as_of_utc": "2026-08-07T23:09:50.081250+00:00",
  "challenger_key": null,
  "champion_key": null,
  "champion_multiplicity_robust": null,
  "comparable_count": 7,
  "headline": "➖ 엣지 확정 트랙 없음 — 비교 가능 트랙 모두 NO_EDGE(우위가 우연과 구별 안 됨). 더 나은 후보 탐색 계속.",
  "incumbent_key": "global",
  "known_count": 7,
  "lagging_keys": [
    "trend",
    "globalfixed",
    "notrend"
  ],
  "max_n_obs": 39,
  "min_n_obs": 33,
  "note": "비교 가능하지만 단순 보유를 과적합 보정 후 못 이긴 상태. 라이브 변경 사유 없음.",
  "observation_health": "OK",
  "observation_note": "모든 후보가 최소 관측을 충족. 관측 수 차이는 참고 정보로만 표시: trend, globalfixed, notrend.",
  "rows": [
    {
      "calmar": "98.042349",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "80.545840",
      "is_incumbent": false,
      "key": "trend",
      "label": "추세 필터 ON (드로다운 방어)",
      "max_drawdown_pct": "93.394390",
      "min_obs": 20,
      "n_obs": 33,
      "psr_vs_benchmark": "0.327408",
      "rank": 1,
      "sharpe": "3.017668",
      "total_return_pct": "80.930398",
      "universe": [
        "MMM",
        "AOS",
        "ABT",
        "ABBV",
        "ACN",
        "ADBE",
        "AMD",
        "AES"
      ],
      "universe_size": 501,
      "verdict": "NO_EDGE"
    },
    {
      "calmar": "53.733327",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "44.731376",
      "is_incumbent": false,
      "key": "multiasset",
      "label": "멀티에셋 분산 추세 (스펙 043)",
      "max_drawdown_pct": "19.890290",
      "min_obs": 20,
      "n_obs": 39,
      "psr_vs_benchmark": "0.739243",
      "rank": 2,
      "sharpe": "3.007743",
      "total_return_pct": "46.299845",
      "universe": [
        "SPY",
        "IEF"
      ],
      "universe_size": 2,
      "verdict": "NO_EDGE"
    },
    {
      "calmar": "29.257344",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "24.333566",
      "is_incumbent": false,
      "key": "globalfixed",
      "label": "글로벌 3자산 추세 고정등가중 (재지정 후보)",
      "max_drawdown_pct": "12.913037",
      "min_obs": 20,
      "n_obs": 36,
      "psr_vs_benchmark": "0.821255",
      "rank": 3,
      "sharpe": "2.815632",
      "total_return_pct": "25.036070",
      "universe": [
        "SPY",
        "IEF",
        "GLD"
      ],
      "universe_size": 3,
      "verdict": "NO_EDGE"
    },
    {
      "calmar": "24.83098",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "56.929508",
      "is_incumbent": false,
      "key": "rmbeta",
      "label": "위험관리 베타 (스펙 042)",
      "max_drawdown_pct": "76.439403",
      "min_obs": 20,
      "n_obs": 39,
      "psr_vs_benchmark": "0.746239",
      "rank": 4,
      "sharpe": "2.513533",
      "total_return_pct": "58.958893",
      "universe": [
        "SPY",
        "QQQ"
      ],
      "universe_size": 2,
      "verdict": "NO_EDGE"
    },
    {
      "calmar": "10.409768",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "10.933550",
      "is_incumbent": true,
      "key": "global",
      "label": "글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD)",
      "max_drawdown_pct": "11.595110",
      "min_obs": 20,
      "n_obs": 39,
      "psr_vs_benchmark": "0.567128",
      "rank": 5,
      "sharpe": "1.793629",
      "total_return_pct": "13.033776",
      "universe": [
        "SPY",
        "IEF",
        "GLD"
      ],
      "universe_size": 3,
      "verdict": "NO_EDGE"
    },
    {
      "calmar": "0.872398",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "7.743391",
      "is_incumbent": false,
      "key": "notrend",
      "label": "추세 필터 OFF (대조군)",
      "max_drawdown_pct": "90.066825",
      "min_obs": 20,
      "n_obs": 34,
      "psr_vs_benchmark": "0.341098",
      "rank": 6,
      "sharpe": "2.538245",
      "total_return_pct": "8.137300",
      "universe": [
        "MMM",
        "AOS",
        "ABT",
        "ABBV",
        "ACN",
        "ADBE",
        "AMD",
        "AES"
      ],
      "universe_size": 501,
      "verdict": "NO_EDGE"
    },
    {
      "calmar": "-1.413632",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "-3.426114",
      "is_incumbent": false,
      "key": "wide",
      "label": "글로벌 분산 추세 확대 (11 슬리브)",
      "max_drawdown_pct": "13.600883",
      "min_obs": 20,
      "n_obs": 39,
      "psr_vs_benchmark": "0.429878",
      "rank": 7,
      "sharpe": "-0.258767",
      "total_return_pct": "-3.250521",
      "universe": [
        "SPY",
        "QQQ",
        "EFA",
        "EEM",
        "IEF",
        "TLT",
        "LQD",
        "GLD"
      ],
      "universe_size": 11,
      "verdict": "NO_EDGE"
    }
  ],
  "schema_version": "1.0",
  "track_count": 7,
  "unknown_count": 0
}
```
