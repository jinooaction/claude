# forward 페이퍼 A/B 토너먼트 — 최신 실행 (현재 데이터, 돈 안 움직임)

추세 필터 **ON**(canary-portfolio.toml / forward_v2_trend.db) vs **OFF**
(canary-portfolio-notrend.toml / forward_v2_notrend.db). 전용 DB 로 격리된
두 페이퍼 트랙을 스펙 035 forward-verdict 로 각각 판정한다. PAPER 전용 — 실주문 0건.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | 9d70758cd505844dc673291ba98651131be670b7 |
| trigger | schedule |
| timestamp_utc | 2026-10-03T01:21:38Z |
| measurement_epoch | v2-clean-unlevered |
| TREND-ON prep ssh_exit | 0 |
| TREND-ON verdict ssh_exit | 0 |
| TREND-OFF prep ssh_exit | 0 |
| TREND-OFF verdict ssh_exit | 0 |
| RISK-MANAGED-BETA prep ssh_exit | 0 |
| RISK-MANAGED-BETA verdict ssh_exit | 0 |
| MULTI-ASSET-TREND prep ssh_exit | 0 |
| MULTI-ASSET-TREND verdict ssh_exit | 0 |
| GLOBAL-TREND prep ssh_exit | 0 |
| GLOBAL-TREND verdict ssh_exit | 0 |
| GLOBAL-TREND-FIXED prep ssh_exit | 0 |
| GLOBAL-TREND-FIXED verdict ssh_exit | 0 |
| GLOBAL-TREND-WIDE prep ssh_exit | 0 |
| GLOBAL-TREND-WIDE verdict ssh_exit | 0 |

> legacy forward PSR/counts are ineligible. 이전 DB는 감사용으로 보존하지만
> 이 측정 세대의 승격 관문에는 사용하지 않는다.

## 🧪 짝지은 forward 관문 교정 (스펙 159, 주문 0건)

> 같은 날짜의 전략−벤치마크 능동 수익률로 PSR을 계산한다. 아래 대조군이
> 실패하면 이 실행은 forward 판정을 신뢰하지 않고 앞 단계에서 중단된다.

```json
{
  "schema_version": "1.0",
  "significance_method": "paired_active_return_psr_v1",
  "code_commit": "9d70758cd505844dc673291ba98651131be670b7",
  "verdict": "UNDERPOWERED",
  "false_positive_control_passed": true,
  "detection_power_passed": false,
  "scenario": {
    "seed_null": 159001,
    "seed_planted": 1159001,
    "repetitions": 5000,
    "observations": 48,
    "benchmark_daily_mean": 0.0003,
    "benchmark_daily_std": 0.01,
    "active_daily_std": 0.003,
    "planted_active_sharpe_annual": 1.5
  },
  "thresholds": {
    "paper_psr": 0.8,
    "live_psr": 0.95
  },
  "required": {
    "minimum_detection_rate": 0.8
  },
  "null": {
    "legacy_fixed_benchmark_sharpe": {
      "paper_acceptance_rate": 0.0032,
      "live_acceptance_rate": 0.0
    },
    "paired_active_return": {
      "paper_acceptance_rate": 0.2042,
      "live_acceptance_rate": 0.0482
    }
  },
  "planted_edge": {
    "legacy_fixed_benchmark_sharpe": {
      "paper_acceptance_rate": 0.0124,
      "live_acceptance_rate": 0.0
    },
    "paired_active_return": {
      "paper_acceptance_rate": 0.4274,
      "live_acceptance_rate": 0.1568
    }
  },
  "checks": {
    "paper_null_rate_within_17_to_23_pct": true,
    "live_null_rate_at_most_6_pct": true,
    "paired_planted_power_exceeds_legacy": true,
    "paper_planted_detection_at_least_80pct": false,
    "live_planted_detection_at_least_80pct": false
  },
  "safety": [
    "simulation only",
    "no broker API",
    "no orders",
    "no capital change"
  ]
}
```

# 🏆 forward 토너먼트 리더보드 — 읽기 전용, 돈 0 이동

> ➖ 엣지 확정 트랙 없음 — 비교 가능 트랙 모두 NO_EDGE(우위가 우연과 구별 안 됨). 더 나은 후보 탐색 계속.
>
> 비교 가능하지만 단순 보유를 과적합 보정 후 못 이긴 상태. 라이브 변경 사유 없음.

| # | 트랙 | 판정 | 관측 | 칼마 | 샤프 | 초과수익% | 낙폭% | 상태 |
|--:|------|:----:|-----:|-----:|-----:|----------:|------:|:----:|
| 1 | 위험관리 베타 (스펙 042) | ➖ NO_EDGE | 29/20 | 15.54 | 2.61 | 0.30 | 2.06 | ✅ |
| 2 | 멀티에셋 분산 추세 (스펙 043) | ➖ NO_EDGE | 29/20 | 2.86 | 0.74 | 2.55 | 1.11 | ✅ |
| 3 | 추세 필터 OFF (대조군) | ➖ NO_EDGE | 29/20 | 2.47 | 0.86 | 1.07 | 2.64 | ✅ |
| 4 | 추세 필터 ON (드로다운 방어) | ➖ NO_EDGE | 29/20 | 2.47 | 0.86 | 1.07 | 2.64 | ✅ |
| 5 | 글로벌 분산 추세 확대 (11 슬리브) | ➖ NO_EDGE | 29/20 | -0.61 | -0.13 | 2.26 | 0.33 | ✅ |
| 6 | 글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD) 🏠 | ➖ NO_EDGE | 29/20 | -6.17 | -2.06 | 4.46 | 0.99 | ✅ |
| 7 | 글로벌 3자산 추세 고정등가중 (재지정 후보) | ➖ NO_EDGE | 29/20 | -6.61 | -3.26 | 1.75 | 3.96 | ✅ |

🏠 라이브 검증 트랙 · 👑 챔피언(비교 가능 EDGE_CONFIRMED 1위) · 🚀 도전자(검증 트랙을 앞섬). 잠정(⏳)은 관측이 더 쌓여야 비교 가능 — 지표는 잠정치.

## 후보 관측 품질

✅ **OK** — 모든 후보 판정이 읽혔고 관측 누적이 같은 속도로 진행 중.

| 전체 | 판정 읽힘 | 판정 없음 | 최소 관측 | 최대 관측 | 뒤처진 트랙 |
|-----:|----------:|----------:|----------:|----------:|-------------|
| 7 | 7 | 0 | 29 | 29 | — |

⚠ 이건 종합 보고다(읽기 전용). 라이브 전략은 자동으로 안 바뀐다 — 재지정은 운영자 게이트(헌법 X.4). 검증=배치 정합이라 도전자가 라이브가 되려면 라이브 설정 지문을 그 트랙으로 맞추는 운영자/세션 결정이 필요하다.

## 🧾 리더보드 결정 JSON (기계 판독 단일 증거)

> 아래 JSON 은 위 리더보드와 같은 순수 코어 출력이다. 재지정·감시 루프는
> 가능하면 이 기계 판독 증거를 우선 소비해야 한다. 특히 known_count,
> unknown_count, observation_health 로 후보 관측 품질을 분리해 본다.

```json
{"schema_version": "1.0", "as_of_utc": "2026-10-03T01:21:38.944448+00:00", "champion_key": null, "incumbent_key": "global", "challenger_key": null, "comparable_count": 7, "adjusted_dsr_threshold": null, "champion_multiplicity_robust": null, "track_count": 7, "known_count": 7, "unknown_count": 0, "max_n_obs": 29, "min_n_obs": 29, "lagging_keys": [], "observation_health": "OK", "observation_note": "모든 후보 판정이 읽혔고 관측 누적이 같은 속도로 진행 중.", "headline": "➖ 엣지 확정 트랙 없음 — 비교 가능 트랙 모두 NO_EDGE(우위가 우연과 구별 안 됨). 더 나은 후보 탐색 계속.", "note": "비교 가능하지만 단순 보유를 과적합 보정 후 못 이긴 상태. 라이브 변경 사유 없음.", "rows": [{"key": "rmbeta", "label": "위험관리 베타 (스펙 042)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 29, "min_obs": 20, "comparability": "COMPARABLE", "rank": 1, "calmar": "15.536337", "sharpe": "2.614542", "total_return_pct": "3.243917", "max_drawdown_pct": "2.057801", "excess_return_pct": "0.299111", "dsr": null, "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": "0.523320", "dsr_threshold": "0.95", "universe_size": 2, "universe": ["SPY", "QQQ"]}, {"key": "multiasset", "label": "멀티에셋 분산 추세 (스펙 043)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 29, "min_obs": 20, "comparability": "COMPARABLE", "rank": 2, "calmar": "2.859349", "sharpe": "0.742004", "total_return_pct": "0.359917", "max_drawdown_pct": "1.109058", "excess_return_pct": "2.547212", "dsr": null, "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": "0.834553", "dsr_threshold": "0.95", "universe_size": 2, "universe": ["SPY", "IEF"]}, {"key": "notrend", "label": "추세 필터 OFF (대조군)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 29, "min_obs": 20, "comparability": "COMPARABLE", "rank": 3, "calmar": "2.471911", "sharpe": "0.855028", "total_return_pct": "0.730375", "max_drawdown_pct": "2.640818", "excess_return_pct": "1.071927", "dsr": null, "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": "0.660499", "dsr_threshold": "0.95", "universe_size": 501, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES"]}, {"key": "trend", "label": "추세 필터 ON (드로다운 방어)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 29, "min_obs": 20, "comparability": "COMPARABLE", "rank": 4, "calmar": "2.471911", "sharpe": "0.855012", "total_return_pct": "0.730375", "max_drawdown_pct": "2.640818", "excess_return_pct": "1.072305", "dsr": null, "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": "0.660542", "dsr_threshold": "0.95", "universe_size": 501, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES"]}, {"key": "wide", "label": "글로벌 분산 추세 확대 (11 슬리브)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 29, "min_obs": 20, "comparability": "COMPARABLE", "rank": 5, "calmar": "-0.610771", "sharpe": "-0.126832", "total_return_pct": "-0.023500", "max_drawdown_pct": "0.334041", "excess_return_pct": "2.258668", "dsr": null, "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": "0.832851", "dsr_threshold": "0.95", "universe_size": 11, "universe": ["SPY", "QQQ", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD"]}, {"key": "global", "label": "글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD)", "is_incumbent": true, "verdict": "NO_EDGE", "n_obs": 29, "min_obs": 20, "comparability": "COMPARABLE", "rank": 6, "calmar": "-6.172341", "sharpe": "-2.056317", "total_return_pct": "-0.720417", "max_drawdown_pct": "0.986584", "excess_return_pct": "4.464689", "dsr": null, "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": "0.890323", "dsr_threshold": "0.95", "universe_size": 3, "universe": ["SPY", "IEF", "GLD"]}, {"key": "globalfixed", "label": "글로벌 3자산 추세 고정등가중 (재지정 후보)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 29, "min_obs": 20, "comparability": "COMPARABLE", "rank": 7, "calmar": "-6.605011", "sharpe": "-3.261098", "total_return_pct": "-3.432250", "max_drawdown_pct": "3.963085", "excess_return_pct": "1.752706", "dsr": null, "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": "0.650120", "dsr_threshold": "0.95", "universe_size": 3, "universe": ["SPY", "IEF", "GLD"]}]}
```

## 🚦 Halt 깃발 상태 (읽기 전용 진단)

> data/halt.flag 는 라이브 워커·라이브 캐너리의 킬스위치(스펙 014 서킷 브레이커
> ·정합성 불일치가 자동 설정). 페이퍼 forward 트랙은 트랙별 전용 깃발
> (data/forward_*.halt.flag)로 격리되어 라이브 깃발에 막히지 않는다. 라이브
> 깃발이 서 있으면 무장 후 실주문이 거부되므로, 운영자는 아래 사유를 확인하고
> 서버에서 'auto-invest resume' 으로 해제를 결정한다(자동 해제 안 함 — 안전 자세).

```
-- data/halt.flag
(none)
-- data/forward_trend.halt.flag
(none)
-- data/forward_notrend.halt.flag
(none)
-- data/forward_rmbeta.halt.flag
(none)
-- data/forward_multiasset.halt.flag
(none)
-- data/forward_global.halt.flag
(none)
-- data/forward_globalfixed.halt.flag
(none)
-- data/forward_wide.halt.flag
(none)
```

## 🔭 일일 전략 모니터 (스펙 046 — 지속 감시, 돈 0 이동)

> 검증된 스펙(042~045)을 합친 대시보드: ① 엣지 최근 유효성 ② 분산 가정 신뢰도
> ③ 낙폭 예산별 레버리지 복리 권고(최근 25년) ④ 오늘 추세 신호. 라이브 레버리지/
> 무장은 여전히 운영자 게이트(헌법 X.4) — 이건 감시 보고이지 거래 변경이 아니다.

```
=== 낙폭 예산 15% ===
# 일일 전략 모니터 (as of 2026-09) — 읽기 전용, 돈 0 이동

① 엣지(분산 추세)가 최근에도 유효한가:
   최근 5년 샤프 +1.74 | 최근 10년 샤프 +1.78 | 최근 5년 낙폭 +3.63%

② 분산 가정이 지금 신뢰 가능한가 (주식·채권 상관):
   현재 -0.01 | 최근 5년 평균 +0.12 → 판정: DIVERSIFICATION_WEAKENED

③ 낙폭 예산 15%에서 레버리지 복리 권고 (최근 25년 기준):
   무레버 복리 +7.88% → 권고 L=2.0 → 복리 11.4%/년 (낙폭 13%)

④ 오늘 추세 신호 (S&P vs 10개월 SMA):
   투자(추세 위) (갭 +6.50%)

⚠ 이건 감시 보고다. 라이브 레버리지/무장은 운영자 게이트(헌법 X.4).

=== 낙폭 예산 20% (레버리지 권고 비교) ===
{"as_of": "2026-09", "edge": {"diversified_5y_sharpe": 1.74, "diversified_10y_sharpe": 1.78, "diversified_5y_maxdd_pct": 3.629}, "regime": {"corr_current": -0.015, "corr_recent_5y_avg": 0.123, "verdict": "DIVERSIFICATION_WEAKENED"}, "leverage_recommendation": {"dd_budget_pct": 20.0, "window_years": 25, "unlevered_cagr_pct": 7.882, "leverage": 3.0, "cagr_pct": 14.845, "maxdd_pct": 19.591}, "today_signal": {"in_market": true, "gap_pct": 6.502}}
```

## 🧭 판정 — 추세 필터 ON (drawdown 방어 오버레이)

> EDGE_CONFIRMED 만이 운영자 라이브 게이트(헌법 X.4)에 올릴 증거(자동 배포 아님).
> INSUFFICIENT_DATA 면 NAV 관측이 더 쌓여야 한다(≈20 거래일) — 정상.

```json
{"schema_version": "1.2", "verdict": "NO_EDGE", "reason": "\ub2a5\ub3d9 \uc218\uc775\ub960 PSR 0.660542 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 2.471911 > \ubca4\uce58 -6.472484 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 29, "min_obs_required": 20, "strategy_sharpe_annual": "0.855012", "strategy_total_return_pct": "0.730375", "strategy_max_drawdown_pct": "2.640818", "strategy_calmar": "2.471911", "benchmark_sharpe_annual": "-4.295123", "benchmark_total_return_pct": "-0.341930", "benchmark_max_drawdown_pct": "0.453070", "benchmark_calmar": "-6.472484", "excess_return_pct": "1.072305", "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": "1.239143", "psr_vs_benchmark": "0.660542", "dsr": null, "num_trials": 1, "min_track_record_obs": "443.111085", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 30, "legacy_snapshots_excluded": 0, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A", "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT", "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX", "BDX", "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BNY", "BA", "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CPT", "CPB", "COF", "CAH", "CCL", "CARR", "CVNA", "CASY", "CAT", "CBOE", "CBRE", "CDW", "COR", "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD", "CIEN", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS", "KO", "CTSH", "COHR", "COIN", "CL", "CMCSA", "FIX", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP", "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI", "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM", "FANG", "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI", "DTE", "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW", "EA", "ELV", "EME", "EMR", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ERIE", "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB", "FSLR", "FE", "FISV", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA", "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON", "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "IBKR", "ICE", "IFF", "IP", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR", "LHX", "LH", "LRCX", "LVS", "LDOS", "LEN", "LII", "LLY", "LIN", "LYV", "LMT", "L", "LOW", "LULU", "LITE", "LYB", "MTB", "MPC", "MAR", "MRSH", "MLM", "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PSKY", "PH", "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTC", "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL", "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC", "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL", "TXT", "TMO", "TJX", "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VRT", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WY", "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH", "ZTS"]}
```

## 🧭 판정 — 추세 필터 OFF (대조군)

```json
{"schema_version": "1.2", "verdict": "NO_EDGE", "reason": "\ub2a5\ub3d9 \uc218\uc775\ub960 PSR 0.660499 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 2.471911 > \ubca4\uce58 -6.470821 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 29, "min_obs_required": 20, "strategy_sharpe_annual": "0.855028", "strategy_total_return_pct": "0.730375", "strategy_max_drawdown_pct": "2.640818", "strategy_calmar": "2.471911", "benchmark_sharpe_annual": "-4.291241", "benchmark_total_return_pct": "-0.341552", "benchmark_max_drawdown_pct": "0.452692", "benchmark_calmar": "-6.470821", "excess_return_pct": "1.071927", "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": "1.238791", "psr_vs_benchmark": "0.660499", "dsr": null, "num_trials": 1, "min_track_record_obs": "443.363847", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 30, "legacy_snapshots_excluded": 0, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A", "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT", "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX", "BDX", "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BNY", "BA", "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CPT", "CPB", "COF", "CAH", "CCL", "CARR", "CVNA", "CASY", "CAT", "CBOE", "CBRE", "CDW", "COR", "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD", "CIEN", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS", "KO", "CTSH", "COHR", "COIN", "CL", "CMCSA", "FIX", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP", "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI", "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM", "FANG", "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI", "DTE", "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW", "EA", "ELV", "EME", "EMR", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ERIE", "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB", "FSLR", "FE", "FISV", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA", "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON", "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "IBKR", "ICE", "IFF", "IP", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR", "LHX", "LH", "LRCX", "LVS", "LDOS", "LEN", "LII", "LLY", "LIN", "LYV", "LMT", "L", "LOW", "LULU", "LITE", "LYB", "MTB", "MPC", "MAR", "MRSH", "MLM", "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PSKY", "PH", "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTC", "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL", "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC", "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL", "TXT", "TMO", "TJX", "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VRT", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WY", "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH", "ZTS"]}
```

> 두 판정을 나란히 비교: ON 의 max_drawdown_pct·sharpe·excess 가 OFF 보다
> 나으면 추세 필터가 *실제로* 도움이 된다는 격리된 증거다.

## 🛡️ 판정 — 위험관리 베타 (추세 게이트 광범위 베타, 스펙 042)

> SPY·QQQ 를 10개월 추세 위일 때만 보유(아래면 현금). 종목 선택이 아니라 베타의
> 자본 방어. 우리 KIS 체결로 forward 실적을 쌓아 *확신을 번다*(운영자 2026-06-05).
> INSUFFICIENT_DATA 면 NAV 관측이 더 쌓여야 함(정상). 200일 미만이면 추세 미확정 →
> on_insufficient=cash 라 현금 보유(보수적). 라이브 전환은 운영자 게이트(헌법 X.4).

```json
{"schema_version": "1.2", "verdict": "NO_EDGE", "reason": "\ub2a5\ub3d9 \uc218\uc775\ub960 PSR 0.523320 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 15.536337 > \ubca4\uce58 12.85069 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 29, "min_obs_required": 20, "strategy_sharpe_annual": "2.614542", "strategy_total_return_pct": "3.243917", "strategy_max_drawdown_pct": "2.057801", "strategy_calmar": "15.536337", "benchmark_sharpe_annual": "2.053265", "benchmark_total_return_pct": "2.944806", "benchmark_max_drawdown_pct": "2.232183", "benchmark_calmar": "12.85069", "excess_return_pct": "0.299111", "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": "0.175725", "psr_vs_benchmark": "0.523320", "dsr": null, "num_trials": 1, "min_track_record_obs": "22145.865343", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 30, "legacy_snapshots_excluded": 0, "universe": ["SPY", "QQQ"]}
```

## 🌐 판정 — 멀티에셋 분산 추세 (비상관 자산 합성, 스펙 043)

> 주식(SPY) + 채권(IEF) 을 각자 추세 위일 때만 보유. ARM C(둘 다 주식)와 달리
> *비상관 자산*을 합쳐 분산 이득을 노린다(스펙 043: 단일 주식 추세 샤프 1.18~1.43
> → 분산 추세 1.58~1.81, 낙폭 절반, Shiller 1871~ 검증). INSUFFICIENT_DATA 면
> NAV 관측이 더 쌓여야 함(정상). 라이브 전환은 운영자 게이트(헌법 X.4).

```json
{"schema_version": "1.2", "verdict": "NO_EDGE", "reason": "\ub2a5\ub3d9 \uc218\uc775\ub960 PSR 0.834553 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 2.859349 > \ubca4\uce58 -6.622371 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 29, "min_obs_required": 20, "strategy_sharpe_annual": "0.742004", "strategy_total_return_pct": "0.359917", "strategy_max_drawdown_pct": "1.109058", "strategy_calmar": "2.859349", "benchmark_sharpe_annual": "-2.588878", "benchmark_total_return_pct": "-2.187295", "benchmark_max_drawdown_pct": "2.640141", "benchmark_calmar": "-6.622371", "excess_return_pct": "2.547212", "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": "3.019773", "psr_vs_benchmark": "0.834553", "dsr": null, "num_trials": 1, "min_track_record_obs": "81.130988", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 30, "legacy_snapshots_excluded": 0, "universe": ["SPY", "IEF"]}
```

## 🪙 판정 — 글로벌 분산 추세 (주식+채권+금, 역변동성, 스펙 047)

> ARM D(주식+채권 2자산)에 *세 번째 비상관 자산(금, GLD)* 을 더한 3자산 GTAA.
> 금은 주식·채권 둘 다와 비상관 — 특히 주식·채권 상관이 양수로 가는 인플레
> regime(일일 모니터의 DIVERSIFICATION_WEAKENED 경고)의 구조적 헤지다. 금은
> 변동성 큰 자산이라 *역변동성(리스크 패리티)* 으로 사이징해 분산 이득만 취하고
> 변동성은 안 들여온다(스펙 047: 균등가중은 낙폭 악화, 역변동성은 모든 구간 낙폭
> ~5%·칼마↑). INSUFFICIENT_DATA 면 NAV 가 더 쌓여야 함(정상). ARM D 와 나란히
> 비교하면 '금이 우리 체결 기준 forward 로도 분산을 더하는가'의 격리된 답.
> 라이브 전환은 운영자 게이트(헌법 X.4).

```json
{"schema_version": "1.2", "verdict": "NO_EDGE", "reason": "\ub2a5\ub3d9 \uc218\uc775\ub960 PSR 0.890323 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 -6.172341 > \ubca4\uce58 -6.936215 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 29, "min_obs_required": 20, "strategy_sharpe_annual": "-2.056317", "strategy_total_return_pct": "-0.720417", "strategy_max_drawdown_pct": "0.986584", "strategy_calmar": "-6.172341", "benchmark_sharpe_annual": "-4.311463", "benchmark_total_return_pct": "-5.185106", "benchmark_max_drawdown_pct": "5.340076", "benchmark_calmar": "-6.936215", "excess_return_pct": "4.464689", "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": "3.683375", "psr_vs_benchmark": "0.890323", "dsr": null, "num_trials": 1, "min_track_record_obs": "51.215932", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 30, "legacy_snapshots_excluded": 0, "universe": ["SPY", "IEF", "GLD"]}
```

## ⚖ 판정 — 글로벌 3자산 추세 고정(등가중) 재지정 후보 (스펙 047/050 후속)

> 라이브 검증 트랙과 weight_scheme 만 다른 등가중 변형. 깊은 분석은 등가중이
> 캡 안 무레버 복리 +1.3~2.3%p 높다고 봤으나 낙폭이 사다리 강등선(10%)에 더
> 가깝다 — 이 트랙이 *일별* 낙폭/강등 빈도를 실측해 재지정 안전성을 답한다.
> EDGE_CONFIRMED + 지문 정합을 벌면 운영자가 재지정 결정(헌법 X.4). 돈 0·페이퍼.

```json
{"schema_version": "1.2", "verdict": "NO_EDGE", "reason": "\ub2a5\ub3d9 \uc218\uc775\ub960 PSR 0.650120 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 -6.605011 > \ubca4\uce58 -6.936247 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 29, "min_obs_required": 20, "strategy_sharpe_annual": "-3.261098", "strategy_total_return_pct": "-3.432250", "strategy_max_drawdown_pct": "3.963085", "strategy_calmar": "-6.605011", "benchmark_sharpe_annual": "-4.311349", "benchmark_total_return_pct": "-5.184956", "benchmark_max_drawdown_pct": "5.339926", "benchmark_calmar": "-6.936247", "excess_return_pct": "1.752706", "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": "1.163173", "psr_vs_benchmark": "0.650120", "dsr": null, "num_trials": 1, "min_track_record_obs": "510.376659", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 30, "legacy_snapshots_excluded": 0, "universe": ["SPY", "IEF", "GLD"]}
```

## 🌍 판정 — 글로벌 분산 추세 확대 유니버스 (11 슬리브, 계획 ③)

> 검증된 메커니즘(역변동성 + 다중 속도 추세 앙상블) 그대로, 베팅의 폭만
> 3 → 11 슬리브(주식 SPY·QQQ·EFA·EEM / 채권 IEF·TLT·LQD / 실물 GLD·DBC·VNQ
> / 통화 UUP). 성과 ≈ 질 × √N — 제약 안에서 가장 큰 지렛대. ARM E(3자산)와
> 나란히 비교하면 '폭 확장이 우리 체결 기준 forward 로도 이득인가'의 격리된
> 답. 라이브는 검증된 3자산 유지 — 이 트랙이 EDGE_CONFIRMED 를 벌어야 재지정
> 후보가 된다(검증=배치 정합, 헌법 X.4 v5.0.0 사다리).

```json
{"schema_version": "1.2", "verdict": "NO_EDGE", "reason": "\ub2a5\ub3d9 \uc218\uc775\ub960 PSR 0.832851 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 -0.610771 > \ubca4\uce58 -7.009504 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 29, "min_obs_required": 20, "strategy_sharpe_annual": "-0.126832", "strategy_total_return_pct": "-0.023500", "strategy_max_drawdown_pct": "0.334041", "strategy_calmar": "-0.610771", "benchmark_sharpe_annual": "-2.806150", "benchmark_total_return_pct": "-2.282168", "benchmark_max_drawdown_pct": "2.593178", "benchmark_calmar": "-7.009504", "excess_return_pct": "2.258668", "beats_benchmark_calmar": true, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": "2.968648", "psr_vs_benchmark": "0.832851", "dsr": null, "num_trials": 1, "min_track_record_obs": "82.267016", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 30, "legacy_snapshots_excluded": 0, "universe": ["SPY", "QQQ", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD", "DBC", "VNQ", "UUP"]}
```

## TREND-ON 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_trend.db
{"results": [{"symbol": "COHR", "exchange": "NYS", "fetched": 906, "inserted": 1}, {"symbol": "COO", "exchange": "NAS", "fetched": 758, "inserted": 1}, {"symbol": "CPAY", "exchange": "NYS", "fetched": 634, "inserted": 1}, {"symbol": "CPB", "exchange": "NAS", "fetched": 533, "inserted": 1}, {"symbol": "BNY", "exchange": "NYS", "fetched": 93, "inserted": 1}]}
{"portfolio_id": "forward-paper-canary", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "signal_target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": false, "capital_usd": "12000.0", "investable_usd": "11400.000", "active_target_count": 10, "funded_target_count": 10, "funded_target_ratio": "1", "whole_share_eligible_target_count": 10, "funded_whole_share_target_count": 10, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.95", "target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "holdings": {"ABNB": 3, "ADP": 2, "AMAT": 1, "AMD": 1, "ANET": 3, "BAC": 10, "BKNG": 2, "BX": 4, "CRWD": 3, "CSCO": 5}, "prices": {"ABNB": "162.4300", "ADP": "257.6800", "AMAT": "540.0400", "AMD": "633.9100", "ANET": "207.3500", "BAC": "53.7500", "BKNG": "159.0200", "BX": "111.7500", "CRWD": "270.0400", "CSCO": "112.2000"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "5.0", "per_symbol_pct": "25.0", "global_exposure_pct": "80.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"AMD": 1, "CRWD": 3, "ANET": 3, "ABNB": 3, "CSCO": 5, "AMAT": 1, "ADP": 2, "BX": 4, "BKNG": 2, "BAC": 10}, "projected_weights": {"AMD": "0.05282583333333333333333333333", "CRWD": "0.06751", "ANET": "0.0518375", "ABNB": "0.0406075", "CSCO": "0.04675", "AMAT": "0.04500333333333333333333333333", "ADP": "0.04294666666666666666666666667", "BX": "0.03725", "BKNG": "0.02650333333333333333333333333", "BAC": "0.04479166666666666666666666667"}, "l1_weight_error": "0.4939741666666666666666666667", "max_leg_weight_error": "0.06849666666666666666666666667", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": false, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": ["l1_weight_error"]}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=58)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "6615.3350", "total_market_value_usd": "5472.3100", "total_nav_usd": "12087.6450", "total_unrealized_pnl_usd": "145.8050", "broker_reported_nav_usd": null, "holdings": [{"symbol": "ABNB", "qty": 3, "avg_cost_usd": "190.2100", "mark_price_usd": "162.4300", "market_value_usd": "487.2900", "marked": true, "weight_pct": "4.031306346273405613748583781", "unrealized_pnl_usd": "-83.3400"}, {"symbol": "ADP", "qty": 2, "avg_cost_usd": "283.0100", "mark_price_usd": "257.6800", "market_value_usd": "515.3600", "marked": true, "weight_pct": "4.263526931838253026127090926", "unrealized_pnl_usd": "-50.6600"}, {"symbol": "AMAT", "qty": 1, "avg_cost_usd": "484.1900", "mark_price_usd": "540.0400", "market_value_usd": "540.0400", "marked": true, "weight_pct": "4.467702352277883739967545374", "unrealized_pnl_usd": "55.8500"}, {"symbol": "AMD", "qty": 1, "avg_cost_usd": "456.7450", "mark_price_usd": "633.9100", "market_value_usd": "633.9100", "marked": true, "weight_pct": "5.244280420214193914530084231", "unrealized_pnl_usd": "177.1650"}, {"symbol": "ANET", "qty": 3, "avg_cost_usd": "188.1500", "mark_price_usd": "207.3500", "market_value_usd": "622.0500", "marked": true, "weight_pct": "5.146163706826267647668342345", "unrealized_pnl_usd": "57.6000"}, {"symbol": "BAC", "qty": 10, "avg_cost_usd": "56.0000", "mark_price_usd": "53.7500", "market_value_usd": "537.5000", "marked": true, "weight_pct": "4.446689160709137305074727128", "unrealized_pnl_usd": "-22.5000"}, {"symbol": "BKNG", "qty": 2, "avg_cost_usd": "213.3600", "mark_price_usd": "159.0200", "market_value_usd": "318.0400", "marked": true, "weight_pct": "2.631116317529179587918076681", "unrealized_pnl_usd": "-108.6800"}, {"symbol": "BX", "qty": 4, "avg_cost_usd": "143.6400", "mark_price_usd": "111.7500", "market_value_usd": "447.0000", "marked": true, "weight_pct": "3.697990799696715116964470747", "unrealized_pnl_usd": "-127.5600"}, {"symbol": "CRWD", "qty": 3, "avg_cost_usd": "190.6800", "mark_price_usd": "270.0400", "market_value_usd": "810.1200", "marked": true, "weight_pct": "6.702049903020811746208628728", "unrealized_pnl_usd": "238.0800"}, {"symbol": "CSCO", "qty": 5, "avg_cost_usd": "110.2300", "mark_price_usd": "112.2000", "market_value_usd": "561.0000", "marked": true, "weight_pct": "4.641102547270374005854738454", "unrealized_pnl_usd": "9.8500"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```

## TREND-OFF 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_notrend.db
{"results": [{"symbol": "COHR", "exchange": "NYS", "fetched": 906, "inserted": 1}, {"symbol": "COO", "exchange": "NAS", "fetched": 758, "inserted": 1}, {"symbol": "CPAY", "exchange": "NYS", "fetched": 634, "inserted": 1}, {"symbol": "CPB", "exchange": "NAS", "fetched": 533, "inserted": 1}, {"symbol": "BNY", "exchange": "NYS", "fetched": 93, "inserted": 1}]}
{"portfolio_id": "forward-paper-canary-notrend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "signal_target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": false, "capital_usd": "12000.0", "investable_usd": "11400.000", "active_target_count": 10, "funded_target_count": 10, "funded_target_ratio": "1", "whole_share_eligible_target_count": 10, "funded_whole_share_target_count": 10, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.95", "target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "holdings": {"ABNB": 3, "ADP": 2, "AMAT": 1, "AMD": 1, "ANET": 3, "BAC": 10, "BKNG": 2, "BX": 4, "CRWD": 3, "CSCO": 5}, "prices": {"ABNB": "162.4300", "ADP": "257.6800", "AMAT": "540.0400", "AMD": "633.9100", "ANET": "207.3500", "BAC": "53.7500", "BKNG": "159.0200", "BX": "111.7500", "CRWD": "270.0400", "CSCO": "112.2000"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "5.0", "per_symbol_pct": "25.0", "global_exposure_pct": "80.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"AMD": 1, "CRWD": 3, "ANET": 3, "ABNB": 3, "CSCO": 5, "AMAT": 1, "ADP": 2, "BX": 4, "BKNG": 2, "BAC": 10}, "projected_weights": {"AMD": "0.05282583333333333333333333333", "CRWD": "0.06751", "ANET": "0.0518375", "ABNB": "0.0406075", "CSCO": "0.04675", "AMAT": "0.04500333333333333333333333333", "ADP": "0.04294666666666666666666666667", "BX": "0.03725", "BKNG": "0.02650333333333333333333333333", "BAC": "0.04479166666666666666666666667"}, "l1_weight_error": "0.4939741666666666666666666667", "max_leg_weight_error": "0.06849666666666666666666666667", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": false, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": ["l1_weight_error"]}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=58)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "6615.3350", "total_market_value_usd": "5472.3100", "total_nav_usd": "12087.6450", "total_unrealized_pnl_usd": "145.8050", "broker_reported_nav_usd": null, "holdings": [{"symbol": "ABNB", "qty": 3, "avg_cost_usd": "190.2100", "mark_price_usd": "162.4300", "market_value_usd": "487.2900", "marked": true, "weight_pct": "4.031306346273405613748583781", "unrealized_pnl_usd": "-83.3400"}, {"symbol": "ADP", "qty": 2, "avg_cost_usd": "283.0100", "mark_price_usd": "257.6800", "market_value_usd": "515.3600", "marked": true, "weight_pct": "4.263526931838253026127090926", "unrealized_pnl_usd": "-50.6600"}, {"symbol": "AMAT", "qty": 1, "avg_cost_usd": "484.1900", "mark_price_usd": "540.0400", "market_value_usd": "540.0400", "marked": true, "weight_pct": "4.467702352277883739967545374", "unrealized_pnl_usd": "55.8500"}, {"symbol": "AMD", "qty": 1, "avg_cost_usd": "456.7450", "mark_price_usd": "633.9100", "market_value_usd": "633.9100", "marked": true, "weight_pct": "5.244280420214193914530084231", "unrealized_pnl_usd": "177.1650"}, {"symbol": "ANET", "qty": 3, "avg_cost_usd": "188.1500", "mark_price_usd": "207.3500", "market_value_usd": "622.0500", "marked": true, "weight_pct": "5.146163706826267647668342345", "unrealized_pnl_usd": "57.6000"}, {"symbol": "BAC", "qty": 10, "avg_cost_usd": "56.0000", "mark_price_usd": "53.7500", "market_value_usd": "537.5000", "marked": true, "weight_pct": "4.446689160709137305074727128", "unrealized_pnl_usd": "-22.5000"}, {"symbol": "BKNG", "qty": 2, "avg_cost_usd": "213.3600", "mark_price_usd": "159.0200", "market_value_usd": "318.0400", "marked": true, "weight_pct": "2.631116317529179587918076681", "unrealized_pnl_usd": "-108.6800"}, {"symbol": "BX", "qty": 4, "avg_cost_usd": "143.6400", "mark_price_usd": "111.7500", "market_value_usd": "447.0000", "marked": true, "weight_pct": "3.697990799696715116964470747", "unrealized_pnl_usd": "-127.5600"}, {"symbol": "CRWD", "qty": 3, "avg_cost_usd": "190.6800", "mark_price_usd": "270.0400", "market_value_usd": "810.1200", "marked": true, "weight_pct": "6.702049903020811746208628728", "unrealized_pnl_usd": "238.0800"}, {"symbol": "CSCO", "qty": 5, "avg_cost_usd": "110.2300", "mark_price_usd": "112.2000", "market_value_usd": "561.0000", "marked": true, "weight_pct": "4.641102547270374005854738454", "unrealized_pnl_usd": "9.8500"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```

## RISK-MANAGED-BETA 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_rmbeta.db
{"results": [{"symbol": "QQQ", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "risk-managed-beta", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"QQQ": "0.500000", "SPY": "0.500000"}, "signal_target_weights": {"QQQ": "0.500000", "SPY": "0.500000"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "12000.0", "investable_usd": "11880.000", "active_target_count": 2, "funded_target_count": 2, "funded_target_ratio": "1", "whole_share_eligible_target_count": 2, "funded_whole_share_target_count": 2, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"QQQ": "0.500000", "SPY": "0.500000"}, "holdings": {"QQQ": 8, "SPY": 7}, "prices": {"QQQ": "749.5800", "SPY": "769.6400"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"QQQ": 8, "SPY": 7}, "projected_weights": {"QQQ": "0.49972", "SPY": "0.4489566666666666666666666667"}, "l1_weight_error": "0.0507633333333333333333333333", "max_leg_weight_error": "0.0460433333333333333333333333", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=34)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "1005.1500", "total_market_value_usd": "11384.1200", "total_nav_usd": "12389.2700", "total_unrealized_pnl_usd": "389.2700", "broker_reported_nav_usd": null, "holdings": [{"symbol": "QQQ", "qty": 8, "avg_cost_usd": "706.3200", "mark_price_usd": "749.5800", "market_value_usd": "5996.6400", "marked": true, "weight_pct": "48.40188324251549929899017456", "unrealized_pnl_usd": "346.0800"}, {"symbol": "SPY", "qty": 7, "avg_cost_usd": "763.4700", "mark_price_usd": "769.6400", "market_value_usd": "5387.4800", "marked": true, "weight_pct": "43.48504794874919991250493370", "unrealized_pnl_usd": "43.1900"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```

## MULTI-ASSET-TREND 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_multiasset.db
{"results": [{"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "multi-asset-trend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"SPY": "0.500000"}, "signal_target_weights": {"SPY": "0.500000"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "12000.0", "investable_usd": "11880.000", "active_target_count": 1, "funded_target_count": 1, "funded_target_ratio": "1", "whole_share_eligible_target_count": 1, "funded_whole_share_target_count": 1, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"SPY": "0.500000"}, "holdings": {"SPY": 7}, "prices": {"SPY": "769.6400"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"SPY": 7}, "projected_weights": {"SPY": "0.4489566666666666666666666667"}, "l1_weight_error": "0.0460433333333333333333333333", "max_leg_weight_error": "0.0460433333333333333333333333", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=32)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "6655.7100", "total_market_value_usd": "5387.4800", "total_nav_usd": "12043.1900", "total_unrealized_pnl_usd": "43.1900", "broker_reported_nav_usd": null, "holdings": [{"symbol": "SPY", "qty": 7, "avg_cost_usd": "763.4700", "mark_price_usd": "769.6400", "market_value_usd": "5387.4800", "marked": true, "weight_pct": "44.73465917252820888817663759", "unrealized_pnl_usd": "43.1900"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```

## GLOBAL-TREND 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_global.db
{"results": [{"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"SPY": "0.251463"}, "signal_target_weights": {"SPY": "0.251463"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "12000.0", "investable_usd": "11880.000", "active_target_count": 1, "funded_target_count": 1, "funded_target_ratio": "1", "whole_share_eligible_target_count": 1, "funded_whole_share_target_count": 1, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"SPY": "0.251463"}, "holdings": {"SPY": 3}, "prices": {"SPY": "769.6400"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"SPY": 3}, "projected_weights": {"SPY": "0.19241"}, "l1_weight_error": "0.05653837", "max_leg_weight_error": "0.05653837", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=40)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "9604.6300", "total_market_value_usd": "2308.9200", "total_nav_usd": "11913.5500", "total_unrealized_pnl_usd": "18.5100", "broker_reported_nav_usd": null, "holdings": [{"symbol": "SPY", "qty": 3, "avg_cost_usd": "763.4700", "mark_price_usd": "769.6400", "market_value_usd": "2308.9200", "marked": true, "weight_pct": "19.38062122541140130355771370", "unrealized_pnl_usd": "18.5100"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```

## GLOBAL-TREND-FIXED 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_globalfixed.db
{"results": [{"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend-fixed", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"SPY": "0.333334"}, "signal_target_weights": {"SPY": "0.333334"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "12000.0", "investable_usd": "11880.000", "active_target_count": 1, "funded_target_count": 1, "funded_target_ratio": "1", "whole_share_eligible_target_count": 1, "funded_whole_share_target_count": 1, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"SPY": "0.333334"}, "holdings": {"SPY": 5}, "prices": {"SPY": "769.6400"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"SPY": 5}, "projected_weights": {"SPY": "0.3206833333333333333333333333"}, "l1_weight_error": "0.0093173266666666666666666667", "max_leg_weight_error": "0.0093173266666666666666666667", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=3496)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "7739.9300", "total_market_value_usd": "3848.2000", "total_nav_usd": "11588.1300", "total_unrealized_pnl_usd": "30.8500", "broker_reported_nav_usd": null, "holdings": [{"symbol": "SPY", "qty": 5, "avg_cost_usd": "763.4700", "mark_price_usd": "769.6400", "market_value_usd": "3848.2000", "marked": true, "weight_pct": "33.20811899762947084646099069", "unrealized_pnl_usd": "30.8500"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```

## GLOBAL-TREND-WIDE 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_wide.db
{"results": [{"symbol": "DBC", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "EEM", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "EFA", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "LQD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "QQQ", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "TLT", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "UUP", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "VNQ", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend-wide", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"QQQ": "0.048560", "SPY": "0.075841", "DBC": "0.043850", "EEM": "0.035933", "UUP": "0.171543", "EFA": "0.043657"}, "signal_target_weights": {"QQQ": "0.048560", "SPY": "0.075841", "DBC": "0.043850", "EEM": "0.035933", "UUP": "0.171543", "EFA": "0.043657"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "12000.0", "investable_usd": "11880.000", "active_target_count": 6, "funded_target_count": 5, "funded_target_ratio": "0.8333333333333333333333333333", "whole_share_eligible_target_count": 5, "funded_whole_share_target_count": 5, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {"QQQ": {"target_notional_usd": "576.892800000", "one_share_price_usd": "749.5800"}}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"QQQ": "0.048560", "SPY": "0.075841", "DBC": "0.043850", "EEM": "0.035933", "UUP": "0.171543", "EFA": "0.043657"}, "holdings": {"DBC": 16, "EEM": 4, "EFA": 6, "SPY": 1, "UUP": 53}, "prices": {"DBC": "32.5400", "EEM": "67.6700", "EFA": "103.9600", "QQQ": "749.5800", "SPY": "769.6400", "UUP": "28.8900"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"QQQ": 0, "SPY": 1, "DBC": 16, "EEM": 4, "UUP": 53, "EFA": 6}, "projected_weights": {"QQQ": "0.000", "SPY": "0.06413666666666666666666666667", "DBC": "0.04338666666666666666666666667", "EEM": "0.02255666666666666666666666667", "UUP": "0.1275975", "EFA": "0.05198"}, "l1_weight_error": "0.1230518000000000000000000000", "max_leg_weight_error": "0.04807440", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=48)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "8281.2900", "total_market_value_usd": "3715.8900", "total_nav_usd": "11997.1800", "total_unrealized_pnl_usd": "62.8800", "broker_reported_nav_usd": null, "holdings": [{"symbol": "DBC", "qty": 16, "avg_cost_usd": "30.9400", "mark_price_usd": "32.5400", "market_value_usd": "520.6400", "marked": true, "weight_pct": "4.339686492992519908845245299", "unrealized_pnl_usd": "25.6000"}, {"symbol": "EEM", "qty": 4, "avg_cost_usd": "66.1100", "mark_price_usd": "67.6700", "market_value_usd": "270.6800", "marked": true, "weight_pct": "2.256196872931805640992299857", "unrealized_pnl_usd": "6.2400"}, {"symbol": "EFA", "qty": 6, "avg_cost_usd": "108.0300", "mark_price_usd": "103.9600", "market_value_usd": "623.7600", "marked": true, "weight_pct": "5.199221817127024850839947388", "unrealized_pnl_usd": "-24.4200"}, {"symbol": "SPY", "qty": 1, "avg_cost_usd": "763.4700", "mark_price_usd": "769.6400", "market_value_usd": "769.6400", "marked": true, "weight_pct": "6.415174232611330329294050769", "unrealized_pnl_usd": "6.1700"}, {"symbol": "UUP", "qty": 53, "avg_cost_usd": "27.9600", "mark_price_usd": "28.8900", "market_value_usd": "1531.1700", "marked": true, "weight_pct": "12.76274924607282711437187739", "unrealized_pnl_usd": "49.2900"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```
