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
| commit | aeb175bc1894684d7467adfb13e80b08a658a093 |
| trigger | schedule |
| timestamp_utc | 2026-09-12T01:24:05Z |
| 타임라인 prep exit | 0 |
| GLOBAL-TREND ssh_exit | 0 |
| GLOBAL-TREND-WIDE ssh_exit | 0 |

## GLOBAL-TREND (3자산 SPY·IEF·GLD — 라이브 지정 전략)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-ddad92040865", "dataset_version": "62d2fbe8ef37910e8382cf4ee57a9cf1ae6b69c02ceb780c2faee2c62c64f1d3", "date_start": "2023-09-12", "date_end": "2026-09-12", "portfolio_id": "global-trend", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 14, "fills": 14, "gate_rejections": 0, "total_return_pct": "42.799741", "max_drawdown_pct": "12.200663", "sharpe_ratio": "1.259508", "sortino_ratio": "1.752745", "turnover_ratio": "2.606113", "commission_usd": "98.085942", "final_equity_usd": "17122.213107", "benchmark_total_return_pct": "68.417655", "benchmark_max_drawdown_pct": "11.717724", "benchmark_sharpe_ratio": "1.566648", "excess_return_pct": "-25.617914"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적    10.92%  샤프   0.70  최대낙폭 8.20%
  RISK_OFF     n=    7  누적     0.26%
  RISK_ON      n=  313  누적    28.41%  샤프   1.94  최대낙폭 8.25%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "10.92",
      "mean_daily_pct": "0.0257",
      "worst_day_pct": "-2.77",
      "best_day_pct": "3.79",
      "max_drawdown_pct": "8.20",
      "ann_vol_pct": "9.26",
      "ann_return_pct": "6.23",
      "sharpe": "0.70"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.26",
      "mean_daily_pct": "0.0380",
      "worst_day_pct": "-0.77",
      "best_day_pct": "1.04",
      "max_drawdown_pct": "0.77",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "28.41",
      "mean_daily_pct": "0.0822",
      "worst_day_pct": "-5.06",
      "best_day_pct": "2.75",
      "max_drawdown_pct": "8.25",
      "ann_vol_pct": "10.68",
      "ann_return_pct": "22.30",
      "sharpe": "1.94"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "42.80",
    "mean_daily_pct": "0.0493",
    "worst_day_pct": "-5.06",
    "best_day_pct": "3.79",
    "max_drawdown_pct": "12.20",
    "ann_vol_pct": "9.87",
    "ann_return_pct": "12.68",
    "sharpe": "1.26"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```

## GLOBAL-TREND-WIDE (11 슬리브 — 계획 ③ 후보)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-a5c4fd275bcd", "dataset_version": "8a0bd9994d5f9a3ef19671dca4e9c2f9e93b88c5b04ba607fd07dfd596be8f19", "date_start": "2023-09-12", "date_end": "2026-09-12", "portfolio_id": "global-trend-wide", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 61, "fills": 61, "gate_rejections": 0, "total_return_pct": "25.423830", "max_drawdown_pct": "5.981336", "sharpe_ratio": "1.290852", "sortino_ratio": "1.833894", "turnover_ratio": "3.422027", "commission_usd": "114.591141", "final_equity_usd": "15035.431457", "benchmark_total_return_pct": "45.270704", "benchmark_max_drawdown_pct": "7.512891", "benchmark_sharpe_ratio": "1.515281", "excess_return_pct": "-19.846874"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적     9.67%  샤프   0.89  최대낙폭 5.43%
  RISK_OFF     n=    7  누적     0.63%
  RISK_ON      n=  313  누적    13.64%  샤프   1.84  최대낙폭 3.78%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "9.67",
      "mean_daily_pct": "0.0222",
      "worst_day_pct": "-1.82",
      "best_day_pct": "3.12",
      "max_drawdown_pct": "5.43",
      "ann_vol_pct": "6.27",
      "ann_return_pct": "5.53",
      "sharpe": "0.89"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.63",
      "mean_daily_pct": "0.0907",
      "worst_day_pct": "-0.22",
      "best_day_pct": "0.78",
      "max_drawdown_pct": "0.22",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "13.64",
      "mean_daily_pct": "0.0415",
      "worst_day_pct": "-2.19",
      "best_day_pct": "1.09",
      "max_drawdown_pct": "3.78",
      "ann_vol_pct": "5.68",
      "ann_return_pct": "10.84",
      "sharpe": "1.84"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "25.42",
    "mean_daily_pct": "0.0308",
    "worst_day_pct": "-2.19",
    "best_day_pct": "3.12",
    "max_drawdown_pct": "5.98",
    "ann_vol_pct": "6.02",
    "ann_return_pct": "7.89",
    "sharpe": "1.29"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```
