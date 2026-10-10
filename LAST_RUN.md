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
| commit | 4c1926f8da19bea6c2fbeaf6ccc8120c9212d63e |
| trigger | schedule |
| timestamp_utc | 2026-10-10T02:35:43Z |
| 타임라인 prep exit | 0 |
| GLOBAL-TREND ssh_exit | 0 |
| GLOBAL-TREND-WIDE ssh_exit | 0 |

## GLOBAL-TREND (3자산 SPY·IEF·GLD — 라이브 지정 전략)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-da5f6abac015", "dataset_version": "855a4af029bd3c611d8ceb37e48647589a0f02e773ce0bb4ee393eb749fef517", "date_start": "2023-10-10", "date_end": "2026-10-10", "portfolio_id": "global-trend", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 27, "fills": 14, "gate_rejections": 13, "total_return_pct": "38.451907", "max_drawdown_pct": "13.999275", "sharpe_ratio": "1.162660", "sortino_ratio": "1.605278", "turnover_ratio": "3.458950", "commission_usd": "130.195663", "final_equity_usd": "16616.643532", "benchmark_total_return_pct": "68.718906", "benchmark_max_drawdown_pct": "11.562463", "benchmark_sharpe_ratio": "1.584960", "excess_return_pct": "-30.266999"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적     8.67%  샤프   0.58  최대낙폭 9.70%
  RISK_OFF     n=    7  누적     0.31%
  RISK_ON      n=  313  누적    27.02%  샤프   1.84  최대낙폭 7.73%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "8.67",
      "mean_daily_pct": "0.0209",
      "worst_day_pct": "-2.76",
      "best_day_pct": "3.53",
      "max_drawdown_pct": "9.70",
      "ann_vol_pct": "9.03",
      "ann_return_pct": "4.97",
      "sharpe": "0.58"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.31",
      "mean_daily_pct": "0.0455",
      "worst_day_pct": "-0.90",
      "best_day_pct": "0.99",
      "max_drawdown_pct": "0.90",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "27.02",
      "mean_daily_pct": "0.0787",
      "worst_day_pct": "-5.11",
      "best_day_pct": "2.95",
      "max_drawdown_pct": "7.73",
      "ann_vol_pct": "10.77",
      "ann_return_pct": "21.23",
      "sharpe": "1.84"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "38.45",
    "mean_daily_pct": "0.0452",
    "worst_day_pct": "-5.11",
    "best_day_pct": "3.53",
    "max_drawdown_pct": "14.00",
    "ann_vol_pct": "9.79",
    "ann_return_pct": "11.52",
    "sharpe": "1.16"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```

## GLOBAL-TREND-WIDE (11 슬리브 — 계획 ③ 후보)

```
WARN: public-data sidecar fetch failed; using existing origin/automation/public-data
{"run_id": "bt-port-ee9577a6ec5d", "dataset_version": "f8816faf12902f66d26b7d161083507de7cfbc5223ac3f50caecfabf500f023f", "date_start": "2023-10-10", "date_end": "2026-10-10", "portfolio_id": "global-trend-wide", "weight_scheme": "inverse_vol", "rebalances": 36, "orders": 61, "fills": 61, "gate_rejections": 0, "total_return_pct": "22.213634", "max_drawdown_pct": "5.838212", "sharpe_ratio": "1.260991", "sortino_ratio": "1.782612", "turnover_ratio": "3.342773", "commission_usd": "111.510825", "final_equity_usd": "14657.231731", "benchmark_total_return_pct": "47.660843", "benchmark_max_drawdown_pct": "7.514805", "benchmark_sharpe_ratio": "1.566995", "excess_return_pct": "-25.447209"}
regime stratify: 수익률 752일 — d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)
  CAUTION      n=  432  누적     6.98%  샤프   0.74  최대낙폭 4.77%
  RISK_OFF     n=    7  누적     0.88%
  RISK_ON      n=  313  누적    13.25%  샤프   1.90  최대낙폭 5.36%
--- stratified json ---
{
  "schema_version": "1.0",
  "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
  "total_return_days": 752,
  "by_label": {
    "CAUTION": {
      "n_days": 432,
      "total_return_pct": "6.98",
      "mean_daily_pct": "0.0162",
      "worst_day_pct": "-1.61",
      "best_day_pct": "2.10",
      "max_drawdown_pct": "4.77",
      "ann_vol_pct": "5.54",
      "ann_return_pct": "4.01",
      "sharpe": "0.74"
    },
    "RISK_OFF": {
      "n_days": 7,
      "total_return_pct": "0.88",
      "mean_daily_pct": "0.1254",
      "worst_day_pct": "-0.22",
      "best_day_pct": "0.57",
      "max_drawdown_pct": "0.22",
      "note": "관측 7개 < 20개 — 연환산/샤프 생략"
    },
    "RISK_ON": {
      "n_days": 313,
      "total_return_pct": "13.25",
      "mean_daily_pct": "0.0403",
      "worst_day_pct": "-2.03",
      "best_day_pct": "1.07",
      "max_drawdown_pct": "5.36",
      "ann_vol_pct": "5.35",
      "ann_return_pct": "10.54",
      "sharpe": "1.90"
    }
  },
  "all": {
    "n_days": 752,
    "total_return_pct": "22.21",
    "mean_daily_pct": "0.0273",
    "worst_day_pct": "-2.03",
    "best_day_pct": "2.10",
    "max_drawdown_pct": "5.84",
    "ann_vol_pct": "5.45",
    "ann_return_pct": "6.95",
    "sharpe": "1.26"
  },
  "note": "연구 전용 — 라이브 매매 신호 아님"
}
```
