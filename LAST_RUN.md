# forward 페이퍼 A/B 토너먼트 — 최신 실행 (현재 데이터, 돈 안 움직임)

추세 필터 **ON**(canary-portfolio.toml / forward_trend.db) vs **OFF**
(canary-portfolio-notrend.toml / forward_notrend.db). 전용 DB 로 격리된
두 페이퍼 트랙을 스펙 035 forward-verdict 로 각각 판정한다. PAPER 전용 — 실주문 0건.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | 0ad1228bbd6f7cede9cdb360e899faafe21d2ed4 |
| trigger | schedule |
| timestamp_utc | 2026-08-21T22:54:45Z |
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

# 🏆 forward 토너먼트 리더보드 — 읽기 전용, 돈 0 이동

> ➖ 엣지 확정 트랙 없음 — 비교 가능 트랙 모두 NO_EDGE(우위가 우연과 구별 안 됨). 더 나은 후보 탐색 계속.
>
> 비교 가능하지만 단순 보유를 과적합 보정 후 못 이긴 상태. 라이브 변경 사유 없음.

| # | 트랙 | 판정 | 관측 | 칼마 | 샤프 | 초과수익% | 낙폭% | 상태 |
|--:|------|:----:|-----:|-----:|-----:|----------:|------:|:----:|
| 1 | 멀티에셋 분산 추세 (스펙 043) | ➖ NO_EDGE | 50/20 | 18.59 | 2.10 | 34.98 | 19.89 | ✅ |
| 2 | 글로벌 3자산 추세 고정등가중 (재지정 후보) | ➖ NO_EDGE | 47/20 | 11.86 | 1.82 | 16.70 | 12.91 | ✅ |
| 3 | 글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD) 🏠 | ➖ NO_EDGE | 50/20 | 4.57 | 1.10 | 5.09 | 11.60 | ✅ |
| 4 | 위험관리 베타 (스펙 042) | ➖ NO_EDGE | 50/20 | 4.03 | 1.98 | 31.12 | 76.44 | ✅ |
| 5 | 글로벌 분산 추세 확대 (11 슬리브) | ➖ NO_EDGE | 50/20 | 1.26 | 0.57 | 1.87 | 13.60 | ✅ |
| 6 | 추세 필터 ON (드로다운 방어) | ➖ NO_EDGE | 42/20 | -1.05 | 1.67 | -91.01 | 94.79 | ✅ |
| 7 | 추세 필터 OFF (대조군) | ➖ NO_EDGE | 45/20 | -1.11 | 1.24 | -73.30 | 90.07 | ✅ |

🏠 라이브 검증 트랙 · 👑 챔피언(비교 가능 EDGE_CONFIRMED 1위) · 🚀 도전자(검증 트랙을 앞섬). 잠정(⏳)은 관측이 더 쌓여야 비교 가능 — 지표는 잠정치.

## 후보 관측 품질

✅ **OK** — 모든 후보가 최소 관측을 충족. 관측 수 차이는 참고 정보로만 표시: globalfixed, trend, notrend.

| 전체 | 판정 읽힘 | 판정 없음 | 최소 관측 | 최대 관측 | 뒤처진 트랙 |
|-----:|----------:|----------:|----------:|----------:|-------------|
| 7 | 7 | 0 | 42 | 50 | globalfixed, trend, notrend |

⚠ 이건 종합 보고다(읽기 전용). 라이브 전략은 자동으로 안 바뀐다 — 재지정은 운영자 게이트(헌법 X.4). 검증=배치 정합이라 도전자가 라이브가 되려면 라이브 설정 지문을 그 트랙으로 맞추는 운영자/세션 결정이 필요하다.

## 🧾 리더보드 결정 JSON (기계 판독 단일 증거)

> 아래 JSON 은 위 리더보드와 같은 순수 코어 출력이다. 재지정·감시 루프는
> 가능하면 이 기계 판독 증거를 우선 소비해야 한다. 특히 known_count,
> unknown_count, observation_health 로 후보 관측 품질을 분리해 본다.

```json
{"schema_version": "1.0", "as_of_utc": "2026-08-21T22:54:45.077071+00:00", "champion_key": null, "incumbent_key": "global", "challenger_key": null, "comparable_count": 7, "adjusted_dsr_threshold": null, "champion_multiplicity_robust": null, "track_count": 7, "known_count": 7, "unknown_count": 0, "max_n_obs": 50, "min_n_obs": 42, "lagging_keys": ["globalfixed", "trend", "notrend"], "observation_health": "OK", "observation_note": "모든 후보가 최소 관측을 충족. 관측 수 차이는 참고 정보로만 표시: globalfixed, trend, notrend.", "headline": "➖ 엣지 확정 트랙 없음 — 비교 가능 트랙 모두 NO_EDGE(우위가 우연과 구별 안 됨). 더 나은 후보 탐색 계속.", "note": "비교 가능하지만 단순 보유를 과적합 보정 후 못 이긴 상태. 라이브 변경 사유 없음.", "rows": [{"key": "multiasset", "label": "멀티에셋 분산 추세 (스펙 043)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 50, "min_obs": 20, "comparability": "COMPARABLE", "rank": 1, "calmar": "18.594042", "sharpe": "2.101742", "total_return_pct": "35.932584", "max_drawdown_pct": "19.890290", "excess_return_pct": "34.981926", "dsr": null, "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.733785", "dsr_threshold": "0.95", "universe_size": 2, "universe": ["SPY", "IEF"]}, {"key": "globalfixed", "label": "글로벌 3자산 추세 고정등가중 (재지정 후보)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 47, "min_obs": 20, "comparability": "COMPARABLE", "rank": 2, "calmar": "11.864606", "sharpe": "1.820414", "total_return_pct": "18.919143", "max_drawdown_pct": "12.913037", "excess_return_pct": "16.703466", "dsr": null, "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.601730", "dsr_threshold": "0.95", "universe_size": 3, "universe": ["SPY", "IEF", "GLD"]}, {"key": "global", "label": "글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD)", "is_incumbent": true, "verdict": "NO_EDGE", "n_obs": 50, "min_obs": 20, "comparability": "COMPARABLE", "rank": 3, "calmar": "4.567736", "sharpe": "1.100945", "total_return_pct": "8.798901", "max_drawdown_pct": "11.595110", "excess_return_pct": "5.094155", "dsr": null, "beats_benchmark_calmar": false, "psr_vs_benchmark": "0.365116", "dsr_threshold": "0.95", "universe_size": 3, "universe": ["SPY", "IEF", "GLD"]}, {"key": "rmbeta", "label": "위험관리 베타 (스펙 042)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 50, "min_obs": 20, "comparability": "COMPARABLE", "rank": 4, "calmar": "4.029526", "sharpe": "1.984886", "total_return_pct": "32.180017", "max_drawdown_pct": "76.439403", "excess_return_pct": "31.115567", "dsr": null, "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.764021", "dsr_threshold": "0.95", "universe_size": 2, "universe": ["SPY", "QQQ"]}, {"key": "wide", "label": "글로벌 분산 추세 확대 (11 슬리브)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 50, "min_obs": 20, "comparability": "COMPARABLE", "rank": 5, "calmar": "1.262554", "sharpe": "0.571447", "total_return_pct": "3.194229", "max_drawdown_pct": "13.600883", "excess_return_pct": "1.867750", "dsr": null, "beats_benchmark_calmar": false, "psr_vs_benchmark": "0.427366", "dsr_threshold": "0.95", "universe_size": 11, "universe": ["SPY", "QQQ", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD"]}, {"key": "trend", "label": "추세 필터 ON (드로다운 방어)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 42, "min_obs": 20, "comparability": "COMPARABLE", "rank": 6, "calmar": "-1.05494", "sharpe": "1.667500", "total_return_pct": "-90.577252", "max_drawdown_pct": "94.792059", "excess_return_pct": "-91.009544", "dsr": null, "beats_benchmark_calmar": false, "psr_vs_benchmark": "0.189360", "dsr_threshold": "0.95", "universe_size": 501, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES"]}, {"key": "notrend", "label": "추세 필터 OFF (대조군)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 45, "min_obs": 20, "comparability": "COMPARABLE", "rank": 7, "calmar": "-1.109547", "sharpe": "1.240313", "total_return_pct": "-72.909542", "max_drawdown_pct": "90.066825", "excess_return_pct": "-73.298971", "dsr": null, "beats_benchmark_calmar": false, "psr_vs_benchmark": "0.257525", "dsr_threshold": "0.95", "universe_size": 501, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES"]}]}
```

## 🚦 Halt 깃발 상태 (읽기 전용 진단)

> data/halt.flag 는 라이브 워커·라이브 캐너리의 킬스위치(스펙 014 서킷 브레이커
> ·정합성 불일치가 자동 설정). 페이퍼 forward 트랙은 트랙별 전용 깃발
> (data/forward_*.halt.flag)로 격리되어 라이브 깃발에 막히지 않는다. 라이브
> 깃발이 서 있으면 무장 후 실주문이 거부되므로, 운영자는 아래 사유를 확인하고
> 서버에서 'auto-invest resume' 으로 해제를 결정한다(자동 해제 안 함 — 안전 자세).

```
-- data/halt.flag
{"ts_utc":"2026-06-26T20:00:01.456Z","reason":"reconciliation mismatch: 3 position(s)"}-- data/forward_trend.halt.flag
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
# 일일 전략 모니터 (as of 2026-07) — 읽기 전용, 돈 0 이동

① 엣지(분산 추세)가 최근에도 유효한가:
   최근 5년 샤프 +1.71 | 최근 10년 샤프 +1.77 | 최근 5년 낙폭 +3.63%

② 분산 가정이 지금 신뢰 가능한가 (주식·채권 상관):
   현재 +0.13 | 최근 5년 평균 +0.12 → 판정: DIVERSIFICATION_WEAKENED

③ 낙폭 예산 15%에서 레버리지 복리 권고 (최근 25년 기준):
   무레버 복리 +7.87% → 권고 L=2.0 → 복리 11.4%/년 (낙폭 13%)

④ 오늘 추세 신호 (S&P vs 10개월 SMA):
   투자(추세 위) (갭 +6.71%)

⚠ 이건 감시 보고다. 라이브 레버리지/무장은 운영자 게이트(헌법 X.4).

=== 낙폭 예산 20% (레버리지 권고 비교) ===
{"as_of": "2026-07", "edge": {"diversified_5y_sharpe": 1.708, "diversified_10y_sharpe": 1.767, "diversified_5y_maxdd_pct": 3.629}, "regime": {"corr_current": 0.131, "corr_recent_5y_avg": 0.115, "verdict": "DIVERSIFICATION_WEAKENED"}, "leverage_recommendation": {"dd_budget_pct": 20.0, "window_years": 25, "unlevered_cagr_pct": 7.868, "leverage": 3.0, "cagr_pct": 14.811, "maxdd_pct": 19.591}, "today_signal": {"in_market": true, "gap_pct": 6.712}}
```

## 🧭 판정 — 추세 필터 ON (drawdown 방어 오버레이)

> EDGE_CONFIRMED 만이 운영자 라이브 게이트(헌법 X.4)에 올릴 증거(자동 배포 아님).
> INSUFFICIENT_DATA 면 NAV 관측이 더 쌓여야 한다(≈20 거래일) — 정상.

```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "\ub2e8\uc21c \ubcf4\uc720\ub97c \uc704\ud5d8\uc870\uc815\uc73c\ub85c \ubabb \uc774\uae40; PSR 0.189360 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428)", "n_obs": 42, "min_obs_required": 20, "strategy_sharpe_annual": "1.667500", "strategy_total_return_pct": "-90.577252", "strategy_max_drawdown_pct": "94.792059", "strategy_calmar": "-1.05494", "benchmark_sharpe_annual": "3.459270", "benchmark_total_return_pct": "0.432292", "benchmark_max_drawdown_pct": "0.125245", "benchmark_calmar": "20.934533", "excess_return_pct": "-91.009544", "beats_benchmark_calmar": false, "psr_vs_benchmark": "0.189360", "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 43, "legacy_snapshots_excluded": 18, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A", "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT", "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX", "BDX", "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BNY", "BA", "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CPT", "CPB", "COF", "CAH", "CCL", "CARR", "CVNA", "CASY", "CAT", "CBOE", "CBRE", "CDW", "COR", "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD", "CIEN", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS", "KO", "CTSH", "COHR", "COIN", "CL", "CMCSA", "FIX", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP", "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI", "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM", "FANG", "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI", "DTE", "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW", "EA", "ELV", "EME", "EMR", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ERIE", "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB", "FSLR", "FE", "FISV", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA", "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON", "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "IBKR", "ICE", "IFF", "IP", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR", "LHX", "LH", "LRCX", "LVS", "LDOS", "LEN", "LII", "LLY", "LIN", "LYV", "LMT", "L", "LOW", "LULU", "LITE", "LYB", "MTB", "MPC", "MAR", "MRSH", "MLM", "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PSKY", "PH", "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTC", "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL", "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC", "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL", "TXT", "TMO", "TJX", "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VRT", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WY", "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH", "ZTS"]}
```

## 🧭 판정 — 추세 필터 OFF (대조군)

```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "\ub2e8\uc21c \ubcf4\uc720\ub97c \uc704\ud5d8\uc870\uc815\uc73c\ub85c \ubabb \uc774\uae40; PSR 0.257525 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428)", "n_obs": 45, "min_obs_required": 20, "strategy_sharpe_annual": "1.240313", "strategy_total_return_pct": "-72.909542", "strategy_max_drawdown_pct": "90.066825", "strategy_calmar": "-1.109547", "benchmark_sharpe_annual": "2.714984", "benchmark_total_return_pct": "0.389429", "benchmark_max_drawdown_pct": "0.159612", "benchmark_calmar": "13.7861", "excess_return_pct": "-73.298971", "beats_benchmark_calmar": false, "psr_vs_benchmark": "0.257525", "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 46, "legacy_snapshots_excluded": 14, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A", "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT", "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX", "BDX", "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BNY", "BA", "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CPT", "CPB", "COF", "CAH", "CCL", "CARR", "CVNA", "CASY", "CAT", "CBOE", "CBRE", "CDW", "COR", "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD", "CIEN", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS", "KO", "CTSH", "COHR", "COIN", "CL", "CMCSA", "FIX", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP", "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI", "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM", "FANG", "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI", "DTE", "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW", "EA", "ELV", "EME", "EMR", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ERIE", "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB", "FSLR", "FE", "FISV", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA", "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON", "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "IBKR", "ICE", "IFF", "IP", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR", "LHX", "LH", "LRCX", "LVS", "LDOS", "LEN", "LII", "LLY", "LIN", "LYV", "LMT", "L", "LOW", "LULU", "LITE", "LYB", "MTB", "MPC", "MAR", "MRSH", "MLM", "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PSKY", "PH", "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTC", "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL", "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC", "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL", "TXT", "TMO", "TJX", "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VRT", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WY", "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH", "ZTS"]}
```

> 두 판정을 나란히 비교: ON 의 max_drawdown_pct·sharpe·excess 가 OFF 보다
> 나으면 추세 필터가 *실제로* 도움이 된다는 격리된 증거다.

## 🛡️ 판정 — 위험관리 베타 (추세 게이트 광범위 베타, 스펙 042)

> SPY·QQQ 를 10개월 추세 위일 때만 보유(아래면 현금). 종목 선택이 아니라 베타의
> 자본 방어. 우리 KIS 체결로 forward 실적을 쌓아 *확신을 번다*(운영자 2026-06-05).
> INSUFFICIENT_DATA 면 NAV 관측이 더 쌓여야 함(정상). 200일 미만이면 추세 미확정 →
> on_insufficient=cash 라 현금 보유(보수적). 라이브 전환은 운영자 게이트(헌법 X.4).

```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "PSR 0.764021 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 4.029526 > \ubca4\uce58 1.432913 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 50, "min_obs_required": 20, "strategy_sharpe_annual": "1.984886", "strategy_total_return_pct": "32.180017", "strategy_max_drawdown_pct": "76.439403", "strategy_calmar": "4.029526", "benchmark_sharpe_annual": "0.434080", "benchmark_total_return_pct": "1.064450", "benchmark_max_drawdown_pct": "3.825378", "benchmark_calmar": "1.432913", "excess_return_pct": "31.115567", "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.764021", "dsr": null, "num_trials": 1, "min_track_record_obs": "257.231808", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 51, "legacy_snapshots_excluded": 5, "universe": ["SPY", "QQQ"]}
```

## 🌐 판정 — 멀티에셋 분산 추세 (비상관 자산 합성, 스펙 043)

> 주식(SPY) + 채권(IEF) 을 각자 추세 위일 때만 보유. ARM C(둘 다 주식)와 달리
> *비상관 자산*을 합쳐 분산 이득을 노린다(스펙 043: 단일 주식 추세 샤프 1.18~1.43
> → 분산 추세 1.58~1.81, 낙폭 절반, Shiller 1871~ 검증). INSUFFICIENT_DATA 면
> NAV 관측이 더 쌓여야 함(정상). 라이브 전환은 운영자 게이트(헌법 X.4).

```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "PSR 0.733785 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 18.594042 > \ubca4\uce58 3.569744 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 50, "min_obs_required": 20, "strategy_sharpe_annual": "2.101742", "strategy_total_return_pct": "35.932584", "strategy_max_drawdown_pct": "19.890290", "strategy_calmar": "18.594042", "benchmark_sharpe_annual": "0.756660", "benchmark_total_return_pct": "0.950658", "benchmark_max_drawdown_pct": "1.368226", "benchmark_calmar": "3.569744", "excess_return_pct": "34.981926", "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.733785", "dsr": null, "num_trials": 1, "min_track_record_obs": "341.143306", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 51, "legacy_snapshots_excluded": 5, "universe": ["SPY", "IEF"]}
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
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "\ub2e8\uc21c \ubcf4\uc720\ub97c \uc704\ud5d8\uc870\uc815\uc73c\ub85c \ubabb \uc774\uae40; PSR 0.365116 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428)", "n_obs": 50, "min_obs_required": 20, "strategy_sharpe_annual": "1.100945", "strategy_total_return_pct": "8.798901", "strategy_max_drawdown_pct": "11.595110", "strategy_calmar": "4.567736", "benchmark_sharpe_annual": "1.864581", "benchmark_total_return_pct": "3.704746", "benchmark_max_drawdown_pct": "3.219720", "benchmark_calmar": "6.249831", "excess_return_pct": "5.094155", "beats_benchmark_calmar": false, "psr_vs_benchmark": "0.365116", "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 51, "legacy_snapshots_excluded": 4, "universe": ["SPY", "IEF", "GLD"]}
```

## ⚖ 판정 — 글로벌 3자산 추세 고정(등가중) 재지정 후보 (스펙 047/050 후속)

> 라이브 검증 트랙과 weight_scheme 만 다른 등가중 변형. 깊은 분석은 등가중이
> 캡 안 무레버 복리 +1.3~2.3%p 높다고 봤으나 낙폭이 사다리 강등선(10%)에 더
> 가깝다 — 이 트랙이 *일별* 낙폭/강등 빈도를 실측해 재지정 안전성을 답한다.
> EDGE_CONFIRMED + 지문 정합을 벌면 운영자가 재지정 결정(헌법 X.4). 돈 0·페이퍼.

```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "PSR 0.601730 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 11.864606 > \ubca4\uce58 3.929082 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 47, "min_obs_required": 20, "strategy_sharpe_annual": "1.820414", "strategy_total_return_pct": "18.919143", "strategy_max_drawdown_pct": "12.913037", "strategy_calmar": "11.864606", "benchmark_sharpe_annual": "1.244457", "benchmark_total_return_pct": "2.215677", "benchmark_max_drawdown_pct": "3.173331", "benchmark_calmar": "3.929082", "excess_return_pct": "16.703466", "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.601730", "dsr": null, "num_trials": 1, "min_track_record_obs": "1873.213990", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 48, "legacy_snapshots_excluded": 0, "universe": ["SPY", "IEF", "GLD"]}
```

## 🌍 판정 — 글로벌 분산 추세 확대 유니버스 (11 슬리브, 계획 ③)

> 검증된 메커니즘(역변동성 + 다중 속도 추세 앙상블) 그대로, 베팅의 폭만
> 3 → 11 슬리브(주식 SPY·QQQ·EFA·EEM / 채권 IEF·TLT·LQD / 실물 GLD·DBC·VNQ
> / 통화 UUP). 성과 ≈ 질 × √N — 제약 안에서 가장 큰 지렛대. ARM E(3자산)와
> 나란히 비교하면 '폭 확장이 우리 체결 기준 forward 로도 이득인가'의 격리된
> 답. 라이브는 검증된 3자산 유지 — 이 트랙이 EDGE_CONFIRMED 를 벌어야 재지정
> 후보가 된다(검증=배치 정합, 헌법 X.4 v5.0.0 사다리).

```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "\ub2e8\uc21c \ubcf4\uc720\ub97c \uc704\ud5d8\uc870\uc815\uc73c\ub85c \ubabb \uc774\uae40; PSR 0.427366 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428)", "n_obs": 50, "min_obs_required": 20, "strategy_sharpe_annual": "0.571447", "strategy_total_return_pct": "3.194229", "strategy_max_drawdown_pct": "13.600883", "strategy_calmar": "1.262554", "benchmark_sharpe_annual": "0.988345", "benchmark_total_return_pct": "1.326479", "benchmark_max_drawdown_pct": "2.049168", "benchmark_calmar": "3.351123", "excess_return_pct": "1.867750", "beats_benchmark_calmar": false, "psr_vs_benchmark": "0.427366", "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 51, "legacy_snapshots_excluded": 0, "universe": ["SPY", "QQQ", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD", "DBC", "VNQ", "UUP"]}
```

## TREND-ON 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "GEN", "exchange": "NAS", "fetched": 949, "inserted": 1}, {"symbol": "EVRG", "exchange": "NAS", "fetched": 915, "inserted": 1}, {"symbol": "GEHC", "exchange": "NAS", "fetched": 911, "inserted": 1}, {"symbol": "COHR", "exchange": "NYS", "fetched": 877, "inserted": 1}, {"symbol": "EG", "exchange": "NYS", "fetched": 784, "inserted": 1}, {"symbol": "COO", "exchange": "NAS", "fetched": 729, "inserted": 1}, {"symbol": "DASH", "exchange": "NAS", "fetched": 728, "inserted": 1}, {"symbol": "EXPD", "exchange": "NYS", "fetched": 689, "inserted": 1}, {"symbol": "CPAY", "exchange": "NYS", "fetched": 605, "inserted": 1}, {"symbol": "GEV", "exchange": "NYS", "fetched": 600, "inserted": 1}, {"symbol": "CPB", "exchange": "NAS", "fetched": 504, "inserted": 1}, {"symbol": "EXE", "exchange": "NAS", "fetched": 473, "inserted": 1}, {"symbol": "FISV", "exchange": "NAS", "fetched": 195, "inserted": 1}]}
{"portfolio_id": "forward-paper-canary", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "916.63", "planned_buy_notional_usd": "907.55", "planned_sell_notional_usd": "577.04", "target_weights": {"INTC": "0.100000", "AMD": "0.100000", "GLW": "0.100000", "AMAT": "0.100000", "CSCO": "0.100000", "CAT": "0.100000", "ADI": "0.100000", "CRWD": "0.100000", "XOM": "0.100000", "CVX": "0.100000"}, "signal_target_weights": {"INTC": "0.100000", "AMD": "0.100000", "GLW": "0.100000", "AMAT": "0.100000", "CSCO": "0.100000", "CAT": "0.100000", "ADI": "0.100000", "CRWD": "0.100000", "XOM": "0.100000", "CVX": "0.100000"}, "execution_symbol_map": {}, "results": [{"symbol": "COHR", "side": "SELL", "requested_qty": 17, "routed_qty": 2, "limit_price_usd": "288.52", "state": "PAPER_FILLED", "reason": null}, {"symbol": "CAT", "side": "BUY", "requested_qty": 1, "routed_qty": 0, "limit_price_usd": "829.34", "state": "SKIPPED_PER_TRADE_CAP", "reason": "per_trade_cap_below_one_share"}, {"symbol": "CVX", "side": "BUY", "requested_qty": 5, "routed_qty": 2, "limit_price_usd": "205.90", "state": "REJECTED_BY_GATE", "reason": "global exposure would become $88108.2958, exceeds cap $9600.00"}, {"symbol": "XOM", "side": "BUY", "requested_qty": 6, "routed_qty": 3, "limit_price_usd": "165.25", "state": "REJECTED_BY_GATE", "reason": "global exposure would become $88192.2458, exceeds cap $9600.00"}], "withheld_orders": []}
(경고: 장부 현금 음수 $-88242.2054 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=629)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-88242.2054", "total_market_value_usd": "87115.5098", "total_nav_usd": "-1126.6956", "total_unrealized_pnl_usd": "-11986.83888125000000000000000", "broker_reported_nav_usd": null, "holdings": [{"symbol": "ADI", "qty": 30, "avg_cost_usd": "399.1320466666666666666666667", "mark_price_usd": "373.1800", "market_value_usd": "11195.4000", "marked": true, "weight_pct": null, "unrealized_pnl_usd": "-778.5614000000000000000000010"}, {"symbol": "AMAT", "qty": 18, "avg_cost_usd": "558.2801055555555555555555556", "mark_price_usd": "492.3100", "market_value_usd": "8861.5800", "marked": true, "weight_pct": null, "unrealized_pnl_usd": "-1187.461900000000000000000001"}, {"symbol": "AMD", "qty": 30, "avg_cost_usd": "523.77984000000000000000000", "mark_price_usd": "472.3100", "market_value_usd": "14169.3000", "marked": true, "weight_pct": null, "unrealized_pnl_usd": "-1544.09520000000000000000000"}, {"symbol": "COHR", "qty": 15, "avg_cost_usd": "345.96121875000000000000000", "mark_price_usd": "289.1000", "market_value_usd": "4336.5000", "marked": true, "weight_pct": null, "unrealized_pnl_usd": "-852.91828125000000000000000"}, {"symbol": "CRWD", "qty": 38, "avg_cost_usd": "195.3712289473684210526315789", "mark_price_usd": "190.9056", "market_value_usd": "7254.4128", "marked": true, "weight_pct": null, "unrealized_pnl_usd": "-169.6938999999999999999999982"}, {"symbol": "CSCO", "qty": 144, "avg_cost_usd": "116.77784375000000000000000", "mark_price_usd": "111.0000", "market_value_usd": "15984.0000", "marked": true, "weight_pct": null, "unrealized_pnl_usd": "-832.00950000000000000000000"}, {"symbol": "GLW", "qty": 85, "avg_cost_usd": "185.6028423529411764705882353", "mark_price_usd": "149.5802", "market_value_usd": "12714.3170", "marked": true, "weight_pct": null, "unrealized_pnl_usd": "-3061.924600000000000000000000"}, {"symbol": "INTC", "qty": 140, "avg_cost_usd": "115.42981500000000000000000", "mark_price_usd": "90.0000", "market_value_usd": "12600.0000", "marked": true, "weight_pct": null, "unrealized_pnl_usd": "-3560.17410000000000000000000"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## TREND-OFF 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "GEN", "exchange": "NAS", "fetched": 949, "inserted": 1}, {"symbol": "EVRG", "exchange": "NAS", "fetched": 915, "inserted": 1}, {"symbol": "GEHC", "exchange": "NAS", "fetched": 911, "inserted": 1}, {"symbol": "COHR", "exchange": "NYS", "fetched": 877, "inserted": 1}, {"symbol": "EG", "exchange": "NYS", "fetched": 784, "inserted": 1}, {"symbol": "COO", "exchange": "NAS", "fetched": 729, "inserted": 1}, {"symbol": "DASH", "exchange": "NAS", "fetched": 728, "inserted": 1}, {"symbol": "EXPD", "exchange": "NYS", "fetched": 689, "inserted": 1}, {"symbol": "CPAY", "exchange": "NYS", "fetched": 605, "inserted": 1}, {"symbol": "GEV", "exchange": "NYS", "fetched": 600, "inserted": 1}, {"symbol": "CPB", "exchange": "NAS", "fetched": 504, "inserted": 1}, {"symbol": "EXE", "exchange": "NAS", "fetched": 473, "inserted": 1}, {"symbol": "FISV", "exchange": "NAS", "fetched": 195, "inserted": 1}]}
{"portfolio_id": "forward-paper-canary-notrend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "544.39", "planned_buy_notional_usd": "539.00", "planned_sell_notional_usd": "577.02", "target_weights": {"DELL": "0.100000", "CIEN": "0.100000", "AMD": "0.100000", "GLW": "0.100000", "AMAT": "0.100000", "CSCO": "0.100000", "CAT": "0.100000", "ADI": "0.100000", "CRWD": "0.100000", "FCX": "0.100000"}, "signal_target_weights": {"DELL": "0.100000", "CIEN": "0.100000", "AMD": "0.100000", "GLW": "0.100000", "AMAT": "0.100000", "CSCO": "0.100000", "CAT": "0.100000", "ADI": "0.100000", "CRWD": "0.100000", "FCX": "0.100000"}, "execution_symbol_map": {}, "results": [{"symbol": "COHR", "side": "SELL", "requested_qty": 13, "routed_qty": 2, "limit_price_usd": "288.51", "state": "PAPER_FILLED", "reason": null}, {"symbol": "CAT", "side": "BUY", "requested_qty": 1, "routed_qty": 0, "limit_price_usd": "829.34", "state": "SKIPPED_PER_TRADE_CAP", "reason": "per_trade_cap_below_one_share"}, {"symbol": "FCX", "side": "BUY", "requested_qty": 14, "routed_qty": 7, "limit_price_usd": "77.00", "state": "REJECTED_BY_GATE", "reason": "global exposure would become $93401.7908, exceeds cap $9600.00"}], "withheld_orders": []}
(경고: 장부 현금 음수 $-89770.3035 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=628)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-89770.3035", "total_market_value_usd": "92279.0308", "total_nav_usd": "2508.7273", "total_unrealized_pnl_usd": "-8347.715360000000000000000001", "broker_reported_nav_usd": null, "holdings": [{"symbol": "ADI", "qty": 30, "avg_cost_usd": "399.1284666666666666666666667", "mark_price_usd": "373.1800", "market_value_usd": "11195.4000", "marked": true, "weight_pct": "446.2581485042236356259207607", "unrealized_pnl_usd": "-778.4540000000000000000000010"}, {"symbol": "AMAT", "qty": 17, "avg_cost_usd": "555.8969470588235294117647059", "mark_price_usd": "492.3100", "market_value_usd": "8369.2700", "marked": true, "weight_pct": "333.6062074183989626931552106", "unrealized_pnl_usd": "-1080.978100000000000000000000"}, {"symbol": "AMD", "qty": 30, "avg_cost_usd": "523.7594333333333333333333333", "mark_price_usd": "472.4500", "market_value_usd": "14173.5000", "marked": true, "weight_pct": "564.9677428072792128502767120", "unrealized_pnl_usd": "-1539.282999999999999999999999"}, {"symbol": "CIEN", "qty": 30, "avg_cost_usd": "437.9061366666666666666666667", "mark_price_usd": "397.0000", "market_value_usd": "11910.0000", "marked": true, "weight_pct": "474.7427111747059953467242135", "unrealized_pnl_usd": "-1227.184100000000000000000001"}, {"symbol": "COHR", "qty": 11, "avg_cost_usd": "350.88526000000000000000000", "mark_price_usd": "289.0900", "market_value_usd": "3179.9900", "marked": true, "weight_pct": "126.7571011006258033704978616", "unrealized_pnl_usd": "-679.74786000000000000000000"}, {"symbol": "CRWD", "qty": 8, "avg_cost_usd": "191.86375", "mark_price_usd": "190.9000", "market_value_usd": "1527.2000", "marked": true, "weight_pct": "60.87548853954752276184023668", "unrealized_pnl_usd": "-7.71000"}, {"symbol": "CSCO", "qty": 144, "avg_cost_usd": "116.7711284722222222222222222", "mark_price_usd": "111.0007", "market_value_usd": "15984.1008", "marked": true, "weight_pct": "637.1398278322239328284106447", "unrealized_pnl_usd": "-830.9416999999999999999999968"}, {"symbol": "DELL", "qty": 30, "avg_cost_usd": "412.2568366666666666666666667", "mark_price_usd": "440.8140", "market_value_usd": "13224.4200", "marked": true, "weight_pct": "527.1366082714530192261231422", "unrealized_pnl_usd": "856.7148999999999999999999990"}, {"symbol": "GLW", "qty": 85, "avg_cost_usd": "185.5915470588235294117647059", "mark_price_usd": "149.5900", "market_value_usd": "12715.1500", "marked": true, "weight_pct": "506.8366737189809350741310146", "unrealized_pnl_usd": "-3060.131500000000000000000002"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## RISK-MANAGED-BETA 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "QQQ", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "risk-managed-beta", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"QQQ": "0.500000", "SPY": "0.500000"}, "signal_target_weights": {"QQQ": "0.500000", "SPY": "0.500000"}, "execution_symbol_map": {}, "results": [], "withheld_orders": []}
(경고: 장부 현금 음수 $-322437.2495 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=186)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-322437.2495", "total_market_value_usd": "338719.0783", "total_nav_usd": "16281.8288", "total_unrealized_pnl_usd": "4281.828800000000000000000002", "broker_reported_nav_usd": null, "holdings": [{"symbol": "QQQ", "qty": 239, "avg_cost_usd": "717.4312937238493723849372385", "mark_price_usd": "714.1016", "market_value_usd": "170670.2824", "marked": true, "weight_pct": "1048.225506461534591249356460", "unrealized_pnl_usd": "-795.7968000000000000000000015"}, {"symbol": "SPY", "qty": 219, "avg_cost_usd": "744.1605949771689497716894977", "mark_price_usd": "767.3461", "market_value_usd": "168048.7959", "marked": true, "weight_pct": "1032.124818189956646639104816", "unrealized_pnl_usd": "5077.625600000000000000000004"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## MULTI-ASSET-TREND 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "multi-asset-trend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"SPY": "0.500000"}, "signal_target_weights": {"SPY": "0.500000"}, "execution_symbol_map": {}, "results": [], "withheld_orders": []}
(경고: 장부 현금 음수 $-151584.0976 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=138)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-151584.0976", "total_market_value_usd": "168048.7959", "total_nav_usd": "16464.6983", "total_unrealized_pnl_usd": "5077.149900000000000000000006", "broker_reported_nav_usd": null, "holdings": [{"symbol": "SPY", "qty": 219, "avg_cost_usd": "744.1627671232876712328767123", "mark_price_usd": "767.3461", "market_value_usd": "168048.7959", "marked": true, "weight_pct": "1020.661252566043071678999426", "unrealized_pnl_usd": "5077.149900000000000000000006"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## GLOBAL-TREND 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "855.15", "planned_buy_notional_usd": "846.68", "planned_sell_notional_usd": "0.00", "target_weights": {"SPY": "0.233424", "GLD": "0.103475"}, "signal_target_weights": {"SPY": "0.233424", "GLD": "0.103475"}, "execution_symbol_map": {}, "results": [{"symbol": "GLD", "side": "BUY", "requested_qty": 2, "routed_qty": 2, "limit_price_usd": "423.34", "state": "REJECTED_BY_GATE", "reason": "global exposure would become $69140.8300, exceeds cap $12000.00"}], "withheld_orders": []}
(경고: 장부 현금 음수 $-55192.4231 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=15881)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-55192.4231", "total_market_value_usd": "68294.1500", "total_nav_usd": "13101.7269", "total_unrealized_pnl_usd": "2028.689299999999999999999996", "broker_reported_nav_usd": null, "holdings": [{"symbol": "SPY", "qty": 89, "avg_cost_usd": "744.5557382022471910112359551", "mark_price_usd": "767.3500", "market_value_usd": "68294.1500", "marked": true, "weight_pct": "521.2606744230029706999922277", "unrealized_pnl_usd": "2028.689299999999999999999996"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## GLOBAL-TREND-FIXED 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend-fixed", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "3848.16", "planned_buy_notional_usd": "3810.06", "planned_sell_notional_usd": "0.00", "target_weights": {"SPY": "0.333334", "GLD": "0.333333"}, "signal_target_weights": {"SPY": "0.333334", "GLD": "0.333333"}, "execution_symbol_map": {}, "results": [{"symbol": "GLD", "side": "BUY", "requested_qty": 9, "routed_qty": 9, "limit_price_usd": "423.34", "state": "REJECTED_BY_GATE", "reason": "global exposure would become $102796.9200, exceeds cap $12000.00"}], "withheld_orders": []}
(경고: 장부 현금 음수 $-84716.4736 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=2064)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-84716.4736", "total_market_value_usd": "98986.8600", "total_nav_usd": "14270.3864", "total_unrealized_pnl_usd": "2861.624999999999999999999995", "broker_reported_nav_usd": null, "holdings": [{"symbol": "SPY", "qty": 129, "avg_cost_usd": "745.1568604651162790697674419", "mark_price_usd": "767.3400", "market_value_usd": "98986.8600", "marked": true, "weight_pct": "693.6522755964057147044035192", "unrealized_pnl_usd": "2861.624999999999999999999995"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## GLOBAL-TREND-WIDE 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "DBC", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "EEM", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "EFA", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "LQD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "QQQ", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "TLT", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "UUP", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "VNQ", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend-wide", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"DBC": "0.041471", "QQQ": "0.035074", "SPY": "0.072624", "EEM": "0.036134", "EFA": "0.055587", "VNQ": "0.068415", "UUP": "0.120862", "GLD": "0.032150"}, "signal_target_weights": {"DBC": "0.041471", "QQQ": "0.035074", "SPY": "0.072624", "EEM": "0.036134", "EFA": "0.055587", "VNQ": "0.068415", "UUP": "0.120862", "GLD": "0.032150"}, "execution_symbol_map": {}, "results": [], "withheld_orders": []}
(경고: 장부 현금 음수 $-126615.9625 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=519)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-126615.9625", "total_market_value_usd": "138999.2700", "total_nav_usd": "12383.3075", "total_unrealized_pnl_usd": "2193.256600000000000000000041", "broker_reported_nav_usd": null, "holdings": [{"symbol": "DBC", "qty": 380, "avg_cost_usd": "27.93493210526315789473684211", "mark_price_usd": "31.4300", "market_value_usd": "11943.4000", "marked": true, "weight_pct": "96.44757670759609256250803753", "unrealized_pnl_usd": "1328.125799999999999999999998"}, {"symbol": "EEM", "qty": 164, "avg_cost_usd": "67.16756219512195121951219512", "mark_price_usd": "67.2200", "market_value_usd": "11024.0800", "marked": true, "weight_pct": "89.02371196063733376563571566", "unrealized_pnl_usd": "8.59980000000000000000000032"}, {"symbol": "EFA", "qty": 168, "avg_cost_usd": "104.1313916666666666666666666", "mark_price_usd": "108.3700", "market_value_usd": "18206.1600", "marked": true, "weight_pct": "147.0217871921536310069018314", "unrealized_pnl_usd": "712.0862000000000000000000112"}, {"symbol": "SPY", "qty": 28, "avg_cost_usd": "745.29022500000000000000000", "mark_price_usd": "767.3925", "market_value_usd": "21486.9900", "marked": true, "weight_pct": "173.5157590167247320637075353", "unrealized_pnl_usd": "618.86370000000000000000000"}, {"symbol": "UUP", "qty": 1934, "avg_cost_usd": "28.30004906928645294725956565", "mark_price_usd": "27.9300", "market_value_usd": "54016.6200", "marked": true, "weight_pct": "436.2051091762035304380513849", "unrealized_pnl_usd": "-715.6748999999999999999999671"}, {"symbol": "VNQ", "qty": 226, "avg_cost_usd": "97.70249557522123893805309735", "mark_price_usd": "98.7700", "market_value_usd": "22322.0200", "marked": true, "weight_pct": "180.2589493961932222065873758", "unrealized_pnl_usd": "241.2559999999999999999999989"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```
