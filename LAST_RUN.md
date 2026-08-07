# 라이브 캐너리 포트폴리오 — 최신 실행 (가드형 실거래 채널)

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| timestamp_utc | 2026-08-07T15:59:51Z |
| armed (무장 여부) | false |
| capital_usd | [REDACTED]|
| blocked (자본 가드 거부) | false |
| event | schedule |
| LIVE 스텝 | preview-job-skipped (실주문은 production-gated job 전용) |

> 🛡 **드라이런 미리보기만** (armed=false) — 실주문 0건. 아래는 *무장 시* 실거래가
> 무엇을 사고팔지 보여준다. 무장하려면 automation/rebalance-live.request 의
> armed: true 로 머지(룰 워커 충돌 먼저 해소).

## 드라이런 미리보기 — 무장 시 거래할 내역 (주문 0건)
```json
{"portfolio_id": "global-trend", "mode": "dry-run", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "222.82", "target_weights": {"SPY": "0.233648", "GLD": "0.050011"}, "results": [{"symbol": "AAPL", "side": "SELL", "requested_qty": 2, "routed_qty": 0, "limit_price_usd": "275.20", "state": "SKIPPED_PER_TRADE_CAP", "reason": "per_trade_cap_below_one_share"}, {"symbol": "AMZN", "side": "SELL", "requested_qty": 2, "routed_qty": 0, "limit_price_usd": "256.52", "state": "SKIPPED_PER_TRADE_CAP", "reason": "per_trade_cap_below_one_share"}, {"symbol": "GOOGL", "side": "SELL", "requested_qty": 1, "routed_qty": 0, "limit_price_usd": "361.85", "state": "SKIPPED_PER_TRADE_CAP", "reason": "per_trade_cap_below_one_share"}, {"symbol": "MSFT", "side": "SELL", "requested_qty": 1, "routed_qty": 0, "limit_price_usd": "357.04", "state": "SKIPPED_PER_TRADE_CAP", "reason": "per_trade_cap_below_one_share"}, {"symbol": "NVDA", "side": "SELL", "requested_qty": 2, "routed_qty": 1, "limit_price_usd": "222.82", "state": "DRY_RUN", "reason": null}], "withheld_orders": []}
```

## 라이브 재조정 결과 (armed=true 일 때만)
```json
(preview job — 실주문은 production-gated job 이 승인 뒤 별도 발행)
```

## 라이브 트랙 측정 (NAV 스냅샷 + forward-verdict --mode live + 칼마)
```
{"schema_version": "1.0", "source": "ledger", "cash_usd": "500.0", "total_market_value_usd": "0", "total_nav_usd": "500.0", "total_unrealized_pnl_usd": "0", "broker_reported_nav_usd": null, "holdings": [], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "live"}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=16264)
{"schema_version": "1.1", "verdict": "INSUFFICIENT_DATA", "reason": "\uad00\uce21 18\uac1c < \ucd5c\uc18c 20\uac1c \u2014 \uc0e4\ud504\uac00 \ud1b5\uacc4\uc801\uc73c\ub85c \ubb34\uc758\ubbf8", "n_obs": 18, "min_obs_required": 20, "strategy_sharpe_annual": null, "strategy_total_return_pct": "0.000000", "strategy_max_drawdown_pct": "0.000000", "strategy_calmar": null, "benchmark_sharpe_annual": null, "benchmark_total_return_pct": null, "benchmark_max_drawdown_pct": null, "benchmark_calmar": null, "excess_return_pct": null, "beats_benchmark_calmar": false, "psr_vs_benchmark": null, "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": false, "mode": "live", "snapshot_count": 19, "legacy_snapshots_excluded": 50, "universe": ["SPY", "IEF", "GLD"]}
```
