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
| commit | 68eab4e3fed44205a305d0dd7bbd5352b157f367 |
| trigger | push |
| timestamp_utc | 2026-08-22T06:28:28Z |
| 타임라인 prep exit | 0 |
| GLOBAL-TREND ssh_exit | 0 |
| GLOBAL-TREND-WIDE ssh_exit | 0 |

## GLOBAL-TREND (3자산 SPY·IEF·GLD — 라이브 지정 전략)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-acb1f6372f4a", "dataset_version": "c6a051d2854066d7308f520e53907fd4998cfea29dea00b0b9f42a3adf6bef6f", "date_start": "2023-08-22", "date_end": "2026-08-22", "portfolio_id": "global-trend", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 13, "fills": 13, "gate_rejections": 0, "total_return_pct": "17.124067", "max_drawdown_pct": "5.372807", "sharpe_ratio": "1.179584", "sortino_ratio": "1.680754", "turnover_ratio": "2.825265", "commission_usd": "93.607440", "final_equity_usd": "14046.242489", "benchmark_total_return_pct": "74.500799", "benchmark_max_drawdown_pct": "11.651342", "benchmark_sharpe_ratio": "1.683862", "excess_return_pct": "-57.376732"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적     7.19%  샤프   0.88  최대낙폭 4.25%
  RISK_OFF     n=    7  누적    -0.15%
  RISK_ON      n=  313  누적     9.44%  샤프   1.70  최대낙폭 4.05%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "7.19",
      "mean_daily_pct": "0.0165",
      "worst_day_pct": "-1.24",
      "best_day_pct": "2.16",
      "max_drawdown_pct": "4.25",
      "ann_vol_pct": "4.76",
      "ann_return_pct": "4.13",
      "sharpe": "0.88"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "-0.15",
      "mean_daily_pct": "-0.0215",
      "worst_day_pct": "-0.26",
      "best_day_pct": "0.47",
      "max_drawdown_pct": "0.47",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "9.44",
      "mean_daily_pct": "0.0292",
      "worst_day_pct": "-1.47",
      "best_day_pct": "0.68",
      "max_drawdown_pct": "4.05",
      "ann_vol_pct": "4.33",
      "ann_return_pct": "7.53",
      "sharpe": "1.70"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "17.12",
    "mean_daily_pct": "0.0214",
    "worst_day_pct": "-1.47",
    "best_day_pct": "2.16",
    "max_drawdown_pct": "5.37",
    "ann_vol_pct": "4.58",
    "ann_return_pct": "5.44",
    "sharpe": "1.18"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```

## GLOBAL-TREND-WIDE (11 슬리브 — 계획 ③ 후보)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-dfbfc41dee57", "dataset_version": "d3e7c3cf106027fae003801661630315ddda34e6c83331d705f27407758efd44", "date_start": "2023-08-22", "date_end": "2026-08-22", "portfolio_id": "global-trend-wide", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 65, "fills": 65, "gate_rejections": 0, "total_return_pct": "20.556540", "max_drawdown_pct": "5.993387", "sharpe_ratio": "1.307098", "sortino_ratio": "1.860897", "turnover_ratio": "3.739053", "commission_usd": "122.284384", "final_equity_usd": "14455.361478", "benchmark_total_return_pct": "51.576051", "benchmark_max_drawdown_pct": "8.346240", "benchmark_sharpe_ratio": "1.588700", "excess_return_pct": "-31.019511"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적     9.03%  샤프   0.97  최대낙폭 5.23%
  RISK_OFF     n=    7  누적     0.52%
  RISK_ON      n=  313  누적    10.00%  샤프   1.84  최대낙폭 2.90%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "9.03",
      "mean_daily_pct": "0.0206",
      "worst_day_pct": "-1.62",
      "best_day_pct": "2.59",
      "max_drawdown_pct": "5.23",
      "ann_vol_pct": "5.33",
      "ann_return_pct": "5.17",
      "sharpe": "0.97"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.52",
      "mean_daily_pct": "0.0744",
      "worst_day_pct": "-0.26",
      "best_day_pct": "0.54",
      "max_drawdown_pct": "0.26",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "10.00",
      "mean_daily_pct": "0.0308",
      "worst_day_pct": "-1.29",
      "best_day_pct": "0.83",
      "max_drawdown_pct": "2.90",
      "ann_vol_pct": "4.23",
      "ann_return_pct": "7.98",
      "sharpe": "1.84"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "20.56",
    "mean_daily_pct": "0.0253",
    "worst_day_pct": "-1.62",
    "best_day_pct": "2.59",
    "max_drawdown_pct": "5.99",
    "ann_vol_pct": "4.88",
    "ann_return_pct": "6.47",
    "sharpe": "1.31"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```
