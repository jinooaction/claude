# 자본 사다리 게이트 — 최신 실행 (스펙 050; 스펙 049 승계)

헌법 X.4 v11.0.0. 단0=0% → 단1=10% 운영 검증 → 단2=20% 탐색 → 단3=25% → 단4=50% → 단5=100%
(실계좌 NAV 대비). 내려가는 건 낙폭 하나로 즉시, 올라가는 건 세 증거 전부.
판정 계산은 read-only — 서버 상태 무변경, 주문 0건.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| timestamp_utc | 2026-09-05T02:10:58Z |
| trigger | workflow_dispatch |
| **결정(action)** | **STAY** |
| 단(rung) | 1 → 1 |
| 자본 | $? (실계좌 NAV $1434.91000000) |
| 엣지 출처 | none |
| 센티넬 변경 | false |
| PR | (없음 — 변경 없음) |
| 머지 | n/a |

## 의미

⏳ **유지** — 승격 증거 미충족·강등 사유 없음(정상).

- 사유: 단 1 유지 — 승격 증거 미충족(관측 2/20, 경과 0.0028914351851851853일/27, 낙폭 0.000000%, forward_confirmed=False), 강등 사유 없음.

## 결정 JSON
```json
{"schema_version": "1.0", "action": "STAY", "current_rung": 1, "target_rung": 1, "reason": "\ub2e8 1 \uc720\uc9c0 \u2014 \uc2b9\uaca9 \uc99d\uac70 \ubbf8\ucda9\uc871(\uad00\uce21 2/20, \uacbd\uacfc 0.0028914351851851853\uc77c/27, \ub099\ud3ed 0.000000%, forward_confirmed=False), \uac15\ub4f1 \uc0ac\uc720 \uc5c6\uc74c.", "account_nav_usd": "1434.91000000", "target_capital_usd": null, "live_dd_pct": "0.000000", "live_obs": 2, "entry_route": "operational_canary", "edge_source": "none", "exploration_verdict": {"verdict": "EXPLORATION_CANARY_WAIT", "candidate_id": "globalfixed-ensemble-3-6-9-12", "historical_forward_ready": false, "hardened_canary_pass": true, "fundability_passed": true, "execution_proxy_parity_passed": true, "route_calibrated": false, "capital_eligible": false, "calibration_reason": "exploration full-path calibration is not registered"}, "factory_verdict": {"verdict": "RESEARCH_CANARY_WAIT", "candidate_id": null, "contract_version": "calibrated-family-entry-v3.1", "contract_complete": false, "contract_reasons": ["factory_edge", "research_canary_eligible", "all_blocking_gates_pass", "selected_output_complete", "selected_record_match", "development_selection_match", "development_winner_recomputed", "selected_psr_matches_record", "selected_psr_threshold", "point_in_time_data", "benchmark_execution_parity", "research_live_parity", "family_dsr_recomputed", "standardized_statistics", "family_pbo"], "candidate_count": 16, "complete_trials": 16, "exact_strategy_match": false, "hardened_canary_pass": true, "evidence_age_hours": 61.033055555555556, "fundability_passed": true, "execution_proxy_parity_passed": true, "entry_execution_ready": true, "execution_proxy_parity": {"checks": {"all_pairs_passed": true, "mapping_exact": true, "pair_count": true}, "contract": {"lookback_sessions": 252, "max_annualized_return_gap": 0.03, "max_annualized_tracking_error": 0.06, "max_evidence_age_hours": 36.0, "max_market_data_age_days": 7, "min_common_sessions": 252, "min_median_dollar_volume_usd": "1000000", "min_return_correlation": 0.95}, "dataset_version": "sqlite-price_bars-1d", "evidence_digest": "sha256:c5bc015b2db4804e76571e41f824f960a74b43032252b7c14449f99c9cfbcde1", "observed_at_utc": "2026-09-05T02:10:40.499546Z", "pairs": [{"annualized_return_gap": 0.004208311269351839, "annualized_tracking_error": 0.008187170707769385, "checks": {"annualized_return_gap": true, "annualized_tracking_error": true, "common_sessions": true, "execution_liquidity": true, "freshness": true, "latest_session_aligned": true, "return_correlation": true}, "common_sessions": 252, "execution_latest_session": "2026-09-04", "execution_symbol": "IAUM", "first_session": "2025-09-05", "last_session": "2026-09-04", "median_execution_dollar_volume_usd": "120169570.6700", "passed": true, "return_correlation": 0.9996593372585979, "signal_latest_session": "2026-09-04", "signal_symbol": "GLD"}, {"annualized_return_gap": 0.008911375593547488, "annualized_tracking_error": 0.01541699094753887, "checks": {"annualized_return_gap": true, "annualized_tracking_error": true, "common_sessions": true, "execution_liquidity": true, "freshness": true, "latest_session_aligned": true, "return_correlation": true}, "common_sessions": 252, "execution_latest_session": "2026-09-04", "execution_symbol": "SPTI", "first_session": "2025-09-05", "last_session": "2026-09-04", "median_execution_dollar_volume_usd": "50595477.2511", "passed": true, "return_correlation": 0.9777398740074984, "signal_latest_session": "2026-09-04", "signal_symbol": "IEF"}, {"annualized_return_gap": 0.006630246416671648, "annualized_tracking_error": 0.010052200860913539, "checks": {"annualized_return_gap": true, "annualized_tracking_error": true, "common_sessions": true, "execution_liquidity": true, "freshness": true, "latest_session_aligned": true, "return_correlation": true}, "common_sessions": 252, "execution_latest_session": "2026-09-04", "execution_symbol": "SCHX", "first_session": "2025-09-05", "last_session": "2026-09-04", "median_execution_dollar_volume_usd": "396865518.7673", "passed": true, "return_correlation": 0.9969513096870555, "signal_latest_session": "2026-09-04", "signal_symbol": "SPY"}], "passed": true, "schema_version": "1.0", "symbol_map": {"GLD": "IAUM", "IEF": "SPTI", "SPY": "SCHX"}}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "143.0", "investable_usd": "141.570", "active_target_count": 2, "funded_target_count": 2, "funded_target_ratio": "1", "whole_share_eligible_target_count": 1, "funded_whole_share_target_count": 1, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {"IAUM": {"target_notional_usd": "23.594905620", "one_share_price_usd": "44.2000"}}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"SCHX": "0.333334", "IAUM": "0.166666"}, "holdings": {}, "prices": {"IAUM": "44.2000", "SCHX": "30.3600"}, "order_prices": {"IAUM": "44.29", "SCHX": "30.42"}, "planned_orders": [{"symbol": "IAUM", "side": "BUY", "qty": 1}, {"symbol": "SCHX", "side": "BUY", "qty": 2}], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "10.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"SCHX": 2, "IAUM": 1}, "projected_weights": {"SCHX": "0.4246153846153846153846153846", "IAUM": "0.3090909090909090909090909091"}, "l1_weight_error": "0.2387062937062937062937062937", "max_leg_weight_error": "0.1440915690909090909090909091", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "expected_research_capital_usd": 143}, "operational_verdict": {"verdict": "OPERATIONAL_CANARY_READY", "candidate_id": "globalfixed-ensemble-3-6-9-12", "assessment": {"schema_version": "1.0", "eligible": true, "alpha_confirmed": false, "capital_fraction": 0.1, "max_rung": 1, "candidate_id": "globalfixed-ensemble-3-6-9-12", "strategy_fingerprint": "sha256:d4376129fa4181a92cd572638fa2940355687a617e0364c920b4fa8ceee1383e", "reasons": [], "checks": {"schema_version": true, "role": true, "route": true, "candidate_id": true, "code_commit_format": true, "code_commit": true, "strategy_fingerprint_format": true, "strategy_fingerprint": true, "live_strategy_fingerprint": true, "evidence_fresh": true, "raw_factors_aligned": true, "raw_factors_positive": true, "data_fingerprint": true, "candidate_snapshot_matches_raw": true, "benchmark_snapshot_matches_raw": true, "development_snapshot_present": true, "historical_candidate_preregistered": true, "historical_development_months": true, "historical_holdout_months": true, "historical_temporal_overlap": true, "historical_annual_cost_bps": true, "historical_positive_holdout_cagr": true, "historical_absolute_holdout_sharpe": true, "historical_absolute_holdout_drawdown": true, "historical_benchmark_sharpe_superiority": true, "historical_benchmark_drawdown_ratio": true, "decision_bounded": true, "safety_no_side_effect": true}, "recomputed": {"candidate": {"n_months": 236, "cagr_pct": 8.713987, "sharpe": 1.841859, "max_drawdown_pct": 5.572914, "calmar": 1.563632}, "benchmark": {"n_months": 236, "cagr_pct": 8.465965, "sharpe": 1.284444, "max_drawdown_pct": 17.268823, "calmar": 0.490246}, "active_psr": 0.553141, "cost_sensitivity": {"100": {"candidate_sharpe": 1.733081, "active_sharpe": -0.092379}, "150": {"candidate_sharpe": 1.62371, "active_sharpe": -0.215302}}}}, "alpha_confirmed": false, "max_rung": 1, "capital_fraction": 0.1, "hardened_canary_pass": true, "fundability_passed": true, "execution_proxy_parity_passed": true, "evidence_age_hours": 0.014166666666666666, "expected_operational_capital_usd": 143}, "standard_forward_calibration": {"verdict": "UNDERPOWERED", "false_positive_control_passed": true, "detection_power_passed": false, "code_commit_match": true}}
```

## forward 판정 JSON (검증된 앙상블, read-only)
```json
{"schema_version": "1.2", "verdict": "INSUFFICIENT_DATA", "reason": "\uad00\uce21 9\uac1c < \ucd5c\uc18c 20\uac1c \u2014 \uc0e4\ud504\uac00 \ud1b5\uacc4\uc801\uc73c\ub85c \ubb34\uc758\ubbf8", "n_obs": 9, "min_obs_required": 20, "strategy_sharpe_annual": null, "strategy_total_return_pct": "-1.244833", "strategy_max_drawdown_pct": "2.588918", "strategy_calmar": null, "benchmark_sharpe_annual": null, "benchmark_total_return_pct": null, "benchmark_max_drawdown_pct": null, "benchmark_calmar": null, "excess_return_pct": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": null, "psr_vs_benchmark": null, "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 10, "legacy_snapshots_excluded": 0, "universe": ["SPY", "IEF", "GLD"]}
```

## 앵커드 판정 JSON (깊은 OOS + 짧은 forward 지속성, read-only)
```json
{"schema_version": "1.0", "method": "backtest_anchored", "verdict": "NO_EDGE", "reason": "OOS walk-forward \uc5e3\uc9c0 \ubbf8\ud655\uc815 \u2014 \uac15\uac74\ud55c \uc5e3\uc9c0 \uc5c6\uc74c: \uad6c\uac04 \uacfc\ubc18 \uc2e4\ud328(0/3); \ud3c9\uade0 \uc0e4\ud504\uac00 \ub2e8\uc21c \ubcf4\uc720 \uc774\ud558. \ub77c\uc774\ube0c \ubc30\ud3ec \uc815\ub2f9\ud654 \uc548 \ub428.", "oos_n_obs": 748, "oos_sharpe_annual": "1.941448", "oos_significance": "0.998745", "forward_n_obs": 9, "forward_mean_daily": null, "oos_mean_daily": "0.0006366898395721925", "consistency_z": null, "dsr_threshold": "0.95", "num_trials": 1, "mode": "paper", "dataset_version": "2023-02-05", "wf_segments": 3, "wf_verdict": "\uac15\uac74\ud55c \uc5e3\uc9c0 \uc5c6\uc74c: \uad6c\uac04 \uacfc\ubc18 \uc2e4\ud328(0/3); \ud3c9\uade0 \uc0e4\ud504\uac00 \ub2e8\uc21c \ubcf4\uc720 \uc774\ud558. \ub77c\uc774\ube0c \ubc30\ud3ec \uc815\ub2f9\ud654 \uc548 \ub428."}
```

## 정확 배포전략 수익 증거 JSON (read-only)
```json
{
  "candidate_id": "globalfixed-ensemble-3-6-9-12",
  "config_path": "deploy/global-trend-fixed-portfolio.toml",
  "trend_windows_months": [
    3,
    6,
    9,
    12
  ],
  "annual_cost_bps": 50,
  "split": {
    "development_start": "1971-02-01",
    "development_end": "2006-12-01",
    "holdout_start": "2007-01-01",
    "holdout_end": "2026-08-01",
    "overlap_months": 0
  },
  "development": {
    "n_months": 431,
    "cagr_pct": 12.01558,
    "sharpe": 1.854531,
    "max_drawdown_pct": 9.021682,
    "calmar": 1.331856
  },
  "holdout": {
    "n_months": 236,
    "cagr_pct": 8.713987,
    "sharpe": 1.841859,
    "max_drawdown_pct": 5.572914,
    "calmar": 1.563632
  },
  "benchmark_holdout": {
    "n_months": 236,
    "cagr_pct": 8.465965,
    "sharpe": 1.284444,
    "max_drawdown_pct": 17.268823,
    "calmar": 0.490246
  },
  "gates": [
    {
      "gate_id": "deployment_temporal_split",
      "passed": true,
      "candidate_value": 0.0,
      "benchmark_value": 0.0,
      "rule": "development and holdout periods do not overlap"
    },
    {
      "gate_id": "deployment_holdout_months",
      "passed": true,
      "candidate_value": 236.0,
      "benchmark_value": 120.0,
      "rule": "deployed candidate holdout contains at least 120 months"
    },
    {
      "gate_id": "deployment_annual_cost_bps",
      "passed": true,
      "candidate_value": 50.0,
      "benchmark_value": 50.0,
      "rule": "deployed candidate deducts at least 50bp annual cost drag"
    },
    {
      "gate_id": "deployment_cagr",
      "passed": true,
      "candidate_value": 8.713987,
      "benchmark_value": 8.465965,
      "rule": "cost-adjusted deployed candidate CAGR > benchmark CAGR"
    },
    {
      "gate_id": "deployment_sharpe",
      "passed": true,
      "candidate_value": 1.841859,
      "benchmark_value": 1.284444,
      "rule": "deployed candidate Sharpe > benchmark Sharpe"
    },
    {
      "gate_id": "deployment_drawdown",
      "passed": true,
      "candidate_value": 5.572914,
      "benchmark_value": 17.268823,
      "rule": "deployed candidate max drawdown <= 80% of benchmark"
    }
  ],
  "forward": {
    "track_key": "globalfixed",
    "present": true,
    "n_obs": 9,
    "psr_vs_benchmark": null,
    "dsr": null,
    "verdict": "INSUFFICIENT_DATA",
    "beats_benchmark_calmar": false,
    "significance_method": "paired_active_return_psr_v1",
    "threshold": 0.95,
    "passed": false
  },
  "historical_passed": true,
  "exploration_canary_ready": false,
  "entry_policy": {
    "min_forward_obs": 40,
    "min_forward_psr": 0.8,
    "requires_forward_calmar_superiority": true,
    "requires_hardened_canary_pass": true,
    "requires_strategy_fingerprint_match": true
  }
}
```

## 전략 공장 완전성 판정 JSON (read-only)
```json
{"candidate_count": 16, "checks": {"all_blocking_gates_pass": false, "all_candidates_complete": true, "audit_candidate_ids_unique": true, "audit_count_recomputed": true, "audit_fingerprints_unique": true, "audit_gate_counts_match": true, "audit_identity_complete": true, "audit_rows_complete": true, "audit_rows_present": true, "benchmark_execution_parity": false, "candidate_count_minimum": true, "current_family_is_audit_tail": true, "development_selection_match": false, "development_winner_recomputed": false, "factory_edge": false, "family_dsr_recomputed": false, "family_pbo": false, "family_pbo_recomputed": true, "family_statistics_inputs": true, "gate_rows_present": true, "historical_data_not_reused": true, "point_in_time_data": false, "prior_count_recomputed": true, "program_research_budget": true, "repository_calibration": true, "required_audit_gates": true, "research_canary_eligible": false, "research_family_audit_present": true, "research_family_audit_recomputed": true, "research_family_count_recomputed": true, "research_family_ids_recomputed": true, "research_live_parity": false, "selected_output_complete": false, "selected_psr_matches_record": false, "selected_psr_threshold": false, "selected_record_match": false, "standardized_statistics": false, "thresholds_frozen_before_results": true, "trial_count_recomputed": true, "trial_identities_unique": true, "trial_rows_complete": true, "trial_rows_present": true}, "complete_trial_count": 16, "contract_version": "calibrated-family-entry-v3.1", "eligible": false, "global_audit_trial_count": 800, "program_multiplicity": {"calibration_complete": true, "claimed_dsr": "0.964996", "claimed_pbo": "0.277778", "claimed_research_family_count": 20, "dsr_diagnostic": {"blocking": false, "passed": false, "threshold": "0.95"}, "family_calibrations": {"16": true, "64": true}, "maximum_research_families": 20, "method": "calibrated-family-risk-budget-v1", "per_family_false_acceptance_max": "0.01", "program_false_acceptance_bound": "0.20", "program_false_acceptance_budget": "0.2", "raw_bonferroni_diagnostic": {"adjusted_p": "1", "blocking": false, "global_trial_count": 800, "method": "bonferroni-global-fwer-v1", "passed": false, "raw_one_sided_p": "0.728464", "required_psr": "0.9999375", "threshold": "0.05"}, "recomputed_dsr": null, "recomputed_pbo": "0.277778", "research_family_count": 20, "selected_psr": "0.271536"}, "reasons": ["factory_edge", "research_canary_eligible", "all_blocking_gates_pass", "selected_output_complete", "selected_record_match", "development_selection_match", "development_winner_recomputed", "selected_psr_matches_record", "selected_psr_threshold", "point_in_time_data", "benchmark_execution_parity", "research_live_parity", "family_dsr_recomputed", "standardized_statistics", "family_pbo"], "selected_candidate_id": null, "selected_strategy_fingerprint": null}
```

## 운영 검증 캐너리 독립 판정 JSON (read-only)
```json
{
  "schema_version": "1.0",
  "eligible": true,
  "alpha_confirmed": false,
  "capital_fraction": 0.1,
  "max_rung": 1,
  "candidate_id": "globalfixed-ensemble-3-6-9-12",
  "strategy_fingerprint": "sha256:d4376129fa4181a92cd572638fa2940355687a617e0364c920b4fa8ceee1383e",
  "reasons": [],
  "checks": {
    "schema_version": true,
    "role": true,
    "route": true,
    "candidate_id": true,
    "code_commit_format": true,
    "code_commit": true,
    "strategy_fingerprint_format": true,
    "strategy_fingerprint": true,
    "live_strategy_fingerprint": true,
    "evidence_fresh": true,
    "raw_factors_aligned": true,
    "raw_factors_positive": true,
    "data_fingerprint": true,
    "candidate_snapshot_matches_raw": true,
    "benchmark_snapshot_matches_raw": true,
    "development_snapshot_present": true,
    "historical_candidate_preregistered": true,
    "historical_development_months": true,
    "historical_holdout_months": true,
    "historical_temporal_overlap": true,
    "historical_annual_cost_bps": true,
    "historical_positive_holdout_cagr": true,
    "historical_absolute_holdout_sharpe": true,
    "historical_absolute_holdout_drawdown": true,
    "historical_benchmark_sharpe_superiority": true,
    "historical_benchmark_drawdown_ratio": true,
    "decision_bounded": true,
    "safety_no_side_effect": true
  },
  "recomputed": {
    "candidate": {
      "n_months": 236,
      "cagr_pct": 8.713987,
      "sharpe": 1.841859,
      "max_drawdown_pct": 5.572914,
      "calmar": 1.563632
    },
    "benchmark": {
      "n_months": 236,
      "cagr_pct": 8.465965,
      "sharpe": 1.284444,
      "max_drawdown_pct": 17.268823,
      "calmar": 0.490246
    },
    "active_psr": 0.553141,
    "cost_sensitivity": {
      "100": {
        "candidate_sharpe": 1.733081,
        "active_sharpe": -0.092379
      },
      "150": {
        "candidate_sharpe": 1.62371,
        "active_sharpe": -0.215302
      }
    }
  }
}
```

## 연구 단 1 구현 가능성 미리보기 (read-only, 주문 0건)
```json
{"portfolio_id": "global-trend-fixed", "mode": "dry-run", "account_wide": true, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": "934.27", "required_cash_usd": "106.18", "planned_buy_notional_usd": "105.13", "planned_sell_notional_usd": "0.00", "target_weights": {"SCHX": "0.333334", "IAUM": "0.166666"}, "signal_target_weights": {"SPY": "0.333334", "GLD": "0.166666"}, "execution_symbol_map": {"SPY": "SCHX", "IEF": "SPTI", "GLD": "IAUM"}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "143.0", "investable_usd": "141.570", "active_target_count": 2, "funded_target_count": 2, "funded_target_ratio": "1", "whole_share_eligible_target_count": 1, "funded_whole_share_target_count": 1, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {"IAUM": {"target_notional_usd": "23.594905620", "one_share_price_usd": "44.2000"}}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"SCHX": "0.333334", "IAUM": "0.166666"}, "holdings": {}, "prices": {"IAUM": "44.2000", "SCHX": "30.3600"}, "order_prices": {"IAUM": "44.29", "SCHX": "30.42"}, "planned_orders": [{"symbol": "IAUM", "side": "BUY", "qty": 1}, {"symbol": "SCHX", "side": "BUY", "qty": 2}], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "10.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"SCHX": 2, "IAUM": 1}, "projected_weights": {"SCHX": "0.4246153846153846153846153846", "IAUM": "0.3090909090909090909090909091"}, "l1_weight_error": "0.2387062937062937062937062937", "max_leg_weight_error": "0.1440915690909090909090909091", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "results": [{"symbol": "IAUM", "side": "BUY", "requested_qty": 1, "routed_qty": 1, "limit_price_usd": "44.29", "state": "DRY_RUN", "gate": null, "reason": null}, {"symbol": "SCHX", "side": "BUY", "requested_qty": 2, "routed_qty": 2, "limit_price_usd": "30.42", "state": "DRY_RUN", "gate": null, "reason": null}], "withheld_orders": [{"symbol": "ORANY", "side": "SELL", "requested_qty": 28, "reason": "unmanaged_holding"}]}
```

## 실행 대체 ETF 동등성 감사 (KIS read-only, 주문 0건)
```json
{"checks": {"all_pairs_passed": true, "mapping_exact": true, "pair_count": true}, "contract": {"lookback_sessions": 252, "max_annualized_return_gap": 0.03, "max_annualized_tracking_error": 0.06, "max_evidence_age_hours": 36.0, "max_market_data_age_days": 7, "min_common_sessions": 252, "min_median_dollar_volume_usd": "1000000", "min_return_correlation": 0.95}, "dataset_version": "sqlite-price_bars-1d", "evidence_digest": "sha256:c5bc015b2db4804e76571e41f824f960a74b43032252b7c14449f99c9cfbcde1", "observed_at_utc": "2026-09-05T02:10:40.499546Z", "pairs": [{"annualized_return_gap": 0.004208311269351839, "annualized_tracking_error": 0.008187170707769385, "checks": {"annualized_return_gap": true, "annualized_tracking_error": true, "common_sessions": true, "execution_liquidity": true, "freshness": true, "latest_session_aligned": true, "return_correlation": true}, "common_sessions": 252, "execution_latest_session": "2026-09-04", "execution_symbol": "IAUM", "first_session": "2025-09-05", "last_session": "2026-09-04", "median_execution_dollar_volume_usd": "120169570.6700", "passed": true, "return_correlation": 0.9996593372585979, "signal_latest_session": "2026-09-04", "signal_symbol": "GLD"}, {"annualized_return_gap": 0.008911375593547488, "annualized_tracking_error": 0.01541699094753887, "checks": {"annualized_return_gap": true, "annualized_tracking_error": true, "common_sessions": true, "execution_liquidity": true, "freshness": true, "latest_session_aligned": true, "return_correlation": true}, "common_sessions": 252, "execution_latest_session": "2026-09-04", "execution_symbol": "SPTI", "first_session": "2025-09-05", "last_session": "2026-09-04", "median_execution_dollar_volume_usd": "50595477.2511", "passed": true, "return_correlation": 0.9777398740074984, "signal_latest_session": "2026-09-04", "signal_symbol": "IEF"}, {"annualized_return_gap": 0.006630246416671648, "annualized_tracking_error": 0.010052200860913539, "checks": {"annualized_return_gap": true, "annualized_tracking_error": true, "common_sessions": true, "execution_liquidity": true, "freshness": true, "latest_session_aligned": true, "return_correlation": true}, "common_sessions": 252, "execution_latest_session": "2026-09-04", "execution_symbol": "SCHX", "first_session": "2025-09-05", "last_session": "2026-09-04", "median_execution_dollar_volume_usd": "396865518.7673", "passed": true, "return_correlation": 0.9969513096870555, "signal_latest_session": "2026-09-04", "signal_symbol": "SPY"}], "passed": true, "schema_version": "1.0", "symbol_map": {"GLD": "IAUM", "IEF": "SPTI", "SPY": "SCHX"}}
```

## 탐색 진입 hardened canary JSON (격리, 주문 0건)
```json
{"schema_version": "1.1", "outcome": "passed", "verdict": "PASS", "tier": "L3", "failing_metrics": [], "candidate_drawdown_pct": 1.020264, "shock_violations": 0, "audit_integrity_count": 0, "audit_integrity_holes": [], "fuzz_counterexamples": 0, "window_gate_rejections": 0, "resolved_shock_dates": ["2024-08-05", "2026-06-18"], "skipped_shock_dates": ["2020-03-12", "2020-04-20"], "portfolio_id": "global-trend-fixed", "window_start": "2026-07-06", "window_end": "2026-09-04", "window_common_session_count": 45}
```

## 라이브 실적 JSON (현재 단 진입 이후, read-only)
```json
{"schema_version": "1.0", "mode": "live", "snapshot_count": 2, "first_at_utc": "2026-09-05T01:46:21.256Z", "last_at_utc": "2026-09-05T01:50:31.076Z", "starting_nav_usd": "143.0", "current_nav_usd": "143.0", "absolute_change_usd": "0.0", "total_return_pct": "0.000000", "max_drawdown_pct": "0.000000", "period_days": "0.0028914351851851853", "cagr_pct": "0.0"}
```

## 라이브 전략 성과 JSON (첫 체결 수, read-only)
```json
{
  "schema_version": "1.2",
  "mode": "live",
  "period": {
    "since_utc": "1970-01-01T00:00:00.000Z",
    "until_utc": "2026-09-05T02:10:55.851Z"
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
```
