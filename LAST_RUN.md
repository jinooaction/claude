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
| commit | 87c00951e99ecccb42750a40fe351ab48786b0f5 |
| trigger | schedule |
| timestamp_utc | 2026-09-05T01:18:10Z |
| 타임라인 prep exit | 0 |
| GLOBAL-TREND ssh_exit | 0 |
| GLOBAL-TREND-WIDE ssh_exit | 0 |

## GLOBAL-TREND (3자산 SPY·IEF·GLD — 라이브 지정 전략)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-4f85abfcbba7", "dataset_version": "14f1113d3df562a38c56f955751f70a99b25f3255878a278ac4ce7705ca48ddd", "date_start": "2023-09-05", "date_end": "2026-09-05", "portfolio_id": "global-trend", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 14, "fills": 12, "gate_rejections": 2, "total_return_pct": "38.773658", "max_drawdown_pct": "11.297996", "sharpe_ratio": "1.229216", "sortino_ratio": "1.672800", "turnover_ratio": "2.779655", "commission_usd": "101.919535", "final_equity_usd": "16633.524632", "benchmark_total_return_pct": "70.391458", "benchmark_max_drawdown_pct": "11.744926", "benchmark_sharpe_ratio": "1.599170", "excess_return_pct": "-31.617800"}
regime stratify: 수익률 753일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  433  누적     8.32%  샤프   0.61  최대낙폭 7.28%
  RISK_OFF     n=    7  누적     0.39%
  RISK_ON      n=  313  누적    27.62%  샤프   1.90  최대낙폭 7.89%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 753,
  "by_label": {
    "CAUTION": {
      "n_days": 433,
      "total_return_pct": "8.32",
      "mean_daily_pct": "0.0198",
      "worst_day_pct": "-2.67",
      "best_day_pct": "1.95",
      "max_drawdown_pct": "7.28",
      "ann_vol_pct": "8.17",
      "ann_return_pct": "4.76",
      "sharpe": "0.61"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.39",
      "mean_daily_pct": "0.0567",
      "worst_day_pct": "-0.83",
      "best_day_pct": "1.04",
      "max_drawdown_pct": "0.83",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "27.62",
      "mean_daily_pct": "0.0802",
      "worst_day_pct": "-4.97",
      "best_day_pct": "2.79",
      "max_drawdown_pct": "7.89",
      "ann_vol_pct": "10.62",
      "ann_return_pct": "21.69",
      "sharpe": "1.90"
    }
  },
  "all": {
    "n_days": 753,
    "total_return_pct": "38.77",
    "mean_daily_pct": "0.0452",
    "worst_day_pct": "-4.97",
    "best_day_pct": "2.79",
    "max_drawdown_pct": "11.30",
    "ann_vol_pct": "9.27",
    "ann_return_pct": "11.59",
    "sharpe": "1.23"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```

## GLOBAL-TREND-WIDE (11 슬리브 — 계획 ③ 후보)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-38d2c2ae8693", "dataset_version": "bfdc82af6b2efbb6797dd4652b24377152868c5241434ac0933674db49c1900c", "date_start": "2023-09-05", "date_end": "2026-09-05", "portfolio_id": "global-trend-wide", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 57, "fills": 57, "gate_rejections": 0, "total_return_pct": "25.035994", "max_drawdown_pct": "4.770450", "sharpe_ratio": "1.370458", "sortino_ratio": "1.877202", "turnover_ratio": "3.583577", "commission_usd": "119.043761", "final_equity_usd": "14990.531178", "benchmark_total_return_pct": "46.291938", "benchmark_max_drawdown_pct": "7.532967", "benchmark_sharpe_ratio": "1.536727", "excess_return_pct": "-21.255944"}
regime stratify: 수익률 753일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  433  누적     7.85%  샤프   0.84  최대낙폭 4.64%
  RISK_OFF     n=    7  누적     0.58%
  RISK_ON      n=  313  누적    15.27%  샤프   2.01  최대낙폭 3.87%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 753,
  "by_label": {
    "CAUTION": {
      "n_days": 433,
      "total_return_pct": "7.85",
      "mean_daily_pct": "0.0180",
      "worst_day_pct": "-1.78",
      "best_day_pct": "1.27",
      "max_drawdown_pct": "4.64",
      "ann_vol_pct": "5.43",
      "ann_return_pct": "4.49",
      "sharpe": "0.84"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.58",
      "mean_daily_pct": "0.0835",
      "worst_day_pct": "-0.21",
      "best_day_pct": "0.75",
      "max_drawdown_pct": "0.25",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "15.27",
      "mean_daily_pct": "0.0461",
      "worst_day_pct": "-2.24",
      "best_day_pct": "1.12",
      "max_drawdown_pct": "3.87",
      "ann_vol_pct": "5.77",
      "ann_return_pct": "12.12",
      "sharpe": "2.01"
    }
  },
  "all": {
    "n_days": 753,
    "total_return_pct": "25.04",
    "mean_daily_pct": "0.0303",
    "worst_day_pct": "-2.24",
    "best_day_pct": "1.27",
    "max_drawdown_pct": "4.77",
    "ann_vol_pct": "5.57",
    "ann_return_pct": "7.76",
    "sharpe": "1.37"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```
