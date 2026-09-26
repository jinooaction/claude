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
| commit | 37829096639c7ef60c3df43bf899fce516667fc4 |
| trigger | schedule |
| timestamp_utc | 2026-09-26T01:50:50Z |
| 타임라인 prep exit | 0 |
| GLOBAL-TREND ssh_exit | 0 |
| GLOBAL-TREND-WIDE ssh_exit | 0 |

## GLOBAL-TREND (3자산 SPY·IEF·GLD — 라이브 지정 전략)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-fbd7b0e658e4", "dataset_version": "79fad3e85f33efcef49b78c981ffbad81e734d1d5742d270f1a79590487efc04", "date_start": "2023-09-26", "date_end": "2026-09-26", "portfolio_id": "global-trend", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 11, "fills": 11, "gate_rejections": 0, "total_return_pct": "20.075383", "max_drawdown_pct": "4.623367", "sharpe_ratio": "1.482341", "sortino_ratio": "2.115250", "turnover_ratio": "1.308056", "commission_usd": "43.605901", "final_equity_usd": "14399.934394", "benchmark_total_return_pct": "69.814277", "benchmark_max_drawdown_pct": "11.576406", "benchmark_sharpe_ratio": "1.607601", "excess_return_pct": "-49.738894"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적     8.40%  샤프   1.14  최대낙폭 3.06%
  RISK_OFF     n=    7  누적     0.35%
  RISK_ON      n=  313  누적    10.39%  샤프   1.91  최대낙폭 3.82%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "8.40",
      "mean_daily_pct": "0.0190",
      "worst_day_pct": "-1.16",
      "best_day_pct": "1.95",
      "max_drawdown_pct": "3.06",
      "ann_vol_pct": "4.20",
      "ann_return_pct": "4.82",
      "sharpe": "1.14"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.35",
      "mean_daily_pct": "0.0496",
      "worst_day_pct": "-0.18",
      "best_day_pct": "0.47",
      "max_drawdown_pct": "0.18",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "10.39",
      "mean_daily_pct": "0.0319",
      "worst_day_pct": "-1.80",
      "best_day_pct": "0.83",
      "max_drawdown_pct": "3.82",
      "ann_vol_pct": "4.21",
      "ann_return_pct": "8.29",
      "sharpe": "1.91"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "20.08",
    "mean_daily_pct": "0.0247",
    "worst_day_pct": "-1.80",
    "best_day_pct": "1.95",
    "max_drawdown_pct": "4.62",
    "ann_vol_pct": "4.20",
    "ann_return_pct": "6.32",
    "sharpe": "1.48"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```

## GLOBAL-TREND-WIDE (11 슬리브 — 계획 ③ 후보)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-b2e7c765d99a", "dataset_version": "fa25fb6981cea1d77cbecab88231a946db7d002509de38655ee6367bb504e6ea", "date_start": "2023-09-26", "date_end": "2026-09-26", "portfolio_id": "global-trend-wide", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 55, "fills": 55, "gate_rejections": 0, "total_return_pct": "21.049754", "max_drawdown_pct": "5.382704", "sharpe_ratio": "1.340925", "sortino_ratio": "1.928234", "turnover_ratio": "2.943565", "commission_usd": "95.981886", "final_equity_usd": "14521.056300", "benchmark_total_return_pct": "51.720767", "benchmark_max_drawdown_pct": "8.300746", "benchmark_sharpe_ratio": "1.590504", "excess_return_pct": "-30.671013"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적     9.50%  샤프   1.04  최대낙폭 5.04%
  RISK_OFF     n=    7  누적     0.55%
  RISK_ON      n=  313  누적     9.94%  샤프   1.78  최대낙폭 3.44%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "9.50",
      "mean_daily_pct": "0.0215",
      "worst_day_pct": "-1.65",
      "best_day_pct": "2.15",
      "max_drawdown_pct": "5.04",
      "ann_vol_pct": "5.23",
      "ann_return_pct": "5.44",
      "sharpe": "1.04"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.55",
      "mean_daily_pct": "0.0786",
      "worst_day_pct": "-0.22",
      "best_day_pct": "0.53",
      "max_drawdown_pct": "0.22",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "9.94",
      "mean_daily_pct": "0.0307",
      "worst_day_pct": "-1.24",
      "best_day_pct": "0.91",
      "max_drawdown_pct": "3.44",
      "ann_vol_pct": "4.34",
      "ann_return_pct": "7.93",
      "sharpe": "1.78"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "21.05",
    "mean_daily_pct": "0.0259",
    "worst_day_pct": "-1.65",
    "best_day_pct": "2.15",
    "max_drawdown_pct": "5.38",
    "ann_vol_pct": "4.86",
    "ann_return_pct": "6.61",
    "sharpe": "1.34"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```
