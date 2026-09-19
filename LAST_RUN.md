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
| timestamp_utc | 2026-09-19T01:27:24Z |
| 타임라인 prep exit | 0 |
| GLOBAL-TREND ssh_exit | 0 |
| GLOBAL-TREND-WIDE ssh_exit | 0 |

## GLOBAL-TREND (3자산 SPY·IEF·GLD — 라이브 지정 전략)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-056d971dec70", "dataset_version": "f8f4d84c0702543eb1574027a426b6ccfcbfe2d235c793b45b77d751674c442c", "date_start": "2023-09-19", "date_end": "2026-09-19", "portfolio_id": "global-trend", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 13, "fills": 13, "gate_rejections": 0, "total_return_pct": "34.456951", "max_drawdown_pct": "9.975296", "sharpe_ratio": "1.288674", "sortino_ratio": "1.789809", "turnover_ratio": "2.808280", "commission_usd": "101.812545", "final_equity_usd": "16116.268632", "benchmark_total_return_pct": "68.612609", "benchmark_max_drawdown_pct": "11.715649", "benchmark_sharpe_ratio": "1.566342", "excess_return_pct": "-34.155658"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적     9.68%  샤프   0.77  최대낙폭 6.97%
  RISK_OFF     n=    7  누적    -0.14%
  RISK_ON      n=  313  누적    22.76%  샤프   1.95  최대낙폭 7.01%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "9.68",
      "mean_daily_pct": "0.0225",
      "worst_day_pct": "-2.14",
      "best_day_pct": "2.76",
      "max_drawdown_pct": "6.97",
      "ann_vol_pct": "7.39",
      "ann_return_pct": "5.54",
      "sharpe": "0.77"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "-0.14",
      "mean_daily_pct": "-0.0186",
      "worst_day_pct": "-0.61",
      "best_day_pct": "0.71",
      "max_drawdown_pct": "0.61",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "22.76",
      "mean_daily_pct": "0.0670",
      "worst_day_pct": "-4.07",
      "best_day_pct": "2.15",
      "max_drawdown_pct": "7.01",
      "ann_vol_pct": "8.67",
      "ann_return_pct": "17.95",
      "sharpe": "1.95"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "34.46",
    "mean_daily_pct": "0.0406",
    "worst_day_pct": "-4.07",
    "best_day_pct": "2.76",
    "max_drawdown_pct": "9.98",
    "ann_vol_pct": "7.95",
    "ann_return_pct": "10.43",
    "sharpe": "1.29"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```

## GLOBAL-TREND-WIDE (11 슬리브 — 계획 ③ 후보)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-9ff5992a7a41", "dataset_version": "8ac37a0d169e36d5f23141b88953a3b3a8d276f7ad465fad3a00f7d51c1a75b9", "date_start": "2023-09-19", "date_end": "2026-09-19", "portfolio_id": "global-trend-wide", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 65, "fills": 65, "gate_rejections": 0, "total_return_pct": "24.120434", "max_drawdown_pct": "4.986321", "sharpe_ratio": "1.385112", "sortino_ratio": "1.967075", "turnover_ratio": "3.824964", "commission_usd": "127.650112", "final_equity_usd": "14880.014874", "benchmark_total_return_pct": "45.192483", "benchmark_max_drawdown_pct": "7.572096", "benchmark_sharpe_ratio": "1.497199", "excess_return_pct": "-21.072049"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적     7.34%  샤프   0.78  최대낙폭 5.04%
  RISK_OFF     n=    7  누적     0.67%
  RISK_ON      n=  313  누적    14.86%  샤프   2.21  최대낙폭 3.72%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "7.34",
      "mean_daily_pct": "0.0170",
      "worst_day_pct": "-1.76",
      "best_day_pct": "2.47",
      "max_drawdown_pct": "5.04",
      "ann_vol_pct": "5.49",
      "ann_return_pct": "4.22",
      "sharpe": "0.78"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.67",
      "mean_daily_pct": "0.0955",
      "worst_day_pct": "-0.18",
      "best_day_pct": "0.65",
      "max_drawdown_pct": "0.18",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "14.86",
      "mean_daily_pct": "0.0448",
      "worst_day_pct": "-1.89",
      "best_day_pct": "0.99",
      "max_drawdown_pct": "3.72",
      "ann_vol_pct": "5.12",
      "ann_return_pct": "11.80",
      "sharpe": "2.21"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "24.12",
    "mean_daily_pct": "0.0293",
    "worst_day_pct": "-1.89",
    "best_day_pct": "2.47",
    "max_drawdown_pct": "4.99",
    "ann_vol_pct": "5.33",
    "ann_return_pct": "7.51",
    "sharpe": "1.39"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```
