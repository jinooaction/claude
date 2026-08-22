# 자본 사다리 게이트 — 최신 실행 (스펙 050; 스펙 049 승계)

헌법 X.4 v7.0.0. 단0=0% → 단1=20% 탐색 → 단2=25% → 단3=50% → 단4=100%
(실계좌 NAV 대비). 내려가는 건 낙폭 하나로 즉시, 올라가는 건 세 증거 전부.
판정 계산은 read-only — 서버 상태 무변경, 주문 0건.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| timestamp_utc | 2026-08-22T11:33:45Z |
| trigger | workflow_dispatch |
| **결정(action)** | **WAIT_EDGE** |
| 단(rung) | 0 → 0 |
| 자본 | $? (실계좌 NAV $1457.59000000) |
| 엣지 출처 | none |
| 센티넬 변경 | false |
| PR | (없음 — 변경 없음) |
| 머지 | n/a |

## 의미

⏳ **배치 보류** — 아직 forward EDGE_CONFIRMED 아님(더 쌓여야 함, 정상). 돈 0 이동.

- 사유: 단 0 + forward 판정='NO_EDGE', 탐색 캐너리='EXPLORATION_CANARY_WAIT' — 진입 증거 미충족. 배치 보류.

## 결정 JSON
```json
{"schema_version": "1.0", "action": "WAIT_EDGE", "current_rung": 0, "target_rung": 0, "reason": "\ub2e8 0 + forward \ud310\uc815='NO_EDGE', \ud0d0\uc0c9 \uce90\ub108\ub9ac='EXPLORATION_CANARY_WAIT' \u2014 \uc9c4\uc785 \uc99d\uac70 \ubbf8\ucda9\uc871. \ubc30\uce58 \ubcf4\ub958.", "account_nav_usd": "1457.59000000", "target_capital_usd": null, "live_dd_pct": null, "live_obs": 2, "edge_source": "none", "exploration_verdict": {"verdict": "EXPLORATION_CANARY_WAIT", "candidate_id": "globalfixed-ensemble-3-6-9-12", "historical_forward_ready": false, "hardened_canary_pass": true}}
```

## forward 판정 JSON (검증된 앙상블, read-only)
```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "PSR 0.601730 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 11.864606 > \ubca4\uce58 3.929082 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 47, "min_obs_required": 20, "strategy_sharpe_annual": "1.820414", "strategy_total_return_pct": "18.919143", "strategy_max_drawdown_pct": "12.913037", "strategy_calmar": "11.864606", "benchmark_sharpe_annual": "1.244457", "benchmark_total_return_pct": "2.215677", "benchmark_max_drawdown_pct": "3.173331", "benchmark_calmar": "3.929082", "excess_return_pct": "16.703466", "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.601730", "dsr": null, "num_trials": 1, "min_track_record_obs": "1873.213990", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 48, "legacy_snapshots_excluded": 0, "universe": ["SPY", "IEF", "GLD"]}
```

## 앵커드 판정 JSON (깊은 OOS + 짧은 forward 지속성, read-only)
```json
{"schema_version": "1.0", "method": "backtest_anchored", "verdict": "NO_EDGE", "reason": "OOS walk-forward \uc5e3\uc9c0 \ubbf8\ud655\uc815 \u2014 \uac15\uac74\ud55c \uc5e3\uc9c0 \uc5c6\uc74c: \uad6c\uac04 \uacfc\ubc18 \uc2e4\ud328(1/3); \ud3c9\uade0 \uc0e4\ud504\uac00 \ub2e8\uc21c \ubcf4\uc720 \uc774\ud558. \ub77c\uc774\ube0c \ubc30\ud3ec \uc815\ub2f9\ud654 \uc548 \ub428.", "oos_n_obs": 749, "oos_sharpe_annual": "1.852943", "oos_significance": "0.998968", "forward_n_obs": 47, "forward_mean_daily": null, "oos_mean_daily": "0.0005120520694259013", "consistency_z": null, "dsr_threshold": "0.95", "num_trials": 1, "mode": "paper", "dataset_version": "2022-11-29", "wf_segments": 3, "wf_verdict": "\uac15\uac74\ud55c \uc5e3\uc9c0 \uc5c6\uc74c: \uad6c\uac04 \uacfc\ubc18 \uc2e4\ud328(1/3); \ud3c9\uade0 \uc0e4\ud504\uac00 \ub2e8\uc21c \ubcf4\uc720 \uc774\ud558. \ub77c\uc774\ube0c \ubc30\ud3ec \uc815\ub2f9\ud654 \uc548 \ub428."}
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
    "holdout_end": "2026-07-01",
    "overlap_months": 0
  },
  "development": {
    "n_months": 431,
    "cagr_pct": 12.003216,
    "sharpe": 1.851647,
    "max_drawdown_pct": 9.021682,
    "calmar": 1.330485
  },
  "holdout": {
    "n_months": 235,
    "cagr_pct": 8.682649,
    "sharpe": 1.831434,
    "max_drawdown_pct": 5.572914,
    "calmar": 1.558009
  },
  "benchmark_holdout": {
    "n_months": 235,
    "cagr_pct": 8.291414,
    "sharpe": 1.264685,
    "max_drawdown_pct": 17.268823,
    "calmar": 0.480138
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
      "candidate_value": 235.0,
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
      "candidate_value": 8.682649,
      "benchmark_value": 8.291414,
      "rule": "cost-adjusted deployed candidate CAGR > benchmark CAGR"
    },
    {
      "gate_id": "deployment_sharpe",
      "passed": true,
      "candidate_value": 1.831434,
      "benchmark_value": 1.264685,
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
    "n_obs": 47,
    "psr_vs_benchmark": 0.60173,
    "dsr": null,
    "verdict": "NO_EDGE",
    "beats_benchmark_calmar": true,
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

## 탐색 진입 hardened canary JSON (격리, 주문 0건)
```json
{"schema_version": "1.0", "outcome": "passed", "verdict": "PASS", "tier": "L3", "failing_metrics": [], "candidate_drawdown_pct": 1.168899, "shock_violations": 0, "audit_integrity_count": 0, "fuzz_counterexamples": 0, "window_gate_rejections": 0, "resolved_shock_dates": ["2024-08-05", "2026-06-18"], "skipped_shock_dates": ["2020-03-12", "2020-04-20"], "portfolio_id": "global-trend-fixed", "window_start": "2026-06-18", "window_end": "2026-08-21"}
```

## 라이브 실적 JSON (현재 단 진입 이후, read-only)
```json
{"schema_version": "1.0", "mode": "live", "snapshot_count": 2, "first_at_utc": "2026-08-22T11:30:59.270Z", "last_at_utc": "2026-08-22T11:31:31.516Z", "starting_nav_usd": "0.0", "current_nav_usd": "0.0", "absolute_change_usd": "0.0", "total_return_pct": null, "max_drawdown_pct": null, "period_days": "0.00037321759259259263", "cagr_pct": null}
```

## 라이브 전략 성과 JSON (첫 체결 수, read-only)
```json
{}
```
