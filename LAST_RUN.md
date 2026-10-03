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
| commit | 9d70758cd505844dc673291ba98651131be670b7 |
| trigger | schedule |
| timestamp_utc | 2026-10-03T02:14:53Z |
| 타임라인 prep exit | 0 |
| GLOBAL-TREND ssh_exit | 0 |
| GLOBAL-TREND-WIDE ssh_exit | 0 |

## GLOBAL-TREND (3자산 SPY·IEF·GLD — 라이브 지정 전략)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-e591ea96715b", "dataset_version": "a941fe07246addf584c8e517214c8e0e51b53b0921c3cc0ebafe9cdff5554b7b", "date_start": "2023-10-03", "date_end": "2026-10-03", "portfolio_id": "global-trend", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 10, "fills": 10, "gate_rejections": 0, "total_return_pct": "40.195376", "max_drawdown_pct": "11.880732", "sharpe_ratio": "1.279807", "sortino_ratio": "1.747933", "turnover_ratio": "2.231729", "commission_usd": "82.727195", "final_equity_usd": "16816.585098", "benchmark_total_return_pct": "70.835323", "benchmark_max_drawdown_pct": "11.694660", "benchmark_sharpe_ratio": "1.607474", "excess_return_pct": "-30.639947"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적    10.21%  샤프   0.73  최대낙폭 8.08%
  RISK_OFF     n=    7  누적    -0.02%
  RISK_ON      n=  313  누적    27.23%  샤프   1.92  최대낙폭 8.21%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "10.21",
      "mean_daily_pct": "0.0239",
      "worst_day_pct": "-2.67",
      "best_day_pct": "2.15",
      "max_drawdown_pct": "8.08",
      "ann_vol_pct": "8.24",
      "ann_return_pct": "5.84",
      "sharpe": "0.73"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "-0.02",
      "mean_daily_pct": "-0.0015",
      "worst_day_pct": "-0.77",
      "best_day_pct": "0.77",
      "max_drawdown_pct": "0.77",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "27.23",
      "mean_daily_pct": "0.0791",
      "worst_day_pct": "-4.95",
      "best_day_pct": "2.69",
      "max_drawdown_pct": "8.21",
      "ann_vol_pct": "10.37",
      "ann_return_pct": "21.39",
      "sharpe": "1.92"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "40.20",
    "mean_daily_pct": "0.0466",
    "worst_day_pct": "-4.95",
    "best_day_pct": "2.69",
    "max_drawdown_pct": "11.88",
    "ann_vol_pct": "9.18",
    "ann_return_pct": "11.99",
    "sharpe": "1.28"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```

## GLOBAL-TREND-WIDE (11 슬리브 — 계획 ③ 후보)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-8593a08be5b4", "dataset_version": "4642b8d0ed230ab43d7910ad419f0abf3f26b13ec1ba1b90ad7fc27a5c8e63b4", "date_start": "2023-10-03", "date_end": "2026-10-03", "portfolio_id": "global-trend-wide", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 49, "fills": 49, "gate_rejections": 0, "total_return_pct": "23.992880", "max_drawdown_pct": "4.699881", "sharpe_ratio": "1.339553", "sortino_ratio": "1.832448", "turnover_ratio": "2.860877", "commission_usd": "95.421409", "final_equity_usd": "14865.958109", "benchmark_total_return_pct": "52.492822", "benchmark_max_drawdown_pct": "8.226727", "benchmark_sharpe_ratio": "1.620322", "excess_return_pct": "-28.499942"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적     7.24%  샤프   0.77  최대낙폭 4.60%
  RISK_OFF     n=    7  누적     0.48%
  RISK_ON      n=  313  누적    15.07%  샤프   2.07  최대낙폭 3.58%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "7.24",
      "mean_daily_pct": "0.0168",
      "worst_day_pct": "-1.80",
      "best_day_pct": "1.19",
      "max_drawdown_pct": "4.60",
      "ann_vol_pct": "5.47",
      "ann_return_pct": "4.16",
      "sharpe": "0.77"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.48",
      "mean_daily_pct": "0.0693",
      "worst_day_pct": "-0.24",
      "best_day_pct": "0.66",
      "max_drawdown_pct": "0.24",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "15.07",
      "mean_daily_pct": "0.0455",
      "worst_day_pct": "-2.21",
      "best_day_pct": "1.06",
      "max_drawdown_pct": "3.58",
      "ann_vol_pct": "5.54",
      "ann_return_pct": "11.96",
      "sharpe": "2.07"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "23.99",
    "mean_daily_pct": "0.0292",
    "worst_day_pct": "-2.21",
    "best_day_pct": "1.19",
    "max_drawdown_pct": "4.70",
    "ann_vol_pct": "5.49",
    "ann_return_pct": "7.47",
    "sharpe": "1.34"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```
