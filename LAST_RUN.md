# 라이브 캐너리 포트폴리오 — 최신 실행 (가드형 실거래 채널)

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| timestamp_utc | 2026-09-05T02:30:39Z |
| armed (무장 여부) | true |
| capital_usd | [REDACTED]|
| blocked (자본 가드 거부) | false |
| 첫 체결 전 최신 엣지 재검증 | success |
| event | workflow_dispatch |
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
evidence_age_hours=0.017222222222222222 canary_exit=0 profit_exit=0 proxy_parity_exit=0 fundability_exit=0
{"allowed": true, "evidence": {"candidate_id": "globalfixed-ensemble-3-6-9-12", "checks": {"evidence_fresh": true, "execution_proxy_parity": true, "exploration_canary_ready": false, "forward_calmar": false, "forward_observations": false, "forward_psr": false, "forward_significance_method": true, "fundability": true, "hardened_canary": true, "historical_passed": true, "historical_verdict": true}, "declared_canary_capital_pct": "10.0", "entry_route": "operational_canary", "entry_source": "operational_canary", "evidence_age_hours": 0.017222222222222222, "execution_proxy_parity_passed": true, "expected_capital_usd": "143", "expected_operational_capital_pct": "10.0", "factory_assessment": {"candidate_count": 16, "checks": {"all_blocking_gates_pass": false, "all_candidates_complete": true, "audit_candidate_ids_unique": true, "audit_count_recomputed": true, "audit_fingerprints_unique": true, "audit_gate_counts_match": true, "audit_identity_complete": true, "audit_rows_complete": true, "audit_rows_present": true, "benchmark_execution_parity": false, "candidate_count_minimum": true, "current_family_is_audit_tail": true, "development_selection_match": false, "development_winner_recomputed": false, "factory_edge": false, "family_dsr_recomputed": false, "family_pbo": false, "family_pbo_recomputed": true, "family_statistics_inputs": true, "gate_rows_present": true, "historical_data_not_reused": true, "point_in_time_data": false, "prior_count_recomputed": true, "program_research_budget": true, "repository_calibration": true, "required_audit_gates": true, "research_canary_eligible": false, "research_family_audit_present": true, "research_family_audit_recomputed": true, "research_family_count_recomputed": true, "research_family_ids_recomputed": true, "research_live_parity": false, "selected_output_complete": false, "selected_psr_matches_record": false, "selected_psr_threshold": false, "selected_record_match": false, "standardized_statistics": false, "thresholds_frozen_before_results": true, "trial_count_recomputed": true, "trial_identities_unique": true, "trial_rows_complete": true, "trial_rows_present": true}, "complete_trial_count": 16, "contract_version": "calibrated-family-entry-v3.1", "eligible": false, "global_audit_trial_count": 800, "program_multiplicity": {"calibration_complete": true, "claimed_dsr": "0.964996", "claimed_pbo": "0.277778", "claimed_research_family_count": 20, "dsr_diagnostic": {"blocking": false, "passed": false, "threshold": "0.95"}, "family_calibrations": {"16": true, "64": true}, "maximum_research_families": 20, "method": "calibrated-family-risk-budget-v1", "per_family_false_acceptance_max": "0.01", "program_false_acceptance_bound": "0.20", "program_false_acceptance_budget": "0.2", "raw_bonferroni_diagnostic": {"adjusted_p": "1", "blocking": false, "global_trial_count": 800, "method": "bonferroni-global-fwer-v1", "passed": false, "raw_one_sided_p": "0.728464", "required_psr": "0.9999375", "threshold": "0.05"}, "recomputed_dsr": null, "recomputed_pbo": "0.277778", "research_family_count": 20, "selected_psr": "0.271536"}, "reasons": ["factory_edge", "research_canary_eligible", "all_blocking_gates_pass", "selected_output_complete", "selected_record_match", "development_selection_match", "development_winner_recomputed", "selected_psr_matches_record", "selected_psr_threshold", "point_in_time_data", "benchmark_execution_parity", "research_live_parity", "family_dsr_recomputed", "standardized_statistics", "family_pbo"], "selected_candidate_id": null, "selected_strategy_fingerprint": null}, "factory_candidate_id": null, "factory_checks": {"factory_contract_complete": false, "factory_evidence_fresh": false, "factory_execution_proxy_parity": true, "factory_fundability": true, "factory_hardened_canary": true, "factory_strategy_config_valid": false, "factory_strategy_fingerprint": false}, "factory_evidence_age_hours": 61.[REDACTED_ACCOUNT], "forward_n_obs": 9, "forward_psr": null, "forward_significance_method": "paired_active_return_psr_v1", "fundability": {"active_target_count": 2, "capital_usd": "143.0", "caps": {"canary_acceptance_drawdown_pct": "3.0", "canary_capital_pct": "10.0", "canary_min_duration_days": 10, "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "global_exposure_pct": "100.0", "max_total_drawdown_pct": "20", "per_symbol_pct": "60.0", "per_trade_pct": "50.0"}, "checks": {"active_targets_present": true, "capital_positive": true, "exposure_caps": true, "exposure_quote_coverage": true, "funded_whole_share_target_ratio": true, "holdings_long_only": true, "invested_fraction_bounded": true, "l1_weight_error": true, "max_leg_weight_error": true, "quote_coverage": true, "target_weights_bounded": true, "whole_share_eligible_targets_present": true}, "effective_side": "both", "fundable": true, "funded_target_count": 2, "funded_target_ratio": "1", "funded_whole_share_target_count": 1, "funded_whole_share_target_ratio": "1", "holdings": {}, "investable_usd": "141.570", "invested_fraction": "0.99", "l1_weight_error": "0.2387062937062937062937062937", "max_leg_weight_error": "0.1440915690909090909090909091", "order_prices": {"IAUM": "44.29", "SCHX": "30.42"}, "planned_orders": [{"qty": 1, "side": "BUY", "symbol": "IAUM"}, {"qty": 2, "side": "BUY", "symbol": "SCHX"}], "prices": {"IAUM": "44.2000", "SCHX": "30.3600"}, "projected_quantities": {"IAUM": 1, "SCHX": 2}, "projected_weights": {"IAUM": "0.3090909090909090909090909091", "SCHX": "0.4246153846153846153846153846"}, "quote_coverage_ratio": "1", "reasons": [], "schema_version": "1.1", "target_weights": {"IAUM": "0.166666", "SCHX": "0.333334"}, "whole_share_eligible_target_count": 1, "whole_share_ineligible_targets": {"IAUM": {"one_share_price_usd": "44.2000", "target_notional_usd": "23.594905620"}}}, "max_evidence_age_hours": 36.0, "min_forward_obs": 40, "min_forward_psr": 0.8, "operational_assessment": {"alpha_confirmed": false, "candidate_id": "globalfixed-ensemble-3-6-9-12", "capital_fraction": 0.1, "checks": {"benchmark_snapshot_matches_raw": true, "candidate_id": true, "candidate_snapshot_matches_raw": true, "code_commit": true, "code_commit_format": true, "data_fingerprint": true, "decision_bounded": true, "development_snapshot_present": true, "evidence_fresh": true, "historical_absolute_holdout_drawdown": true, "historical_absolute_holdout_sharpe": true, "historical_annual_cost_bps": true, "historical_benchmark_drawdown_ratio": true, "historical_benchmark_sharpe_superiority": true, "historical_candidate_preregistered": true, "historical_development_months": true, "historical_holdout_months": true, "historical_positive_holdout_cagr": true, "historical_temporal_overlap": true, "live_strategy_fingerprint": true, "raw_factors_aligned": true, "raw_factors_positive": true, "role": true, "route": true, "safety_no_side_effect": true, "schema_version": true, "strategy_fingerprint": true, "strategy_fingerprint_format": true}, "eligible": true, "max_rung": 1, "reasons": [], "recomputed": {"active_psr": 0.553141, "benchmark": {"cagr_pct": 8.465965, "calmar": 0.490246, "max_drawdown_pct": 17.268823, "n_months": 236, "sharpe": 1.284444}, "candidate": {"cagr_pct": 8.713987, "calmar": 1.563632, "max_drawdown_pct": 5.572914, "n_months": 236, "sharpe": 1.841859}, "cost_sensitivity": {"100": {"active_sharpe": -0.092379, "candidate_sharpe": 1.733081}, "150": {"active_sharpe": -0.215302, "candidate_sharpe": 1.62371}}}, "schema_version": "1.0", "strategy_fingerprint": "sha256:d4376129fa4181a92cd572638fa2940355687a617e0364c920b4fa8ceee1383e"}, "operational_checks": {"operational_bounded_rung": true, "operational_canary_capital_contract": true, "operational_code_commit": true, "operational_contract_complete": true, "operational_entry_route": true, "operational_evidence_fresh": true, "operational_execution_proxy_parity": true, "operational_fundability": true, "operational_hardened_canary": true, "operational_live_strategy_fingerprint": true, "operational_strategy_fingerprint": true}, "operational_evidence_age_hours": 0.017222222222222222}, "fills_count": 0, "reasons": ["all first-entry gates passed"], "schema_version": "1.0", "state": "ENTRY_READY"}
(스냅샷 기록됨: LIVE_PERFORMANCE_SNAPSHOT seq=17805)
{"results": [{"symbol": "SPY", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "IEF", "exchange": "NAS", "fetched": 300, "inserted": 300}, {"symbol": "GLD", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "SCHX", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "SPTI", "exchange": "AMS", "fetched": 300, "inserted": 300}, {"symbol": "IAUM", "exchange": "AMS", "fetched": 300, "inserted": 300}]}
```

## 라이브 재조정 결과 (armed=true 일 때만)
```json
LIVE_ORDER_AUTHORIZED run_id=[REDACTED_ACCOUNT] commit=4a5f43add677155382487f23a8a47debd2daa378 capital=143 nonce=[REDACTED_ACCOUNT]-1
```

## KIS 체결 동기화·감사 장부 요약
```
--- fill sync attempt 1/3 ---
열린 주문이 없어 동기화할 대상이 없습니다.
열린 주문: 0건
최근 체결(최대 10): 3건
  ord-d2a06a6db328  6 @ 31.10000000  2026-06-23T02:20:15.000Z
  ord-ad62318eb3e9  3 @ 118.94000000  2026-06-23T02:20:15.000Z
  ord-36dc6f62e996  1 @ 82.68000000  2026-06-23T02:20:15.000Z
--- fill sync attempt 2/3 ---
열린 주문이 없어 동기화할 대상이 없습니다.
열린 주문: 0건
최근 체결(최대 10): 3건
  ord-d2a06a6db328  6 @ 31.10000000  2026-06-23T02:20:15.000Z
  ord-ad62318eb3e9  3 @ 118.94000000  2026-06-23T02:20:15.000Z
  ord-36dc6f62e996  1 @ 82.68000000  2026-06-23T02:20:15.000Z
--- fill sync attempt 3/3 ---
열린 주문이 없어 동기화할 대상이 없습니다.
열린 주문: 0건
최근 체결(최대 10): 3건
  ord-d2a06a6db328  6 @ 31.10000000  2026-06-23T02:20:15.000Z
  ord-ad62318eb3e9  3 @ 118.94000000  2026-06-23T02:20:15.000Z
  ord-36dc6f62e996  1 @ 82.68000000  2026-06-23T02:20:15.000Z
```

## 라이브 트랙 측정 (NAV 스냅샷 + forward-verdict --mode live + 칼마)
```
--- nav + forward verdict ---
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=17806)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "143.0", "total_market_value_usd": "0", "total_nav_usd": "143.0", "total_unrealized_pnl_usd": "0", "broker_reported_nav_usd": null, "holdings": [], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "live", "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8", "measurement_scope": "strategy", "excluded_fills_count": 3, "capital_basis_usd": "143.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
{"schema_version": "1.2", "verdict": "INSUFFICIENT_DATA", "reason": "\uc804\ub7b5 \uc218\uc775\ub960 \ubd84\uc0b0\uc774 0\uc774\uac70\ub098 \ud1b5\uacc4 \uacc4\uc0b0 \ubd88\uac00 \u2014 \ud310\uc815 \ubcf4\ub958", "n_obs": 33, "min_obs_required": 20, "strategy_sharpe_annual": null, "strategy_total_return_pct": "0.000000", "strategy_max_drawdown_pct": "0.000000", "strategy_calmar": null, "benchmark_sharpe_annual": null, "benchmark_total_return_pct": null, "benchmark_max_drawdown_pct": null, "benchmark_calmar": null, "excess_return_pct": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": null, "psr_vs_benchmark": null, "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "live", "snapshot_count": 34, "legacy_snapshots_excluded": 91, "universe": ["SPY", "IEF", "GLD"]}
{"schema_version": "1.0", "status": "CLEAR", "reconciliation_state": "OK", "halt_present": false, "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8", "evidence_quality": "VALID", "reasons": [], "orders_submitted": 0, "halt_cleared": false}
--- live performance ---
{
  "schema_version": "1.2",
  "mode": "live",
  "period": {
    "since_utc": "1970-01-01T00:00:00.000Z",
    "until_utc": "2026-09-05T02:30:33.290Z"
  },
  "fills_count": 0,
  "gross_invested_usd": "0",
  "realized_pnl_usd": "0",
  "unrealized_pnl_usd": "0",
  "total_pnl_usd": "0",
  "return_pct": null,
  "per_symbol": [],
  "per_rule": [],
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
  "excluded_unrealized_pnl_usd": "187.18000000",
  "slippage": {
    "measurable_fills": 0,
    "unmeasurable_fills": 0,
    "total_cost_usd": "0",
    "by_side": [
      {
        "side": "BUY",
        "measurable_fills": 0,
        "avg_bps": null,
        "median_bps": null,
        "total_cost_usd": "0"
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
    "measurable_fills": 0,
    "unmeasurable_fills": 0,
    "avg_sec": null,
    "median_sec": null,
    "p95_sec": null,
    "max_sec": null
  }
}
--- performance stderr ---
(스냅샷 기록됨: LIVE_PERFORMANCE_SNAPSHOT seq=17807)
```

## 사후 계좌 정합성
```json
{
  "schema_version": "1.0",
  "status": "CLEAR",
  "observed_at_utc": "2026-09-05T02:30:38.851Z",
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
