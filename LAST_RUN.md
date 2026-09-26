# 자율 전략 재지정 — 최신 실행 (스펙 055 / 헌법 X.5)

forward 토너먼트 챔피언이 5중 게이트를 전부 통과하면 라이브 전략을 자동 교체한다.
결정/실행은 테스트된 src 모듈(decide_reassignment + build_reassignment)이 한다.
fail-closed: 도전자 없음·다중검정 미통과·캐너리 PASS 아님 → 재지정 0.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| timestamp_utc | 2026-09-26T05:07:37Z |
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
{"schema_version": "1.2", "action": "HOLD", "incumbent_key": "global", "challenger_key": null, "canary_verdict": null, "observation_health": "OK", "observation_note": "모든 후보 판정이 읽혔고 관측 누적이 같은 속도로 진행 중.", "execution_feedback": {"source": "rejected_order_opportunity_monitor", "effect": "evidence_only_no_gate_override", "verdict": "INSUFFICIENT_DATA", "verdict_label_ko": "표본 부족", "latest_signal": "INTENT_LOSS", "interpretation_ko": "최신 신호는 보이지만 자동 전략 판단을 내리기에는 표본이 부족합니다.", "next_action_ko": "최신 손실 의도 신호가 실주문을 막고 있어 새 live 표본은 자동으로 쌓이지 않습니다. forward 토너먼트·재지정 증거를 기다리거나 별도 전략 검토 후 재무장 여부를 판단합니다.", "cumulative": {"buy_intended_order_mark_pnl_usd": "-1.14", "sell_intended_order_mark_pnl_usd": "+0.00", "total_intended_order_mark_pnl_usd": "-1.14"}, "counts": {"records": 1, "rejected_orders": 2, "valued_orders": 2, "valued_records": 1}, "latest": {"latest_signal": "INTENT_LOSS", "opportunity_as_of_utc": "2026-06-26T17:03:11Z", "recorded_at_utc": "2026-06-26T17:03:12Z", "rejected_count": 2, "run_id": "[REDACTED_ACCOUNT]", "run_url": "https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT]", "total_intended_order_mark_pnl_usd": "-1.14", "valued_count": 2}}, "reason": "도전자 없음(엣지 확정 + 사과 대 사과로 incumbent 를 앞선 트랙 부재) — 현 전략 유지.", "gates": {"observation_quality_ok": true, "challenger_confirmed": false, "multiplicity_robust": false, "canary_pass": false}, "wrote_files": false}
```

## 라이브 거부 주문 누적 평가 JSON

이 신호는 재지정 결정의 읽기 전용 실행 피드백이다. 기존 5중 게이트를 우회하지 않는다.
```json
{
  "as_of_utc": "2026-09-25T19:10:04Z",
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
  "as_of_utc": "2026-09-26T00:49:17.628551+00:00",
  "challenger_key": null,
  "champion_key": null,
  "champion_multiplicity_robust": null,
  "comparable_count": 7,
  "headline": "➖ 엣지 확정 트랙 없음 — 비교 가능 트랙 모두 NO_EDGE(우위가 우연과 구별 안 됨). 더 나은 후보 탐색 계속.",
  "incumbent_key": "global",
  "known_count": 7,
  "lagging_keys": [],
  "max_n_obs": 24,
  "min_n_obs": 24,
  "note": "비교 가능하지만 단순 보유를 과적합 보정 후 못 이긴 상태. 라이브 변경 사유 없음.",
  "observation_health": "OK",
  "observation_note": "모든 후보 판정이 읽혔고 관측 누적이 같은 속도로 진행 중.",
  "rows": [
    {
      "beats_benchmark_calmar": true,
      "calmar": "17.718989",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "0.304644",
      "is_incumbent": false,
      "key": "rmbeta",
      "label": "위험관리 베타 (스펙 042)",
      "max_drawdown_pct": "2.057801",
      "min_obs": 20,
      "n_obs": 24,
      "psr_vs_benchmark": "0.524489",
      "rank": 1,
      "sharpe": "2.812737",
      "significance_method": "paired_active_return_psr_v1",
      "total_return_pct": "3.005000",
      "universe": [
        "SPY",
        "QQQ"
      ],
      "universe_size": 2,
      "verdict": "NO_EDGE"
    },
    {
      "beats_benchmark_calmar": true,
      "calmar": "4.448163",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "2.028512",
      "is_incumbent": false,
      "key": "multiasset",
      "label": "멀티에셋 분산 추세 (스펙 043)",
      "max_drawdown_pct": "1.109058",
      "min_obs": 20,
      "n_obs": 24,
      "psr_vs_benchmark": "0.785556",
      "rank": 2,
      "sharpe": "1.094862",
      "significance_method": "paired_active_return_psr_v1",
      "total_return_pct": "0.459667",
      "universe": [
        "SPY",
        "IEF"
      ],
      "universe_size": 2,
      "verdict": "NO_EDGE"
    },
    {
      "beats_benchmark_calmar": true,
      "calmar": "0.293762",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "0.492407",
      "is_incumbent": false,
      "key": "notrend",
      "label": "추세 필터 OFF (대조군)",
      "max_drawdown_pct": "2.640818",
      "min_obs": 20,
      "n_obs": 24,
      "psr_vs_benchmark": "0.579943",
      "rank": 3,
      "sharpe": "0.133127",
      "significance_method": "paired_active_return_psr_v1",
      "total_return_pct": "0.073625",
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
      "beats_benchmark_calmar": true,
      "calmar": "0.293762",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "0.492785",
      "is_incumbent": false,
      "key": "trend",
      "label": "추세 필터 ON (드로다운 방어)",
      "max_drawdown_pct": "2.640818",
      "min_obs": 20,
      "n_obs": 24,
      "psr_vs_benchmark": "0.579996",
      "rank": 4,
      "sharpe": "0.133126",
      "significance_method": "paired_active_return_psr_v1",
      "total_return_pct": "0.073625",
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
      "beats_benchmark_calmar": true,
      "calmar": "-1.108778",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "1.365138",
      "is_incumbent": false,
      "key": "wide",
      "label": "글로벌 분산 추세 확대 (11 슬리브)",
      "max_drawdown_pct": "0.260082",
      "min_obs": 20,
      "n_obs": 24,
      "psr_vs_benchmark": "0.733740",
      "rank": 5,
      "sharpe": "-0.174458",
      "significance_method": "paired_active_return_psr_v1",
      "total_return_pct": "-0.027500",
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
    },
    {
      "beats_benchmark_calmar": true,
      "calmar": "-4.447079",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "3.332254",
      "is_incumbent": true,
      "key": "global",
      "label": "글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD)",
      "max_drawdown_pct": "0.970599",
      "min_obs": 20,
      "n_obs": 24,
      "psr_vs_benchmark": "0.825098",
      "rank": 6,
      "sharpe": "-1.434692",
      "significance_method": "paired_active_return_psr_v1",
      "total_return_pct": "-0.419333",
      "universe": [
        "SPY",
        "IEF",
        "GLD"
      ],
      "universe_size": 3,
      "verdict": "NO_EDGE"
    },
    {
      "beats_benchmark_calmar": true,
      "calmar": "-6.33717",
      "comparability": "COMPARABLE",
      "dsr": null,
      "dsr_threshold": "0.95",
      "excess_return_pct": "1.552936",
      "is_incumbent": false,
      "key": "globalfixed",
      "label": "글로벌 3자산 추세 고정등가중 (재지정 후보)",
      "max_drawdown_pct": "3.285021",
      "min_obs": 20,
      "n_obs": 24,
      "psr_vs_benchmark": "0.631436",
      "rank": 7,
      "sharpe": "-2.540872",
      "significance_method": "paired_active_return_psr_v1",
      "total_return_pct": "-2.198500",
      "universe": [
        "SPY",
        "IEF",
        "GLD"
      ],
      "universe_size": 3,
      "verdict": "NO_EDGE"
    }
  ],
  "schema_version": "1.0",
  "track_count": 7,
  "unknown_count": 0
}
```
