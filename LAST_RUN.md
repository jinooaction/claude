# 라이브 캐너리 포트폴리오 — 최신 실행 (가드형 실거래 채널)

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| timestamp_utc | 2026-09-11T18:27:32Z |
| armed (무장 여부) | true |
| capital_usd | [REDACTED]|
| blocked (자본 가드 거부) | false |
| 첫 체결 전 최신 엣지 재검증 | success |
| event | schedule |
| LIVE 스텝 | failure (success=명령 종료 코드 0) |
| 체결 동기화 | success |
| 사후 측정 | success |
| 사후 계좌 정합성 | success |
| 최초 server timer 증거 조회 | skipped |
| 최초 server timer run_id | none |
| 복구 server timer run_id | none |

> 🟡 **무장됐지만 실주문 job 이 완료되지 않음** — 아래 stderr/로그 확인.

## 드라이런 미리보기 — 무장 시 거래할 내역 (주문 0건)
```json
(preview job 이 직전 sidecar에 발행함)
```

## 첫 체결 전 최신 엣지 재검증
```json
evidence_age_hours=0.3663888888888889 canary_exit=0 profit_exit=0 proxy_parity_exit=0 fundability_exit=0
{"allowed": true, "evidence": {"fills_count": 2}, "fills_count": 2, "reasons": ["strategy already has live fills; existing live risk gates remain authoritative"], "schema_version": "1.0", "state": "ACTIVE_LIVE_TRACK"}
(스냅샷 기록됨: LIVE_PERFORMANCE_SNAPSHOT seq=18814)
{"results": [{"symbol": "SPY", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "IEF", "exchange": "NAS", "fetched": 300, "inserted": 300}, {"symbol": "GLD", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "SCHX", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "SPTI", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "IAUM", "exchange": "AMS", "fetched": 300, "inserted": 300}]}
```

## 라이브 재조정 결과 (armed=true 일 때만)
```json
--- stderr ---
ERROR: server code differs from signed main: .specify/feature.json
```

## KIS 체결 동기화·감사 장부 요약
```
--- fill sync attempt 1/3 ---
열린 주문이 없어 동기화할 대상이 없습니다.
열린 주문: 0건
최근 체결(최대 10): 5건
  ord-b1b5b2b9f6f9  1 @ 43.99500000  2026-09-09T02:52:12.000Z
  ord-85a0145129f0  2 @ 30.22880000  2026-09-08T23:36:32.000Z
  ord-d2a06a6db328  6 @ 31.10000000  2026-06-23T02:20:15.000Z
  ord-ad62318eb3e9  3 @ 118.94000000  2026-06-23T02:20:15.000Z
  ord-36dc6f62e996  1 @ 82.68000000  2026-06-23T02:20:15.000Z
--- fill sync attempt 2/3 ---
열린 주문이 없어 동기화할 대상이 없습니다.
열린 주문: 0건
최근 체결(최대 10): 5건
  ord-b1b5b2b9f6f9  1 @ 43.99500000  2026-09-09T02:52:12.000Z
  ord-85a0145129f0  2 @ 30.22880000  2026-09-08T23:36:32.000Z
  ord-d2a06a6db328  6 @ 31.10000000  2026-06-23T02:20:15.000Z
  ord-ad62318eb3e9  3 @ 118.94000000  2026-06-23T02:20:15.000Z
  ord-36dc6f62e996  1 @ 82.68000000  2026-06-23T02:20:15.000Z
--- fill sync attempt 3/3 ---
열린 주문이 없어 동기화할 대상이 없습니다.
열린 주문: 0건
최근 체결(최대 10): 5건
  ord-b1b5b2b9f6f9  1 @ 43.99500000  2026-09-09T02:52:12.000Z
  ord-85a0145129f0  2 @ 30.22880000  2026-09-08T23:36:32.000Z
  ord-d2a06a6db328  6 @ 31.10000000  2026-06-23T02:20:15.000Z
  ord-ad62318eb3e9  3 @ 118.94000000  2026-06-23T02:20:15.000Z
  ord-36dc6f62e996  1 @ 82.68000000  2026-06-23T02:20:15.000Z
```

## 라이브 트랙 측정 (NAV 스냅샷 + forward-verdict --mode live + 칼마)
```
--- nav + forward verdict ---
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=18815)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "38.54740000", "total_market_value_usd": "103.6300", "total_nav_usd": "142.17740000", "total_unrealized_pnl_usd": "-0.82260000", "broker_reported_nav_usd": null, "holdings": [{"symbol": "IAUM", "qty": 1, "avg_cost_usd": "43.99500000", "mark_price_usd": "43.3400", "market_value_usd": "43.3400", "marked": true, "weight_pct": "30.48304442196861104507467432", "unrealized_pnl_usd": "-0.65500000"}, {"symbol": "SCHX", "qty": 2, "avg_cost_usd": "30.22880000", "mark_price_usd": "30.1450", "market_value_usd": "60.2900", "marked": true, "weight_pct": "42.40477037841457221752542950", "unrealized_pnl_usd": "-0.16760000"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "live", "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8", "measurement_scope": "strategy", "excluded_fills_count": 3, "capital_basis_usd": "143.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
{"schema_version": "1.2", "verdict": "NO_EDGE", "reason": "\ub2e8\uc21c \ubcf4\uc720\ub97c \uc704\ud5d8\uc870\uc815\uc73c\ub85c \ubabb \uc774\uae40; \ub2a5\ub3d9 \uc218\uc775\ub960 PSR 0.620677 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 -3.914613 > \ubca4\uce58 -4.28452 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 41, "min_obs_required": 20, "strategy_sharpe_annual": "-1.743004", "strategy_total_return_pct": "-0.575245", "strategy_max_drawdown_pct": "0.889930", "strategy_calmar": "-3.914613", "benchmark_sharpe_annual": "-1.341666", "benchmark_total_return_pct": "-1.277664", "benchmark_max_drawdown_pct": "1.773663", "benchmark_calmar": "-4.28452", "excess_return_pct": "0.702419", "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": "0.795863", "psr_vs_benchmark": "0.620677", "dsr": null, "num_trials": 1, "min_track_record_obs": "1147.313209", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "live", "snapshot_count": 42, "legacy_snapshots_excluded": 91, "universe": ["SPY", "IEF", "GLD"]}
{"schema_version": "1.0", "status": "CLEAR", "reconciliation_state": "OK", "halt_present": false, "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8", "evidence_quality": "VALID", "reasons": [], "orders_submitted": 0, "halt_cleared": false}
--- live performance ---
{
  "schema_version": "1.2",
  "mode": "live",
  "period": {
    "since_utc": "1970-01-01T00:00:00.000Z",
    "until_utc": "2026-09-11T18:27:25.607Z"
  },
  "fills_count": 2,
  "gross_invested_usd": "104.45260000",
  "realized_pnl_usd": "0",
  "unrealized_pnl_usd": "-0.82260000",
  "total_pnl_usd": "-0.82260000",
  "return_pct": "-0.7875342499851607331938123130",
  "per_symbol": [
    {
      "symbol": "IAUM",
      "qty": 1,
      "avg_cost_usd": "43.99500000",
      "realized_pnl_usd": "0",
      "unrealized_pnl_usd": "-0.65500000",
      "mark_price_usd": "43.3400",
      "market_value_usd": "43.3400",
      "total_pnl_usd": "-0.65500000"
    },
    {
      "symbol": "SCHX",
      "qty": 2,
      "avg_cost_usd": "30.22880000",
      "realized_pnl_usd": "0",
      "unrealized_pnl_usd": "-0.16760000",
      "mark_price_usd": "30.1450",
      "market_value_usd": "60.2900",
      "total_pnl_usd": "-0.16760000"
    }
  ],
  "per_rule": [
    {
      "rule_id": "rebalance:global-trend-fixed:IAUM",
      "realized_pnl_usd": "0",
      "fills": 1,
      "buys": 1,
      "sells": 0
    },
    {
      "rule_id": "rebalance:global-trend-fixed:SCHX",
      "realized_pnl_usd": "0",
      "fills": 1,
      "buys": 1,
      "sells": 0
    }
  ],
  "unmarked_symbols": [],
  "data_quality_warnings": [],
  "risk": null,
  "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8",
  "measurement_scope": "strategy",
  "excluded_symbols": [
    "BHP",
    "MRK",
    "ORANY",
    "RELX"
  ],
  "excluded_fills_count": 3,
  "excluded_realized_pnl_usd": "15.93000000",
  "excluded_unrealized_pnl_usd": "190.54000000",
  "slippage": {
    "measurable_fills": 2,
    "unmeasurable_fills": 0,
    "total_cost_usd": "0.02740000",
    "by_side": [
      {
        "side": "BUY",
        "measurable_fills": 2,
        "avg_bps": "2.576190478739389800696872576",
        "median_bps": "2.576190478739389800696872576",
        "total_cost_usd": "0.02740000"
      },
      {
        "side": "SELL",
        "measurable_fills": 0,
        "avg_bps": null,
        "median_bps": null,
        "total_cost_usd": "0"
      }
    ]
  },
  "fill_latency": {
    "measurable_fills": 1,
    "unmeasurable_fills": 1,
    "avg_sec": "32399.322",
    "median_sec": "32399.322",
    "p95_sec": "32399.322",
    "max_sec": "32399.322"
  }
}
--- performance stderr ---
(스냅샷 기록됨: LIVE_PERFORMANCE_SNAPSHOT seq=18816)
```

## 사후 계좌 정합성
```json
{
  "schema_version": "1.0",
  "status": "CLEAR",
  "observed_at_utc": "2026-09-11T18:27:31.983Z",
  "halt_present_before": false,
  "halt_present_after": false,
  "halt_reason_before": null,
  "reconciliation_state": "OK",
  "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8",
  "evidence_quality": "VALID",
  "halt_cleared": false,
  "orders_submitted": 0,
  "reasons": []
}
```

## 최초·복구 server timer 실행 증거 (GitHub 중복 도착 시)
```json
{}
```
