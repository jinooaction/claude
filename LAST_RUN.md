# 레짐 층화 — 배포 전략은 어떤 거시 레짐에서 벌고 잃는가 (최신 실행)

> 거시 레짐 타임라인(공개 데이터 채널)의 d일 라벨에 *배포된 전략*의 d+1
> 거래일 수익률을 붙인 전망적 층화(미래 누출 차단). 수익률은 인스턴스의
> 현재 KIS 일봉을 라이브와 같은 신호·게이트 경로로 리플레이한 일별 자본
> 곡선(최근 ~3년) — 단일 잣대(헌법 X.2). RISK_OFF/CAUTION 의 낙폭·샤프가
> 전체 대비 크게 나쁘면 그 레짐이 전략의 구조적 약점이다(예: 인플레
> regime 의 채권 분산 약화). 연구 전용 — 라이브 신호 아님, 돈 0 이동.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | 758dda2534af38f444ac75361295fb49b489e234 |
| trigger | schedule |
| timestamp_utc | 2026-08-08T00:00:10Z |
| 타임라인 prep exit | 0 |
| GLOBAL-TREND ssh_exit | 0 |
| GLOBAL-TREND-WIDE ssh_exit | 0 |

## GLOBAL-TREND (3자산 SPY·IEF·GLD — 라이브 지정 전략)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-064318eb19bb", "dataset_version": "2697101eb323d8b264a0bd1a15e430130b52070d300856d71ab2b09740a61366", "date_start": "2023-08-07", "date_end": "2026-08-07", "portfolio_id": "global-trend", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 11, "fills": 11, "gate_rejections": 0, "total_return_pct": "39.573962", "max_drawdown_pct": "11.996352", "sharpe_ratio": "1.254146", "sortino_ratio": "1.734892", "turnover_ratio": "2.465913", "commission_usd": "90.310985", "final_equity_usd": "16748.262194", "benchmark_total_return_pct": "68.542386", "benchmark_max_drawdown_pct": "11.794702", "benchmark_sharpe_ratio": "1.569916", "excess_return_pct": "-28.968424"}
regime stratify: 수익률 753일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  433  누적     9.32%  샤프   0.65  최대낙폭 7.95%
  RISK_OFF     n=    7  누적    -0.02%
  RISK_ON      n=  313  누적    27.70%  샤프   1.98  최대낙폭 7.60%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 753,
  "by_label": {
    "CAUTION": {
      "n_days": 433,
      "total_return_pct": "9.32",
      "mean_daily_pct": "0.0220",
      "worst_day_pct": "-2.68",
      "best_day_pct": "2.08",
      "max_drawdown_pct": "7.95",
      "ann_vol_pct": "8.48",
      "ann_return_pct": "5.32",
      "sharpe": "0.65"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "-0.02",
      "mean_daily_pct": "-0.0014",
      "worst_day_pct": "-0.78",
      "best_day_pct": "1.01",
      "max_drawdown_pct": "0.78",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "27.70",
      "mean_daily_pct": "0.0802",
      "worst_day_pct": "-4.90",
      "best_day_pct": "2.73",
      "max_drawdown_pct": "7.60",
      "ann_vol_pct": "10.21",
      "ann_return_pct": "21.76",
      "sharpe": "1.98"
    }
  },
  "all": {
    "n_days": 753,
    "total_return_pct": "39.57",
    "mean_daily_pct": "0.0460",
    "worst_day_pct": "-4.90",
    "best_day_pct": "2.73",
    "max_drawdown_pct": "12.00",
    "ann_vol_pct": "9.24",
    "ann_return_pct": "11.80",
    "sharpe": "1.25"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```

## GLOBAL-TREND-WIDE (11 슬리브 — 계획 ③ 후보)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-af3062d34dc3", "dataset_version": "ebeab4ed52e2fa3c34ea18a8991805a15f7b4bd63a297bf9b23f1496cd5eb649", "date_start": "2023-08-07", "date_end": "2026-08-07", "portfolio_id": "global-trend-wide", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 61, "fills": 61, "gate_rejections": 0, "total_return_pct": "21.893871", "max_drawdown_pct": "5.147414", "sharpe_ratio": "1.250841", "sortino_ratio": "1.755474", "turnover_ratio": "3.424718", "commission_usd": "112.209495", "final_equity_usd": "14619.518902", "benchmark_total_return_pct": "43.382995", "benchmark_max_drawdown_pct": "7.594365", "benchmark_sharpe_ratio": "1.456929", "excess_return_pct": "-21.489124"}
regime stratify: 수익률 753일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  433  누적     6.22%  샤프   0.68  최대낙폭 4.22%
  RISK_OFF     n=    7  누적     0.23%
  RISK_ON      n=  313  누적    14.49%  샤프   2.03  최대낙폭 4.37%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 753,
  "by_label": {
    "CAUTION": {
      "n_days": 433,
      "total_return_pct": "6.22",
      "mean_daily_pct": "0.0145",
      "worst_day_pct": "-1.70",
      "best_day_pct": "1.67",
      "max_drawdown_pct": "4.22",
      "ann_vol_pct": "5.42",
      "ann_return_pct": "3.57",
      "sharpe": "0.68"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.23",
      "mean_daily_pct": "0.0330",
      "worst_day_pct": "-0.21",
      "best_day_pct": "0.55",
      "max_drawdown_pct": "0.30",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "14.49",
      "mean_daily_pct": "0.0438",
      "worst_day_pct": "-2.20",
      "best_day_pct": "1.11",
      "max_drawdown_pct": "4.37",
      "ann_vol_pct": "5.43",
      "ann_return_pct": "11.51",
      "sharpe": "2.03"
    }
  },
  "all": {
    "n_days": 753,
    "total_return_pct": "21.89",
    "mean_daily_pct": "0.0269",
    "worst_day_pct": "-2.20",
    "best_day_pct": "1.67",
    "max_drawdown_pct": "5.15",
    "ann_vol_pct": "5.41",
    "ann_return_pct": "6.85",
    "sharpe": "1.25"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```
