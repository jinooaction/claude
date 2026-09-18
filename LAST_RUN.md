# 라이브 캐너리 포트폴리오 — 최신 실행 (가드형 실거래 채널)

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| timestamp_utc | 2026-09-18T17:45:43Z |
| armed (무장 여부) | true |
| capital_usd | [REDACTED]|
| blocked (자본 가드 거부) | false |
| 첫 체결 전 최신 엣지 재검증 | success |
| event | schedule |
| LIVE 스텝 | success (success=명령 종료 코드 0) |
| 체결 동기화 | success |
| 사후 측정 | success |
| 사후 계좌 정합성 | success |
| 최초 server timer 증거 조회 | skipped |
| 최초 server timer run_id | none |
| 복구 server timer run_id | none |

> ⚠ **무장 + production 기계 승인 + 실행** — 예약이면 실주문, 수동이면 주문 없는 검증이다.
> 아래 라이브 재조정 결과를 확인하라.

## 드라이런 미리보기 — 무장 시 거래할 내역 (주문 0건)
```json
(preview job 이 직전 sidecar에 발행함)
```

## 첫 체결 전 최신 엣지 재검증
```json
evidence_age_hours=4.151111111111111 canary_exit=0 profit_exit=0 proxy_parity_exit=0 fundability_exit=0
{"allowed": true, "evidence": {"fills_count": 2}, "fills_count": 2, "reasons": ["strategy already has live fills; existing live risk gates remain authoritative"], "schema_version": "1.0", "state": "ACTIVE_LIVE_TRACK"}
(스냅샷 기록됨: LIVE_PERFORMANCE_SNAPSHOT seq=19123)
{"results": [{"symbol": "SPY", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "IEF", "exchange": "NAS", "fetched": 300, "inserted": 300}, {"symbol": "GLD", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "SCHX", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "SPTI", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "IAUM", "exchange": "AMS", "fetched": 300, "inserted": 300}]}
```

## 라이브 재조정 결과 (armed=true 일 때만)
```json
LIVE_ORDER_AUTHORIZED run_id=[REDACTED_ACCOUNT] commit=d244c62f12d975e17e9d2f9af4952bf4dc3ec17f capital=143 nonce=[REDACTED_ACCOUNT]-1
LIVE_ORDER_SESSION_CLAIMED market_session=2026-09-18 run_id=[REDACTED_ACCOUNT] source=github_schedule claimed_at=2026-09-18T17:44:27Z
{"portfolio_id": "global-trend-fixed", "mode": "live", "account_wide": true, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": "830.89", "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"SCHX": "0.333334", "IAUM": "0.083333"}, "signal_target_weights": {"SPY": "0.333334", "GLD": "0.083333"}, "execution_symbol_map": {"SPY": "SCHX", "IEF": "SPTI", "GLD": "IAUM"}, "fundability": {"schema_version": "1.1", "fundable": false, "capital_usd": "143.0", "investable_usd": "141.570", "active_target_count": 2, "funded_target_count": 2, "funded_target_ratio": "1", "whole_share_eligible_target_count": 1, "funded_whole_share_target_count": 1, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {"IAUM": {"target_notional_usd": "11.797452810", "one_share_price_usd": "43.7800"}}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"SCHX": "0.333334", "IAUM": "0.083333"}, "holdings": {"IAUM": 1, "SCHX": 2}, "prices": {"IAUM": "43.7800", "SCHX": "29.9950"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "10.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"SCHX": 2, "IAUM": 1}, "projected_weights": {"SCHX": "0.4195104895104895104895104895", "IAUM": "0.3061538461538461538461538462"}, "l1_weight_error": "0.3131640056643356643356643357", "max_leg_weight_error": "0.2236541761538461538461538462", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": false, "max_leg_weight_error": false, "exposure_caps": true}, "reasons": ["l1_weight_error", "max_leg_weight_error"]}, "results": [], "withheld_orders": [{"symbol": "ORANY", "side": "SELL", "requested_qty": 28, "reason": "unmanaged_holding"}]}
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
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=19124)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "38.54740000", "total_market_value_usd": "103.7548", "total_nav_usd": "142.30220000", "total_unrealized_pnl_usd": "-0.69780000", "broker_reported_nav_usd": null, "holdings": [{"symbol": "IAUM", "qty": 1, "avg_cost_usd": "43.99500000", "mark_price_usd": "43.7700", "market_value_usd": "43.7700", "marked": true, "weight_pct": "30.75848440853338880214079614", "unrealized_pnl_usd": "-0.22500000"}, {"symbol": "SCHX", "qty": 2, "avg_cost_usd": "30.22880000", "mark_price_usd": "29.9924", "market_value_usd": "59.9848", "marked": true, "weight_pct": "42.15310796319382272375268970", "unrealized_pnl_usd": "-0.47280000"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "live", "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8", "measurement_scope": "strategy", "excluded_fills_count": 3, "capital_basis_usd": "143.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
{"schema_version": "1.2", "verdict": "NO_EDGE", "reason": "\ub2a5\ub3d9 \uc218\uc775\ub960 PSR 0.714132 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 -2.017988 > \ubca4\uce58 -3.820069 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 47, "min_obs_required": 20, "strategy_sharpe_annual": "-0.969077", "strategy_total_return_pct": "-0.487972", "strategy_max_drawdown_pct": "1.282797", "strategy_calmar": "-2.017988", "benchmark_sharpe_annual": "-1.647485", "benchmark_total_return_pct": "-1.854049", "benchmark_max_drawdown_pct": "2.499214", "benchmark_calmar": "-3.820069", "excess_return_pct": "1.366077", "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": "1.403477", "psr_vs_benchmark": "0.714132", "dsr": null, "num_trials": 1, "min_track_record_obs": "390.180013", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "live", "snapshot_count": 48, "legacy_snapshots_excluded": 91, "universe": ["SPY", "IEF", "GLD"]}
{"schema_version": "1.0", "status": "CLEAR", "reconciliation_state": "OK", "halt_present": false, "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8", "evidence_quality": "VALID", "reasons": [], "orders_submitted": 0, "halt_cleared": false}
--- live performance ---
{
  "schema_version": "1.2",
  "mode": "live",
  "period": {
    "since_utc": "1970-01-01T00:00:00.000Z",
    "until_utc": "2026-09-18T17:45:36.238Z"
  },
  "fills_count": 2,
  "gross_invested_usd": "104.45260000",
  "realized_pnl_usd": "0",
  "unrealized_pnl_usd": "-0.69780000",
  "total_pnl_usd": "-0.69780000",
  "return_pct": "-0.6680542178940495497479239387",
  "per_symbol": [
    {
      "symbol": "IAUM",
      "qty": 1,
      "avg_cost_usd": "43.99500000",
      "realized_pnl_usd": "0",
      "unrealized_pnl_usd": "-0.22500000",
      "mark_price_usd": "43.7700",
      "market_value_usd": "43.7700",
      "total_pnl_usd": "-0.22500000"
    },
    {
      "symbol": "SCHX",
      "qty": 2,
      "avg_cost_usd": "30.22880000",
      "realized_pnl_usd": "0",
      "unrealized_pnl_usd": "-0.47280000",
      "mark_price_usd": "29.9924",
      "market_value_usd": "59.9848",
      "total_pnl_usd": "-0.47280000"
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
  "excluded_unrealized_pnl_usd": "198.66000000",
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
(스냅샷 기록됨: LIVE_PERFORMANCE_SNAPSHOT seq=19125)
```

## 사후 계좌 정합성
```json
{
  "schema_version": "1.0",
  "status": "CLEAR",
  "observed_at_utc": "2026-09-18T17:45:43.278Z",
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
