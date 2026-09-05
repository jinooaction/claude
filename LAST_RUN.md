# forward 페이퍼 A/B 토너먼트 — 최신 실행 (현재 데이터, 돈 안 움직임)

추세 필터 **ON**(canary-portfolio.toml / forward_v2_trend.db) vs **OFF**
(canary-portfolio-notrend.toml / forward_v2_notrend.db). 전용 DB 로 격리된
두 페이퍼 트랙을 스펙 035 forward-verdict 로 각각 판정한다. PAPER 전용 — 실주문 0건.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | 0ff5e687abbaac29109e13863a8c9b63b522f531 |
| trigger | schedule |
| timestamp_utc | 2026-09-05T00:19:17Z |
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
  "code_commit": "0ff5e687abbaac29109e13863a8c9b63b522f531",
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

> ⏳ 아직 비교 불가 — 비교 가능 트랙 0개(모두 관측 부족, 누적 중). 최다 관측: 추세 필터 ON (드로다운 방어)(9/20).
>
> 관측이 최소(스펙 035 기본 20)를 넘는 트랙이 나오면 그때 챔피언을 가린다. 지표는 그전까지 잠정치(통계적으로 노이즈) — 챔피언 선언 안 함(거짓 자신만만 금지).

| # | 트랙 | 판정 | 관측 | 칼마 | 샤프 | 초과수익% | 낙폭% | 상태 |
|--:|------|:----:|-----:|-----:|-----:|----------:|------:|:----:|
| 1 | 추세 필터 ON (드로다운 방어) | ⏳ INSUFFICIENT_DATA | 9/20 | — | — | — | 1.87 | ⏳ |
| 2 | 추세 필터 OFF (대조군) | ⏳ INSUFFICIENT_DATA | 9/20 | — | — | — | 1.87 | ⏳ |
| 3 | 위험관리 베타 (스펙 042) | ⏳ INSUFFICIENT_DATA | 9/20 | — | — | — | 1.42 | ⏳ |
| 4 | 멀티에셋 분산 추세 (스펙 043) | ⏳ INSUFFICIENT_DATA | 9/20 | — | — | — | 0.54 | ⏳ |
| 5 | 글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD) 🏠 | ⏳ INSUFFICIENT_DATA | 9/20 | — | — | — | 0.69 | ⏳ |
| 6 | 글로벌 3자산 추세 고정등가중 (재지정 후보) | ⏳ INSUFFICIENT_DATA | 9/20 | — | — | — | 2.59 | ⏳ |
| 7 | 글로벌 분산 추세 확대 (11 슬리브) | ⏳ INSUFFICIENT_DATA | 9/20 | — | — | — | 0.08 | ⏳ |

🏠 라이브 검증 트랙 · 👑 챔피언(비교 가능 EDGE_CONFIRMED 1위) · 🚀 도전자(검증 트랙을 앞섬). 잠정(⏳)은 관측이 더 쌓여야 비교 가능 — 지표는 잠정치.

## 후보 관측 품질

✅ **OK** — 모든 후보 판정이 읽혔고 관측 누적이 같은 속도로 진행 중.

| 전체 | 판정 읽힘 | 판정 없음 | 최소 관측 | 최대 관측 | 뒤처진 트랙 |
|-----:|----------:|----------:|----------:|----------:|-------------|
| 7 | 7 | 0 | 9 | 9 | — |

⚠ 이건 종합 보고다(읽기 전용). 라이브 전략은 자동으로 안 바뀐다 — 재지정은 운영자 게이트(헌법 X.4). 검증=배치 정합이라 도전자가 라이브가 되려면 라이브 설정 지문을 그 트랙으로 맞추는 운영자/세션 결정이 필요하다.

## 🧾 리더보드 결정 JSON (기계 판독 단일 증거)

> 아래 JSON 은 위 리더보드와 같은 순수 코어 출력이다. 재지정·감시 루프는
> 가능하면 이 기계 판독 증거를 우선 소비해야 한다. 특히 known_count,
> unknown_count, observation_health 로 후보 관측 품질을 분리해 본다.

```json
{"schema_version": "1.0", "as_of_utc": "2026-09-05T00:19:17.216010+00:00", "champion_key": null, "incumbent_key": "global", "challenger_key": null, "comparable_count": 0, "adjusted_dsr_threshold": null, "champion_multiplicity_robust": null, "track_count": 7, "known_count": 7, "unknown_count": 0, "max_n_obs": 9, "min_n_obs": 9, "lagging_keys": [], "observation_health": "OK", "observation_note": "모든 후보 판정이 읽혔고 관측 누적이 같은 속도로 진행 중.", "headline": "⏳ 아직 비교 불가 — 비교 가능 트랙 0개(모두 관측 부족, 누적 중). 최다 관측: 추세 필터 ON (드로다운 방어)(9/20).", "note": "관측이 최소(스펙 035 기본 20)를 넘는 트랙이 나오면 그때 챔피언을 가린다. 지표는 그전까지 잠정치(통계적으로 노이즈) — 챔피언 선언 안 함(거짓 자신만만 금지).", "rows": [{"key": "trend", "label": "추세 필터 ON (드로다운 방어)", "is_incumbent": false, "verdict": "INSUFFICIENT_DATA", "n_obs": 9, "min_obs": 20, "comparability": "PREMATURE", "rank": 1, "calmar": null, "sharpe": null, "total_return_pct": "-0.268292", "max_drawdown_pct": "1.865816", "excess_return_pct": null, "dsr": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": null, "dsr_threshold": "0.95", "universe_size": 501, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES"]}, {"key": "notrend", "label": "추세 필터 OFF (대조군)", "is_incumbent": false, "verdict": "INSUFFICIENT_DATA", "n_obs": 9, "min_obs": 20, "comparability": "PREMATURE", "rank": 2, "calmar": null, "sharpe": null, "total_return_pct": "-0.268292", "max_drawdown_pct": "1.865816", "excess_return_pct": null, "dsr": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": null, "dsr_threshold": "0.95", "universe_size": 501, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES"]}, {"key": "rmbeta", "label": "위험관리 베타 (스펙 042)", "is_incumbent": false, "verdict": "INSUFFICIENT_DATA", "n_obs": 9, "min_obs": 20, "comparability": "PREMATURE", "rank": 3, "calmar": null, "sharpe": null, "total_return_pct": "1.234667", "max_drawdown_pct": "1.421326", "excess_return_pct": null, "dsr": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": null, "dsr_threshold": "0.95", "universe_size": 2, "universe": ["SPY", "QQQ"]}, {"key": "multiasset", "label": "멀티에셋 분산 추세 (스펙 043)", "is_incumbent": false, "verdict": "INSUFFICIENT_DATA", "n_obs": 9, "min_obs": 20, "comparability": "PREMATURE", "rank": 4, "calmar": null, "sharpe": null, "total_return_pct": "0.392000", "max_drawdown_pct": "0.541258", "excess_return_pct": null, "dsr": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": null, "dsr_threshold": "0.95", "universe_size": 2, "universe": ["SPY", "IEF"]}, {"key": "global", "label": "글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD)", "is_incumbent": true, "verdict": "INSUFFICIENT_DATA", "n_obs": 9, "min_obs": 20, "comparability": "PREMATURE", "rank": 5, "calmar": null, "sharpe": null, "total_return_pct": "-0.225667", "max_drawdown_pct": "0.694103", "excess_return_pct": null, "dsr": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": null, "dsr_threshold": "0.95", "universe_size": 3, "universe": ["SPY", "IEF", "GLD"]}, {"key": "globalfixed", "label": "글로벌 3자산 추세 고정등가중 (재지정 후보)", "is_incumbent": false, "verdict": "INSUFFICIENT_DATA", "n_obs": 9, "min_obs": 20, "comparability": "PREMATURE", "rank": 6, "calmar": null, "sharpe": null, "total_return_pct": "-1.244833", "max_drawdown_pct": "2.588918", "excess_return_pct": null, "dsr": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": null, "dsr_threshold": "0.95", "universe_size": 3, "universe": ["SPY", "IEF", "GLD"]}, {"key": "wide", "label": "글로벌 분산 추세 확대 (11 슬리브)", "is_incumbent": false, "verdict": "INSUFFICIENT_DATA", "n_obs": 9, "min_obs": 20, "comparability": "PREMATURE", "rank": 7, "calmar": null, "sharpe": null, "total_return_pct": "0.096500", "max_drawdown_pct": "0.078739", "excess_return_pct": null, "dsr": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "psr_vs_benchmark": null, "dsr_threshold": "0.95", "universe_size": 11, "universe": ["SPY", "QQQ", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD"]}]}
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
# 일일 전략 모니터 (as of 2026-08) — 읽기 전용, 돈 0 이동

① 엣지(분산 추세)가 최근에도 유효한가:
   최근 5년 샤프 +1.77 | 최근 10년 샤프 +1.79 | 최근 5년 낙폭 +3.63%

② 분산 가정이 지금 신뢰 가능한가 (주식·채권 상관):
   현재 -0.01 | 최근 5년 평균 +0.12 → 판정: DIVERSIFICATION_WEAKENED

③ 낙폭 예산 15%에서 레버리지 복리 권고 (최근 25년 기준):
   무레버 복리 +7.91% → 권고 L=2.0 → 복리 11.5%/년 (낙폭 13%)

④ 오늘 추세 신호 (S&P vs 10개월 SMA):
   투자(추세 위) (갭 +8.48%)

⚠ 이건 감시 보고다. 라이브 레버리지/무장은 운영자 게이트(헌법 X.4).

=== 낙폭 예산 20% (레버리지 권고 비교) ===
{"as_of": "2026-08", "edge": {"diversified_5y_sharpe": 1.765, "diversified_10y_sharpe": 1.792, "diversified_5y_maxdd_pct": 3.629}, "regime": {"corr_current": -0.015, "corr_recent_5y_avg": 0.123, "verdict": "DIVERSIFICATION_WEAKENED"}, "leverage_recommendation": {"dd_budget_pct": 20.0, "window_years": 25, "unlevered_cagr_pct": 7.914, "leverage": 3.0, "cagr_pct": 14.953, "maxdd_pct": 19.591}, "today_signal": {"in_market": true, "gap_pct": 8.483}}
```

## 🧭 판정 — 추세 필터 ON (drawdown 방어 오버레이)

> EDGE_CONFIRMED 만이 운영자 라이브 게이트(헌법 X.4)에 올릴 증거(자동 배포 아님).
> INSUFFICIENT_DATA 면 NAV 관측이 더 쌓여야 한다(≈20 거래일) — 정상.

```json
{"schema_version": "1.2", "verdict": "INSUFFICIENT_DATA", "reason": "\uad00\uce21 9\uac1c < \ucd5c\uc18c 20\uac1c \u2014 \uc0e4\ud504\uac00 \ud1b5\uacc4\uc801\uc73c\ub85c \ubb34\uc758\ubbf8", "n_obs": 9, "min_obs_required": 20, "strategy_sharpe_annual": null, "strategy_total_return_pct": "-0.268292", "strategy_max_drawdown_pct": "1.865816", "strategy_calmar": null, "benchmark_sharpe_annual": null, "benchmark_total_return_pct": null, "benchmark_max_drawdown_pct": null, "benchmark_calmar": null, "excess_return_pct": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": null, "psr_vs_benchmark": null, "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 10, "legacy_snapshots_excluded": 0, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A", "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT", "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX", "BDX", "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BNY", "BA", "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CPT", "CPB", "COF", "CAH", "CCL", "CARR", "CVNA", "CASY", "CAT", "CBOE", "CBRE", "CDW", "COR", "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD", "CIEN", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS", "KO", "CTSH", "COHR", "COIN", "CL", "CMCSA", "FIX", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP", "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI", "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM", "FANG", "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI", "DTE", "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW", "EA", "ELV", "EME", "EMR", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ERIE", "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB", "FSLR", "FE", "FISV", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA", "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON", "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "IBKR", "ICE", "IFF", "IP", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR", "LHX", "LH", "LRCX", "LVS", "LDOS", "LEN", "LII", "LLY", "LIN", "LYV", "LMT", "L", "LOW", "LULU", "LITE", "LYB", "MTB", "MPC", "MAR", "MRSH", "MLM", "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PSKY", "PH", "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTC", "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL", "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC", "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL", "TXT", "TMO", "TJX", "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VRT", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WY", "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH", "ZTS"]}
```

## 🧭 판정 — 추세 필터 OFF (대조군)

```json
{"schema_version": "1.2", "verdict": "INSUFFICIENT_DATA", "reason": "\uad00\uce21 9\uac1c < \ucd5c\uc18c 20\uac1c \u2014 \uc0e4\ud504\uac00 \ud1b5\uacc4\uc801\uc73c\ub85c \ubb34\uc758\ubbf8", "n_obs": 9, "min_obs_required": 20, "strategy_sharpe_annual": null, "strategy_total_return_pct": "-0.268292", "strategy_max_drawdown_pct": "1.865816", "strategy_calmar": null, "benchmark_sharpe_annual": null, "benchmark_total_return_pct": null, "benchmark_max_drawdown_pct": null, "benchmark_calmar": null, "excess_return_pct": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": null, "psr_vs_benchmark": null, "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 10, "legacy_snapshots_excluded": 0, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A", "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT", "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX", "BDX", "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BNY", "BA", "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CPT", "CPB", "COF", "CAH", "CCL", "CARR", "CVNA", "CASY", "CAT", "CBOE", "CBRE", "CDW", "COR", "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD", "CIEN", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS", "KO", "CTSH", "COHR", "COIN", "CL", "CMCSA", "FIX", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP", "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI", "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM", "FANG", "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI", "DTE", "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW", "EA", "ELV", "EME", "EMR", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ERIE", "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB", "FSLR", "FE", "FISV", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA", "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON", "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "IBKR", "ICE", "IFF", "IP", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR", "LHX", "LH", "LRCX", "LVS", "LDOS", "LEN", "LII", "LLY", "LIN", "LYV", "LMT", "L", "LOW", "LULU", "LITE", "LYB", "MTB", "MPC", "MAR", "MRSH", "MLM", "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PSKY", "PH", "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTC", "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL", "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC", "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL", "TXT", "TMO", "TJX", "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VRT", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WY", "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH", "ZTS"]}
```

> 두 판정을 나란히 비교: ON 의 max_drawdown_pct·sharpe·excess 가 OFF 보다
> 나으면 추세 필터가 *실제로* 도움이 된다는 격리된 증거다.

## 🛡️ 판정 — 위험관리 베타 (추세 게이트 광범위 베타, 스펙 042)

> SPY·QQQ 를 10개월 추세 위일 때만 보유(아래면 현금). 종목 선택이 아니라 베타의
> 자본 방어. 우리 KIS 체결로 forward 실적을 쌓아 *확신을 번다*(운영자 2026-06-05).
> INSUFFICIENT_DATA 면 NAV 관측이 더 쌓여야 함(정상). 200일 미만이면 추세 미확정 →
> on_insufficient=cash 라 현금 보유(보수적). 라이브 전환은 운영자 게이트(헌법 X.4).

```json
{"schema_version": "1.2", "verdict": "INSUFFICIENT_DATA", "reason": "\uad00\uce21 9\uac1c < \ucd5c\uc18c 20\uac1c \u2014 \uc0e4\ud504\uac00 \ud1b5\uacc4\uc801\uc73c\ub85c \ubb34\uc758\ubbf8", "n_obs": 9, "min_obs_required": 20, "strategy_sharpe_annual": null, "strategy_total_return_pct": "1.234667", "strategy_max_drawdown_pct": "1.421326", "strategy_calmar": null, "benchmark_sharpe_annual": null, "benchmark_total_return_pct": null, "benchmark_max_drawdown_pct": null, "benchmark_calmar": null, "excess_return_pct": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": null, "psr_vs_benchmark": null, "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 10, "legacy_snapshots_excluded": 0, "universe": ["SPY", "QQQ"]}
```

## 🌐 판정 — 멀티에셋 분산 추세 (비상관 자산 합성, 스펙 043)

> 주식(SPY) + 채권(IEF) 을 각자 추세 위일 때만 보유. ARM C(둘 다 주식)와 달리
> *비상관 자산*을 합쳐 분산 이득을 노린다(스펙 043: 단일 주식 추세 샤프 1.18~1.43
> → 분산 추세 1.58~1.81, 낙폭 절반, Shiller 1871~ 검증). INSUFFICIENT_DATA 면
> NAV 관측이 더 쌓여야 함(정상). 라이브 전환은 운영자 게이트(헌법 X.4).

```json
{"schema_version": "1.2", "verdict": "INSUFFICIENT_DATA", "reason": "\uad00\uce21 9\uac1c < \ucd5c\uc18c 20\uac1c \u2014 \uc0e4\ud504\uac00 \ud1b5\uacc4\uc801\uc73c\ub85c \ubb34\uc758\ubbf8", "n_obs": 9, "min_obs_required": 20, "strategy_sharpe_annual": null, "strategy_total_return_pct": "0.392000", "strategy_max_drawdown_pct": "0.541258", "strategy_calmar": null, "benchmark_sharpe_annual": null, "benchmark_total_return_pct": null, "benchmark_max_drawdown_pct": null, "benchmark_calmar": null, "excess_return_pct": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": null, "psr_vs_benchmark": null, "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 10, "legacy_snapshots_excluded": 0, "universe": ["SPY", "IEF"]}
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
{"schema_version": "1.2", "verdict": "INSUFFICIENT_DATA", "reason": "\uad00\uce21 9\uac1c < \ucd5c\uc18c 20\uac1c \u2014 \uc0e4\ud504\uac00 \ud1b5\uacc4\uc801\uc73c\ub85c \ubb34\uc758\ubbf8", "n_obs": 9, "min_obs_required": 20, "strategy_sharpe_annual": null, "strategy_total_return_pct": "-0.225667", "strategy_max_drawdown_pct": "0.694103", "strategy_calmar": null, "benchmark_sharpe_annual": null, "benchmark_total_return_pct": null, "benchmark_max_drawdown_pct": null, "benchmark_calmar": null, "excess_return_pct": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": null, "psr_vs_benchmark": null, "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 10, "legacy_snapshots_excluded": 0, "universe": ["SPY", "IEF", "GLD"]}
```

## ⚖ 판정 — 글로벌 3자산 추세 고정(등가중) 재지정 후보 (스펙 047/050 후속)

> 라이브 검증 트랙과 weight_scheme 만 다른 등가중 변형. 깊은 분석은 등가중이
> 캡 안 무레버 복리 +1.3~2.3%p 높다고 봤으나 낙폭이 사다리 강등선(10%)에 더
> 가깝다 — 이 트랙이 *일별* 낙폭/강등 빈도를 실측해 재지정 안전성을 답한다.
> EDGE_CONFIRMED + 지문 정합을 벌면 운영자가 재지정 결정(헌법 X.4). 돈 0·페이퍼.

```json
{"schema_version": "1.2", "verdict": "INSUFFICIENT_DATA", "reason": "\uad00\uce21 9\uac1c < \ucd5c\uc18c 20\uac1c \u2014 \uc0e4\ud504\uac00 \ud1b5\uacc4\uc801\uc73c\ub85c \ubb34\uc758\ubbf8", "n_obs": 9, "min_obs_required": 20, "strategy_sharpe_annual": null, "strategy_total_return_pct": "-1.244833", "strategy_max_drawdown_pct": "2.588918", "strategy_calmar": null, "benchmark_sharpe_annual": null, "benchmark_total_return_pct": null, "benchmark_max_drawdown_pct": null, "benchmark_calmar": null, "excess_return_pct": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": null, "psr_vs_benchmark": null, "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 10, "legacy_snapshots_excluded": 0, "universe": ["SPY", "IEF", "GLD"]}
```

## 🌍 판정 — 글로벌 분산 추세 확대 유니버스 (11 슬리브, 계획 ③)

> 검증된 메커니즘(역변동성 + 다중 속도 추세 앙상블) 그대로, 베팅의 폭만
> 3 → 11 슬리브(주식 SPY·QQQ·EFA·EEM / 채권 IEF·TLT·LQD / 실물 GLD·DBC·VNQ
> / 통화 UUP). 성과 ≈ 질 × √N — 제약 안에서 가장 큰 지렛대. ARM E(3자산)와
> 나란히 비교하면 '폭 확장이 우리 체결 기준 forward 로도 이득인가'의 격리된
> 답. 라이브는 검증된 3자산 유지 — 이 트랙이 EDGE_CONFIRMED 를 벌어야 재지정
> 후보가 된다(검증=배치 정합, 헌법 X.4 v5.0.0 사다리).

```json
{"schema_version": "1.2", "verdict": "INSUFFICIENT_DATA", "reason": "\uad00\uce21 9\uac1c < \ucd5c\uc18c 20\uac1c \u2014 \uc0e4\ud504\uac00 \ud1b5\uacc4\uc801\uc73c\ub85c \ubb34\uc758\ubbf8", "n_obs": 9, "min_obs_required": 20, "strategy_sharpe_annual": null, "strategy_total_return_pct": "0.096500", "strategy_max_drawdown_pct": "0.078739", "strategy_calmar": null, "benchmark_sharpe_annual": null, "benchmark_total_return_pct": null, "benchmark_max_drawdown_pct": null, "benchmark_calmar": null, "excess_return_pct": null, "beats_benchmark_calmar": false, "significance_method": "paired_active_return_psr_v1", "active_information_ratio_annual": null, "psr_vs_benchmark": null, "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 10, "legacy_snapshots_excluded": 0, "universe": ["SPY", "QQQ", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD", "DBC", "VNQ", "UUP"]}
```

## TREND-ON 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_trend.db
{"results": [{"symbol": "COHR", "exchange": "NYS", "fetched": 887, "inserted": 1}, {"symbol": "COO", "exchange": "NAS", "fetched": 739, "inserted": 1}, {"symbol": "CPAY", "exchange": "NYS", "fetched": 615, "inserted": 1}, {"symbol": "CPB", "exchange": "NAS", "fetched": 514, "inserted": 1}, {"symbol": "BNY", "exchange": "NYS", "fetched": 74, "inserted": 1}]}
{"portfolio_id": "forward-paper-canary", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "signal_target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": false, "capital_usd": "12000.0", "investable_usd": "11400.000", "active_target_count": 10, "funded_target_count": 10, "funded_target_ratio": "1", "whole_share_eligible_target_count": 10, "funded_whole_share_target_count": 10, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.95", "target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "holdings": {"ABNB": 3, "ADP": 2, "AMAT": 1, "AMD": 1, "ANET": 3, "BAC": 9, "BKNG": 2, "BX": 4, "CRWD": 3, "CSCO": 5}, "prices": {"ABNB": "181.9400", "ADP": "277.6200", "AMAT": "454.7100", "AMD": "477.5700", "ANET": "193.7800", "BAC": "62.6800", "BKNG": "193.2900", "BX": "136.1500", "CRWD": "213.1000", "CSCO": "109.2000"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "5.0", "per_symbol_pct": "25.0", "global_exposure_pct": "80.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"AMD": 1, "CRWD": 3, "ANET": 3, "ABNB": 3, "CSCO": 5, "AMAT": 1, "ADP": 2, "BX": 4, "BKNG": 2, "BAC": 9}, "projected_weights": {"AMD": "0.0397975", "CRWD": "0.053275", "ANET": "0.048445", "ABNB": "0.045485", "CSCO": "0.0455", "AMAT": "0.0378925", "ADP": "0.04627", "BX": "0.04538333333333333333333333333", "BKNG": "0.032215", "BAC": "0.04701"}, "l1_weight_error": "0.5087266666666666666666666667", "max_leg_weight_error": "0.06278500", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": false, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": ["l1_weight_error"]}, "results": [], "withheld_orders": []}
{"schema_version": "1.0", "source": "ledger", "cash_usd": "6672.5250", "total_market_value_usd": "5295.2800", "total_nav_usd": "11967.8050", "total_unrealized_pnl_usd": "-32.1950", "broker_reported_nav_usd": null, "holdings": [{"symbol": "ABNB", "qty": 3, "avg_cost_usd": "190.2100", "mark_price_usd": "181.9400", "market_value_usd": "545.8200", "marked": true, "weight_pct": "4.560736074827422405361718377", "unrealized_pnl_usd": "-24.8100"}, {"symbol": "ADP", "qty": 2, "avg_cost_usd": "283.0100", "mark_price_usd": "277.6200", "market_value_usd": "555.2400", "marked": true, "weight_pct": "4.639447250352090462703895994", "unrealized_pnl_usd": "-10.7800"}, {"symbol": "AMAT", "qty": 1, "avg_cost_usd": "484.1900", "mark_price_usd": "454.7100", "market_value_usd": "454.7100", "marked": true, "weight_pct": "3.799443590533101099157280721", "unrealized_pnl_usd": "-29.4800"}, {"symbol": "AMD", "qty": 1, "avg_cost_usd": "456.7450", "mark_price_usd": "477.5700", "market_value_usd": "477.5700", "marked": true, "weight_pct": "3.990456061073856066337979270", "unrealized_pnl_usd": "20.8250"}, {"symbol": "ANET", "qty": 3, "avg_cost_usd": "188.1500", "mark_price_usd": "193.7800", "market_value_usd": "581.3400", "marked": true, "weight_pct": "4.857532354512794952792095125", "unrealized_pnl_usd": "16.8900"}, {"symbol": "BAC", "qty": 9, "avg_cost_usd": "62.3300", "mark_price_usd": "62.6800", "market_value_usd": "564.1200", "marked": true, "weight_pct": "4.713646320273433599561490181", "unrealized_pnl_usd": "3.1500"}, {"symbol": "BKNG", "qty": 2, "avg_cost_usd": "213.3600", "mark_price_usd": "193.2900", "market_value_usd": "386.5800", "marked": true, "weight_pct": "3.230166266913606964685671266", "unrealized_pnl_usd": "-40.1400"}, {"symbol": "BX", "qty": 4, "avg_cost_usd": "143.6400", "mark_price_usd": "136.1500", "market_value_usd": "544.6000", "marked": true, "weight_pct": "4.550542058464354992415066923", "unrealized_pnl_usd": "-29.9600"}, {"symbol": "CRWD", "qty": 3, "avg_cost_usd": "190.6800", "mark_price_usd": "213.1000", "market_value_usd": "639.3000", "marked": true, "weight_pct": "5.341831689269669751470716644", "unrealized_pnl_usd": "67.2600"}, {"symbol": "CSCO", "qty": 5, "avg_cost_usd": "110.2300", "mark_price_usd": "109.2000", "market_value_usd": "546.0000", "marked": true, "weight_pct": "4.562240110028530712189912854", "unrealized_pnl_usd": "-5.1500"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=30)
```

## TREND-OFF 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_notrend.db
{"results": [{"symbol": "COHR", "exchange": "NYS", "fetched": 887, "inserted": 1}, {"symbol": "COO", "exchange": "NAS", "fetched": 739, "inserted": 1}, {"symbol": "CPAY", "exchange": "NYS", "fetched": 615, "inserted": 1}, {"symbol": "CPB", "exchange": "NAS", "fetched": 514, "inserted": 1}, {"symbol": "BNY", "exchange": "NYS", "fetched": 74, "inserted": 1}]}
{"portfolio_id": "forward-paper-canary-notrend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "signal_target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": false, "capital_usd": "12000.0", "investable_usd": "11400.000", "active_target_count": 10, "funded_target_count": 10, "funded_target_ratio": "1", "whole_share_eligible_target_count": 10, "funded_whole_share_target_count": 10, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.95", "target_weights": {"AMD": "0.100000", "CRWD": "0.100000", "ANET": "0.100000", "ABNB": "0.100000", "CSCO": "0.100000", "AMAT": "0.100000", "ADP": "0.100000", "BX": "0.100000", "BKNG": "0.100000", "BAC": "0.100000"}, "holdings": {"ABNB": 3, "ADP": 2, "AMAT": 1, "AMD": 1, "ANET": 3, "BAC": 9, "BKNG": 2, "BX": 4, "CRWD": 3, "CSCO": 5}, "prices": {"ABNB": "181.9400", "ADP": "277.6200", "AMAT": "454.7100", "AMD": "477.5700", "ANET": "193.7800", "BAC": "62.6800", "BKNG": "193.2900", "BX": "136.1500", "CRWD": "213.1000", "CSCO": "109.2000"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "5.0", "per_symbol_pct": "25.0", "global_exposure_pct": "80.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"AMD": 1, "CRWD": 3, "ANET": 3, "ABNB": 3, "CSCO": 5, "AMAT": 1, "ADP": 2, "BX": 4, "BKNG": 2, "BAC": 9}, "projected_weights": {"AMD": "0.0397975", "CRWD": "0.053275", "ANET": "0.048445", "ABNB": "0.045485", "CSCO": "0.0455", "AMAT": "0.0378925", "ADP": "0.04627", "BX": "0.04538333333333333333333333333", "BKNG": "0.032215", "BAC": "0.04701"}, "l1_weight_error": "0.5087266666666666666666666667", "max_leg_weight_error": "0.06278500", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": false, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": ["l1_weight_error"]}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=30)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "6672.5250", "total_market_value_usd": "5295.2800", "total_nav_usd": "11967.8050", "total_unrealized_pnl_usd": "-32.1950", "broker_reported_nav_usd": null, "holdings": [{"symbol": "ABNB", "qty": 3, "avg_cost_usd": "190.2100", "mark_price_usd": "181.9400", "market_value_usd": "545.8200", "marked": true, "weight_pct": "4.560736074827422405361718377", "unrealized_pnl_usd": "-24.8100"}, {"symbol": "ADP", "qty": 2, "avg_cost_usd": "283.0100", "mark_price_usd": "277.6200", "market_value_usd": "555.2400", "marked": true, "weight_pct": "4.639447250352090462703895994", "unrealized_pnl_usd": "-10.7800"}, {"symbol": "AMAT", "qty": 1, "avg_cost_usd": "484.1900", "mark_price_usd": "454.7100", "market_value_usd": "454.7100", "marked": true, "weight_pct": "3.799443590533101099157280721", "unrealized_pnl_usd": "-29.4800"}, {"symbol": "AMD", "qty": 1, "avg_cost_usd": "456.7450", "mark_price_usd": "477.5700", "market_value_usd": "477.5700", "marked": true, "weight_pct": "3.990456061073856066337979270", "unrealized_pnl_usd": "20.8250"}, {"symbol": "ANET", "qty": 3, "avg_cost_usd": "188.1500", "mark_price_usd": "193.7800", "market_value_usd": "581.3400", "marked": true, "weight_pct": "4.857532354512794952792095125", "unrealized_pnl_usd": "16.8900"}, {"symbol": "BAC", "qty": 9, "avg_cost_usd": "62.3300", "mark_price_usd": "62.6800", "market_value_usd": "564.1200", "marked": true, "weight_pct": "4.713646320273433599561490181", "unrealized_pnl_usd": "3.1500"}, {"symbol": "BKNG", "qty": 2, "avg_cost_usd": "213.3600", "mark_price_usd": "193.2900", "market_value_usd": "386.5800", "marked": true, "weight_pct": "3.230166266913606964685671266", "unrealized_pnl_usd": "-40.1400"}, {"symbol": "BX", "qty": 4, "avg_cost_usd": "143.6400", "mark_price_usd": "136.1500", "market_value_usd": "544.6000", "marked": true, "weight_pct": "4.550542058464354992415066923", "unrealized_pnl_usd": "-29.9600"}, {"symbol": "CRWD", "qty": 3, "avg_cost_usd": "190.6800", "mark_price_usd": "213.1000", "market_value_usd": "639.3000", "marked": true, "weight_pct": "5.341831689269669751470716644", "unrealized_pnl_usd": "67.2600"}, {"symbol": "CSCO", "qty": 5, "avg_cost_usd": "110.2300", "mark_price_usd": "109.2000", "market_value_usd": "546.0000", "marked": true, "weight_pct": "4.562240110028530712189912854", "unrealized_pnl_usd": "-5.1500"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```

## RISK-MANAGED-BETA 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_rmbeta.db
{"results": [{"symbol": "QQQ", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "risk-managed-beta", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"QQQ": "0.500000", "SPY": "0.500000"}, "signal_target_weights": {"QQQ": "0.500000", "SPY": "0.500000"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "12000.0", "investable_usd": "11880.000", "active_target_count": 2, "funded_target_count": 2, "funded_target_ratio": "1", "whole_share_eligible_target_count": 2, "funded_whole_share_target_count": 2, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"QQQ": "0.500000", "SPY": "0.500000"}, "holdings": {"QQQ": 8, "SPY": 7}, "prices": {"QQQ": "718.9600", "SPY": "770.1900"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"QQQ": 8, "SPY": 7}, "projected_weights": {"QQQ": "0.4793066666666666666666666667", "SPY": "0.4492775"}, "l1_weight_error": "0.0614158333333333333333333333", "max_leg_weight_error": "0.04572250", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=14)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "1005.1500", "total_market_value_usd": "11143.0100", "total_nav_usd": "12148.1600", "total_unrealized_pnl_usd": "148.1600", "broker_reported_nav_usd": null, "holdings": [{"symbol": "QQQ", "qty": 8, "avg_cost_usd": "706.3200", "mark_price_usd": "718.9600", "market_value_usd": "5751.6800", "marked": true, "weight_pct": "47.34610015014619497932197139", "unrealized_pnl_usd": "101.1200"}, {"symbol": "SPY", "qty": 7, "avg_cost_usd": "763.4700", "mark_price_usd": "770.1900", "market_value_usd": "5391.3300", "marked": true, "weight_pct": "44.37980731238310987013671206", "unrealized_pnl_usd": "47.0400"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```

## MULTI-ASSET-TREND 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_multiasset.db
{"results": [{"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "multi-asset-trend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"SPY": "0.500000"}, "signal_target_weights": {"SPY": "0.500000"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "12000.0", "investable_usd": "11880.000", "active_target_count": 1, "funded_target_count": 1, "funded_target_ratio": "1", "whole_share_eligible_target_count": 1, "funded_whole_share_target_count": 1, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"SPY": "0.500000"}, "holdings": {"SPY": 7}, "prices": {"SPY": "770.1900"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"SPY": 7}, "projected_weights": {"SPY": "0.4492775"}, "l1_weight_error": "0.04572250", "max_leg_weight_error": "0.04572250", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=12)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "6655.7100", "total_market_value_usd": "5391.3300", "total_nav_usd": "12047.0400", "total_unrealized_pnl_usd": "47.0400", "broker_reported_nav_usd": null, "holdings": [{"symbol": "SPY", "qty": 7, "avg_cost_usd": "763.4700", "mark_price_usd": "770.1900", "market_value_usd": "5391.3300", "marked": true, "weight_pct": "44.75232090206390947485855447", "unrealized_pnl_usd": "47.0400"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```

## GLOBAL-TREND 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_global.db
{"results": [{"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"SPY": "0.240232", "GLD": "0.052009"}, "signal_target_weights": {"SPY": "0.240232", "GLD": "0.052009"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "12000.0", "investable_usd": "11880.000", "active_target_count": 2, "funded_target_count": 2, "funded_target_ratio": "1", "whole_share_eligible_target_count": 2, "funded_whole_share_target_count": 2, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"SPY": "0.240232", "GLD": "0.052009"}, "holdings": {"GLD": 2, "SPY": 3}, "prices": {"GLD": "406.7700", "SPY": "770.1900"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"SPY": 3, "GLD": 2}, "projected_weights": {"SPY": "0.1925475", "GLD": "0.067795"}, "l1_weight_error": "0.06158827", "max_leg_weight_error": "0.04528218", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=18)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "8848.8100", "total_market_value_usd": "3124.1100", "total_nav_usd": "11972.9200", "total_unrealized_pnl_usd": "-19.6800", "broker_reported_nav_usd": null, "holdings": [{"symbol": "GLD", "qty": 2, "avg_cost_usd": "426.6900", "mark_price_usd": "406.7700", "market_value_usd": "813.5400", "marked": true, "weight_pct": "6.794833674659147476137817675", "unrealized_pnl_usd": "-39.8400"}, {"symbol": "SPY", "qty": 3, "avg_cost_usd": "763.4700", "mark_price_usd": "770.1900", "market_value_usd": "2310.5700", "marked": true, "weight_pct": "19.29829982994958623293231726", "unrealized_pnl_usd": "20.1600"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```

## GLOBAL-TREND-FIXED 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_globalfixed.db
{"results": [{"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend-fixed", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"SPY": "0.333334", "GLD": "0.166666"}, "signal_target_weights": {"SPY": "0.333334", "GLD": "0.166666"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "12000.0", "investable_usd": "11880.000", "active_target_count": 2, "funded_target_count": 2, "funded_target_ratio": "1", "whole_share_eligible_target_count": 2, "funded_whole_share_target_count": 2, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"SPY": "0.333334", "GLD": "0.166666"}, "holdings": {"GLD": 9, "SPY": 5}, "prices": {"GLD": "406.7700", "SPY": "770.1900"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"SPY": 5, "GLD": 9}, "projected_weights": {"SPY": "0.3209125", "GLD": "0.3050775"}, "l1_weight_error": "0.14916632", "max_leg_weight_error": "0.14007816", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=1458)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "4338.7400", "total_market_value_usd": "7511.8800", "total_nav_usd": "11850.6200", "total_unrealized_pnl_usd": "-145.6800", "broker_reported_nav_usd": null, "holdings": [{"symbol": "GLD", "qty": 9, "avg_cost_usd": "426.6900", "mark_price_usd": "406.7700", "market_value_usd": "3660.9300", "marked": true, "weight_pct": "30.89230774423616654656043313", "unrealized_pnl_usd": "-179.2800"}, {"symbol": "SPY", "qty": 5, "avg_cost_usd": "763.4700", "mark_price_usd": "770.1900", "market_value_usd": "3850.9500", "marked": true, "weight_pct": "32.49576815390249624070301807", "unrealized_pnl_usd": "33.6000"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```

## GLOBAL-TREND-WIDE 준비 로그 (backfill → rebalance → nav-snapshot)

```
measurement_epoch=v2-clean-unlevered db=data/forward_v2_wide.db
{"results": [{"symbol": "DBC", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "EEM", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "EFA", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "LQD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "QQQ", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "TLT", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "UUP", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "VNQ", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend-wide", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"QQQ": "0.046994", "EEM": "0.035835", "SPY": "0.073341", "DBC": "0.043720", "EFA": "0.057091", "VNQ": "0.052312", "UUP": "0.125192", "GLD": "0.015875"}, "signal_target_weights": {"QQQ": "0.046994", "EEM": "0.035835", "SPY": "0.073341", "DBC": "0.043720", "EFA": "0.057091", "VNQ": "0.052312", "UUP": "0.125192", "GLD": "0.015875"}, "execution_symbol_map": {}, "fundability": {"schema_version": "1.1", "fundable": true, "capital_usd": "12000.0", "investable_usd": "11880.000", "active_target_count": 8, "funded_target_count": 6, "funded_target_ratio": "0.75", "whole_share_eligible_target_count": 6, "funded_whole_share_target_count": 6, "funded_whole_share_target_ratio": "1", "whole_share_ineligible_targets": {"QQQ": {"target_notional_usd": "558.288720000", "one_share_price_usd": "718.9600"}, "GLD": {"target_notional_usd": "188.595000000", "one_share_price_usd": "406.7700"}}, "quote_coverage_ratio": "1", "invested_fraction": "0.99", "target_weights": {"QQQ": "0.046994", "EEM": "0.035835", "SPY": "0.073341", "DBC": "0.043720", "EFA": "0.057091", "VNQ": "0.052312", "UUP": "0.125192", "GLD": "0.015875"}, "holdings": {"DBC": 16, "EEM": 4, "EFA": 6, "SPY": 1, "UUP": 53, "VNQ": 8}, "prices": {"DBC": "31.9000", "EEM": "68.7000", "EFA": "108.3500", "GLD": "406.7700", "QQQ": "718.9600", "SPY": "770.1900", "UUP": "28.0800", "VNQ": "96.0200"}, "order_prices": {}, "planned_orders": [], "caps": {"per_trade_pct": "50.0", "per_symbol_pct": "60.0", "global_exposure_pct": "100.0", "canary_capital_pct": "5.0", "canary_min_duration_days": 10, "canary_acceptance_drawdown_pct": "3.0", "circuit_breaker_enabled": true, "daily_loss_limit_pct": "10", "max_total_drawdown_pct": "20"}, "effective_side": "both", "projected_quantities": {"QQQ": 0, "EEM": 4, "SPY": 1, "DBC": 16, "EFA": 6, "VNQ": 8, "UUP": 53, "GLD": 0}, "projected_weights": {"QQQ": "0.000", "EEM": "0.0229", "SPY": "0.0641825", "DBC": "0.04253333333333333333333333333", "EFA": "0.054175", "VNQ": "0.06401333333333333333333333333", "UUP": "0.12402", "GLD": "0.000"}, "l1_weight_error": "0.09864098000000000000000000000", "max_leg_weight_error": "0.04652406", "checks": {"capital_positive": true, "invested_fraction_bounded": true, "holdings_long_only": true, "active_targets_present": true, "target_weights_bounded": true, "quote_coverage": true, "exposure_quote_coverage": true, "whole_share_eligible_targets_present": true, "funded_whole_share_target_ratio": true, "l1_weight_error": true, "max_leg_weight_error": true, "exposure_caps": true}, "reasons": []}, "results": [], "withheld_orders": []}
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=26)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "7549.6900", "total_market_value_usd": "4461.8900", "total_nav_usd": "12011.5800", "total_unrealized_pnl_usd": "16.0800", "broker_reported_nav_usd": null, "holdings": [{"symbol": "DBC", "qty": 16, "avg_cost_usd": "30.9400", "mark_price_usd": "31.9000", "market_value_usd": "510.4000", "marked": true, "weight_pct": "4.249232823658502878056009284", "unrealized_pnl_usd": "15.3600"}, {"symbol": "EEM", "qty": 4, "avg_cost_usd": "66.1100", "mark_price_usd": "68.7000", "market_value_usd": "274.8000", "marked": true, "weight_pct": "2.287792280449366361461189952", "unrealized_pnl_usd": "10.3600"}, {"symbol": "EFA", "qty": 6, "avg_cost_usd": "108.0300", "mark_price_usd": "108.3500", "market_value_usd": "650.1000", "marked": true, "weight_pct": "5.412277152547791381317029067", "unrealized_pnl_usd": "1.9200"}, {"symbol": "SPY", "qty": 1, "avg_cost_usd": "763.4700", "mark_price_usd": "770.1900", "market_value_usd": "770.1900", "marked": true, "weight_pct": "6.412062359822771025959948650", "unrealized_pnl_usd": "6.7200"}, {"symbol": "UUP", "qty": 53, "avg_cost_usd": "27.9600", "mark_price_usd": "28.0800", "market_value_usd": "1488.2400", "marked": true, "weight_pct": "12.39004360791835878377365842", "unrealized_pnl_usd": "6.3600"}, {"symbol": "VNQ", "qty": 8, "avg_cost_usd": "99.1000", "mark_price_usd": "96.0200", "market_value_usd": "768.1600", "marked": true, "weight_pct": "6.395162002001401980422225885", "unrealized_pnl_usd": "-24.6400"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper", "measurement_contract_id": null, "measurement_scope": "account", "excluded_fills_count": 0, "capital_basis_usd": "12000.0", "ledger_cash_nonnegative": true, "measurement_valid": true}
```
