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
| commit | d244c62f12d975e17e9d2f9af4952bf4dc3ec17f |
| trigger | schedule |
| timestamp_utc | 2026-09-15T01:46:11Z |
| 타임라인 prep exit | 0 |
| GLOBAL-TREND ssh_exit | 0 |
| GLOBAL-TREND-WIDE ssh_exit | 0 |

## GLOBAL-TREND (3자산 SPY·IEF·GLD — 라이브 지정 전략)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-9f3c5b5cce05", "dataset_version": "475eed9e18d92fe76400528143dcdbe7501086d5d298d980888697cbd0d38872", "date_start": "2023-09-15", "date_end": "2026-09-15", "portfolio_id": "global-trend", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 14, "fills": 14, "gate_rejections": 0, "total_return_pct": "15.405349", "max_drawdown_pct": "4.004284", "sharpe_ratio": "1.137807", "sortino_ratio": "1.631539", "turnover_ratio": "2.620816", "commission_usd": "86.296300", "final_equity_usd": "13838.747726", "benchmark_total_return_pct": "67.101117", "benchmark_max_drawdown_pct": "11.714005", "benchmark_sharpe_ratio": "1.545400", "excess_return_pct": "-51.695768"}
regime stratify: 수익률 750일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  430  누적     6.94%  샤프   0.92  최대낙폭 3.68%
  RISK_OFF     n=    7  누적    -0.20%
  RISK_ON      n=  313  누적     8.13%  샤프   1.51  최대낙폭 3.35%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 750,
  "by_label": {
    "CAUTION": {
      "n_days": 430,
      "total_return_pct": "6.94",
      "mean_daily_pct": "0.0160",
      "worst_day_pct": "-1.31",
      "best_day_pct": "2.24",
      "max_drawdown_pct": "3.68",
      "ann_vol_pct": "4.39",
      "ann_return_pct": "4.01",
      "sharpe": "0.92"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "-0.20",
      "mean_daily_pct": "-0.0279",
      "worst_day_pct": "-0.29",
      "best_day_pct": "0.44",
      "max_drawdown_pct": "0.56",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "8.13",
      "mean_daily_pct": "0.0253",
      "worst_day_pct": "-1.49",
      "best_day_pct": "0.89",
      "max_drawdown_pct": "3.35",
      "ann_vol_pct": "4.21",
      "ann_return_pct": "6.49",
      "sharpe": "1.51"
    }
  },
  "all": {
    "n_days": 750,
    "total_return_pct": "15.41",
    "mean_daily_pct": "0.0195",
    "worst_day_pct": "-1.49",
    "best_day_pct": "2.24",
    "max_drawdown_pct": "4.00",
    "ann_vol_pct": "4.31",
    "ann_return_pct": "4.93",
    "sharpe": "1.14"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```

## GLOBAL-TREND-WIDE (11 슬리브 — 계획 ③ 후보)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-d146ad2ce59d", "dataset_version": "b477ada39f7a7f026536a7e9493d04a90931a078f4985fdaa1c48394b5411d0a", "date_start": "2023-09-15", "date_end": "2026-09-15", "portfolio_id": "global-trend-wide", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 64, "fills": 64, "gate_rejections": 0, "total_return_pct": "15.529049", "max_drawdown_pct": "5.276650", "sharpe_ratio": "1.144304", "sortino_ratio": "1.615232", "turnover_ratio": "3.373995", "commission_usd": "107.301628", "final_equity_usd": "13849.306264", "benchmark_total_return_pct": "44.145357", "benchmark_max_drawdown_pct": "7.514856", "benchmark_sharpe_ratio": "1.479395", "excess_return_pct": "-28.616308"}
regime stratify: 수익률 750일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  430  누적     5.41%  샤프   0.69  최대낙폭 4.99%
  RISK_OFF     n=    7  누적     0.75%
  RISK_ON      n=  313  누적     8.78%  샤프   1.78  최대낙폭 2.68%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 750,
  "by_label": {
    "CAUTION": {
      "n_days": 430,
      "total_return_pct": "5.41",
      "mean_daily_pct": "0.0127",
      "worst_day_pct": "-1.39",
      "best_day_pct": "2.17",
      "max_drawdown_pct": "4.99",
      "ann_vol_pct": "4.65",
      "ann_return_pct": "3.14",
      "sharpe": "0.69"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.75",
      "mean_daily_pct": "0.1073",
      "worst_day_pct": "-0.18",
      "best_day_pct": "0.54",
      "max_drawdown_pct": "0.18",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "8.78",
      "mean_daily_pct": "0.0272",
      "worst_day_pct": "-1.21",
      "best_day_pct": "0.80",
      "max_drawdown_pct": "2.68",
      "ann_vol_pct": "3.84",
      "ann_return_pct": "7.01",
      "sharpe": "1.78"
    }
  },
  "all": {
    "n_days": 750,
    "total_return_pct": "15.53",
    "mean_daily_pct": "0.0196",
    "worst_day_pct": "-1.39",
    "best_day_pct": "2.17",
    "max_drawdown_pct": "5.28",
    "ann_vol_pct": "4.32",
    "ann_return_pct": "4.97",
    "sharpe": "1.14"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```
