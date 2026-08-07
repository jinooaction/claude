# forward 페이퍼 A/B 토너먼트 — 최신 실행 (현재 데이터, 돈 안 움직임)

추세 필터 **ON**(canary-portfolio.toml / forward_trend.db) vs **OFF**
(canary-portfolio-notrend.toml / forward_notrend.db). 전용 DB 로 격리된
두 페이퍼 트랙을 스펙 035 forward-verdict 로 각각 판정한다. PAPER 전용 — 실주문 0건.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | 758dda2534af38f444ac75361295fb49b489e234 |
| trigger | schedule |
| timestamp_utc | 2026-08-07T23:09:50Z |
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
| 1 | 추세 필터 ON (드로다운 방어) | ➖ NO_EDGE | 33/20 | 98.04 | 3.02 | 80.55 | 93.39 | ✅ |
| 2 | 멀티에셋 분산 추세 (스펙 043) | ➖ NO_EDGE | 39/20 | 53.73 | 3.01 | 44.73 | 19.89 | ✅ |
| 3 | 글로벌 3자산 추세 고정등가중 (재지정 후보) | ➖ NO_EDGE | 36/20 | 29.26 | 2.82 | 24.33 | 12.91 | ✅ |
| 4 | 위험관리 베타 (스펙 042) | ➖ NO_EDGE | 39/20 | 24.83 | 2.51 | 56.93 | 76.44 | ✅ |
| 5 | 글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD) 🏠 | ➖ NO_EDGE | 39/20 | 10.41 | 1.79 | 10.93 | 11.60 | ✅ |
| 6 | 추세 필터 OFF (대조군) | ➖ NO_EDGE | 34/20 | 0.87 | 2.54 | 7.74 | 90.07 | ✅ |
| 7 | 글로벌 분산 추세 확대 (11 슬리브) | ➖ NO_EDGE | 39/20 | -1.41 | -0.26 | -3.43 | 13.60 | ✅ |

🏠 라이브 검증 트랙 · 👑 챔피언(비교 가능 EDGE_CONFIRMED 1위) · 🚀 도전자(검증 트랙을 앞섬). 잠정(⏳)은 관측이 더 쌓여야 비교 가능 — 지표는 잠정치.

## 후보 관측 품질

✅ **OK** — 모든 후보가 최소 관측을 충족. 관측 수 차이는 참고 정보로만 표시: trend, globalfixed, notrend.

| 전체 | 판정 읽힘 | 판정 없음 | 최소 관측 | 최대 관측 | 뒤처진 트랙 |
|-----:|----------:|----------:|----------:|----------:|-------------|
| 7 | 7 | 0 | 33 | 39 | trend, globalfixed, notrend |

⚠ 이건 종합 보고다(읽기 전용). 라이브 전략은 자동으로 안 바뀐다 — 재지정은 운영자 게이트(헌법 X.4). 검증=배치 정합이라 도전자가 라이브가 되려면 라이브 설정 지문을 그 트랙으로 맞추는 운영자/세션 결정이 필요하다.

## 🧾 리더보드 결정 JSON (기계 판독 단일 증거)

> 아래 JSON 은 위 리더보드와 같은 순수 코어 출력이다. 재지정·감시 루프는
> 가능하면 이 기계 판독 증거를 우선 소비해야 한다. 특히 known_count,
> unknown_count, observation_health 로 후보 관측 품질을 분리해 본다.

```json
{"schema_version": "1.0", "as_of_utc": "2026-08-07T23:09:50.081250+00:00", "champion_key": null, "incumbent_key": "global", "challenger_key": null, "comparable_count": 7, "adjusted_dsr_threshold": null, "champion_multiplicity_robust": null, "track_count": 7, "known_count": 7, "unknown_count": 0, "max_n_obs": 39, "min_n_obs": 33, "lagging_keys": ["trend", "globalfixed", "notrend"], "observation_health": "OK", "observation_note": "모든 후보가 최소 관측을 충족. 관측 수 차이는 참고 정보로만 표시: trend, globalfixed, notrend.", "headline": "➖ 엣지 확정 트랙 없음 — 비교 가능 트랙 모두 NO_EDGE(우위가 우연과 구별 안 됨). 더 나은 후보 탐색 계속.", "note": "비교 가능하지만 단순 보유를 과적합 보정 후 못 이긴 상태. 라이브 변경 사유 없음.", "rows": [{"key": "trend", "label": "추세 필터 ON (드로다운 방어)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 33, "min_obs": 20, "comparability": "COMPARABLE", "rank": 1, "calmar": "98.042349", "sharpe": "3.017668", "total_return_pct": "80.930398", "max_drawdown_pct": "93.394390", "excess_return_pct": "80.545840", "dsr": null, "psr_vs_benchmark": "0.327408", "dsr_threshold": "0.95", "universe_size": 501, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES"]}, {"key": "multiasset", "label": "멀티에셋 분산 추세 (스펙 043)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 39, "min_obs": 20, "comparability": "COMPARABLE", "rank": 2, "calmar": "53.733327", "sharpe": "3.007743", "total_return_pct": "46.299845", "max_drawdown_pct": "19.890290", "excess_return_pct": "44.731376", "dsr": null, "psr_vs_benchmark": "0.739243", "dsr_threshold": "0.95", "universe_size": 2, "universe": ["SPY", "IEF"]}, {"key": "globalfixed", "label": "글로벌 3자산 추세 고정등가중 (재지정 후보)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 36, "min_obs": 20, "comparability": "COMPARABLE", "rank": 3, "calmar": "29.257344", "sharpe": "2.815632", "total_return_pct": "25.036070", "max_drawdown_pct": "12.913037", "excess_return_pct": "24.333566", "dsr": null, "psr_vs_benchmark": "0.821255", "dsr_threshold": "0.95", "universe_size": 3, "universe": ["SPY", "IEF", "GLD"]}, {"key": "rmbeta", "label": "위험관리 베타 (스펙 042)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 39, "min_obs": 20, "comparability": "COMPARABLE", "rank": 4, "calmar": "24.83098", "sharpe": "2.513533", "total_return_pct": "58.958893", "max_drawdown_pct": "76.439403", "excess_return_pct": "56.929508", "dsr": null, "psr_vs_benchmark": "0.746239", "dsr_threshold": "0.95", "universe_size": 2, "universe": ["SPY", "QQQ"]}, {"key": "global", "label": "글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD)", "is_incumbent": true, "verdict": "NO_EDGE", "n_obs": 39, "min_obs": 20, "comparability": "COMPARABLE", "rank": 5, "calmar": "10.409768", "sharpe": "1.793629", "total_return_pct": "13.033776", "max_drawdown_pct": "11.595110", "excess_return_pct": "10.933550", "dsr": null, "psr_vs_benchmark": "0.567128", "dsr_threshold": "0.95", "universe_size": 3, "universe": ["SPY", "IEF", "GLD"]}, {"key": "notrend", "label": "추세 필터 OFF (대조군)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 34, "min_obs": 20, "comparability": "COMPARABLE", "rank": 6, "calmar": "0.872398", "sharpe": "2.538245", "total_return_pct": "8.137300", "max_drawdown_pct": "90.066825", "excess_return_pct": "7.743391", "dsr": null, "psr_vs_benchmark": "0.341098", "dsr_threshold": "0.95", "universe_size": 501, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES"]}, {"key": "wide", "label": "글로벌 분산 추세 확대 (11 슬리브)", "is_incumbent": false, "verdict": "NO_EDGE", "n_obs": 39, "min_obs": 20, "comparability": "COMPARABLE", "rank": 7, "calmar": "-1.413632", "sharpe": "-0.258767", "total_return_pct": "-3.250521", "max_drawdown_pct": "13.600883", "excess_return_pct": "-3.426114", "dsr": null, "psr_vs_benchmark": "0.429878", "dsr_threshold": "0.95", "universe_size": 11, "universe": ["SPY", "QQQ", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD"]}]}
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
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "\ub2e8\uc21c \ubcf4\uc720\ub97c \uc704\ud5d8\uc870\uc815\uc73c\ub85c \ubabb \uc774\uae40; PSR 0.327408 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 98.042349 > \ubca4\uce58 27.632819 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 33, "min_obs_required": 20, "strategy_sharpe_annual": "3.017668", "strategy_total_return_pct": "80.930398", "strategy_max_drawdown_pct": "93.394390", "strategy_calmar": "98.042349", "benchmark_sharpe_annual": "3.862367", "benchmark_total_return_pct": "0.384558", "benchmark_max_drawdown_pct": "0.107639", "benchmark_calmar": "27.632819", "excess_return_pct": "80.545840", "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.327408", "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 34, "legacy_snapshots_excluded": 16, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A", "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT", "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX", "BDX", "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BNY", "BA", "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CPT", "CPB", "COF", "CAH", "CCL", "CARR", "CVNA", "CASY", "CAT", "CBOE", "CBRE", "CDW", "COR", "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD", "CIEN", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS", "KO", "CTSH", "COHR", "COIN", "CL", "CMCSA", "FIX", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP", "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI", "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM", "FANG", "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI", "DTE", "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW", "EA", "ELV", "EME", "EMR", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ERIE", "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB", "FSLR", "FE", "FISV", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA", "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON", "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "IBKR", "ICE", "IFF", "IP", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR", "LHX", "LH", "LRCX", "LVS", "LDOS", "LEN", "LII", "LLY", "LIN", "LYV", "LMT", "L", "LOW", "LULU", "LITE", "LYB", "MTB", "MPC", "MAR", "MRSH", "MLM", "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PSKY", "PH", "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTC", "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL", "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC", "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL", "TXT", "TMO", "TJX", "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VRT", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WY", "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH", "ZTS"]}
```

## 🧭 판정 — 추세 필터 OFF (대조군)

```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "\ub2e8\uc21c \ubcf4\uc720\ub97c \uc704\ud5d8\uc870\uc815\uc73c\ub85c \ubabb \uc774\uae40; PSR 0.341098 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428)", "n_obs": 34, "min_obs_required": 20, "strategy_sharpe_annual": "2.538245", "strategy_total_return_pct": "8.137300", "strategy_max_drawdown_pct": "90.066825", "strategy_calmar": "0.872398", "benchmark_sharpe_annual": "3.535039", "benchmark_total_return_pct": "0.393909", "benchmark_max_drawdown_pct": "0.137340", "benchmark_calmar": "21.528272", "excess_return_pct": "7.743391", "beats_benchmark_calmar": false, "psr_vs_benchmark": "0.341098", "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 35, "legacy_snapshots_excluded": 14, "universe": ["MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A", "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT", "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX", "BDX", "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BNY", "BA", "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CPT", "CPB", "COF", "CAH", "CCL", "CARR", "CVNA", "CASY", "CAT", "CBOE", "CBRE", "CDW", "COR", "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD", "CIEN", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS", "KO", "CTSH", "COHR", "COIN", "CL", "CMCSA", "FIX", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP", "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI", "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM", "FANG", "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI", "DTE", "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW", "EA", "ELV", "EME", "EMR", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ERIE", "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB", "FSLR", "FE", "FISV", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA", "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON", "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "IBKR", "ICE", "IFF", "IP", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR", "LHX", "LH", "LRCX", "LVS", "LDOS", "LEN", "LII", "LLY", "LIN", "LYV", "LMT", "L", "LOW", "LULU", "LITE", "LYB", "MTB", "MPC", "MAR", "MRSH", "MLM", "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PSKY", "PH", "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTC", "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL", "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC", "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL", "TXT", "TMO", "TJX", "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VRT", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WY", "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH", "ZTS"]}
```

> 두 판정을 나란히 비교: ON 의 max_drawdown_pct·sharpe·excess 가 OFF 보다
> 나으면 추세 필터가 *실제로* 도움이 된다는 격리된 증거다.

## 🛡️ 판정 — 위험관리 베타 (추세 게이트 광범위 베타, 스펙 042)

> SPY·QQQ 를 10개월 추세 위일 때만 보유(아래면 현금). 종목 선택이 아니라 베타의
> 자본 방어. 우리 KIS 체결로 forward 실적을 쌓아 *확신을 번다*(운영자 2026-06-05).
> INSUFFICIENT_DATA 면 NAV 관측이 더 쌓여야 함(정상). 200일 미만이면 추세 미확정 →
> on_insufficient=cash 라 현금 보유(보수적). 라이브 전환은 운영자 게이트(헌법 X.4).

```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "PSR 0.746239 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 24.83098 > \ubca4\uce58 3.623684 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 39, "min_obs_required": 20, "strategy_sharpe_annual": "2.513533", "strategy_total_return_pct": "58.958893", "strategy_max_drawdown_pct": "76.439403", "strategy_calmar": "24.83098", "benchmark_sharpe_annual": "0.897543", "benchmark_total_return_pct": "2.029385", "benchmark_max_drawdown_pct": "3.825378", "benchmark_calmar": "3.623684", "excess_return_pct": "56.929508", "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.746239", "dsr": null, "num_trials": 1, "min_track_record_obs": "235.100463", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 40, "legacy_snapshots_excluded": 5, "universe": ["SPY", "QQQ"]}
```

## 🌐 판정 — 멀티에셋 분산 추세 (비상관 자산 합성, 스펙 043)

> 주식(SPY) + 채권(IEF) 을 각자 추세 위일 때만 보유. ARM C(둘 다 주식)와 달리
> *비상관 자산*을 합쳐 분산 이득을 노린다(스펙 043: 단일 주식 추세 샤프 1.18~1.43
> → 분산 추세 1.58~1.81, 낙폭 절반, Shiller 1871~ 검증). INSUFFICIENT_DATA 면
> NAV 관측이 더 쌓여야 함(정상). 라이브 전환은 운영자 게이트(헌법 X.4).

```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "PSR 0.739243 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 53.733327 > \ubca4\uce58 7.731961 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 39, "min_obs_required": 20, "strategy_sharpe_annual": "3.007743", "strategy_total_return_pct": "46.299845", "strategy_max_drawdown_pct": "19.890290", "strategy_calmar": "53.733327", "benchmark_sharpe_annual": "1.483687", "benchmark_total_return_pct": "1.568469", "benchmark_max_drawdown_pct": "1.368226", "benchmark_calmar": "7.731961", "excess_return_pct": "44.731376", "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.739243", "dsr": null, "num_trials": 1, "min_track_record_obs": "251.209062", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 40, "legacy_snapshots_excluded": 5, "universe": ["SPY", "IEF"]}
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
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "PSR 0.567128 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 10.409768 > \ubca4\uce58 4.464288 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 39, "min_obs_required": 20, "strategy_sharpe_annual": "1.793629", "strategy_total_return_pct": "13.033776", "strategy_max_drawdown_pct": "11.595110", "strategy_calmar": "10.409768", "benchmark_sharpe_annual": "1.375764", "benchmark_total_return_pct": "2.100226", "benchmark_max_drawdown_pct": "3.219720", "benchmark_calmar": "4.464288", "excess_return_pct": "10.933550", "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.567128", "dsr": null, "num_trials": 1, "min_track_record_obs": "3597.797192", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 40, "legacy_snapshots_excluded": 4, "universe": ["SPY", "IEF", "GLD"]}
```

## ⚖ 판정 — 글로벌 3자산 추세 고정(등가중) 재지정 후보 (스펙 047/050 후속)

> 라이브 검증 트랙과 weight_scheme 만 다른 등가중 변형. 깊은 분석은 등가중이
> 캡 안 무레버 복리 +1.3~2.3%p 높다고 봤으나 낙폭이 사다리 강등선(10%)에 더
> 가깝다 — 이 트랙이 *일별* 낙폭/강등 빈도를 실측해 재지정 안전성을 답한다.
> EDGE_CONFIRMED + 지문 정합을 벌면 운영자가 재지정 결정(헌법 X.4). 돈 0·페이퍼.

```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "PSR 0.821255 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 29.257344 > \ubca4\uce58 1.582686 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 36, "min_obs_required": 20, "strategy_sharpe_annual": "2.815632", "strategy_total_return_pct": "25.036070", "strategy_max_drawdown_pct": "12.913037", "strategy_calmar": "29.257344", "benchmark_sharpe_annual": "0.547594", "benchmark_total_return_pct": "0.702504", "benchmark_max_drawdown_pct": "3.173331", "benchmark_calmar": "1.582686", "excess_return_pct": "24.333566", "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.821255", "dsr": null, "num_trials": 1, "min_track_record_obs": "112.840282", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 37, "legacy_snapshots_excluded": 0, "universe": ["SPY", "IEF", "GLD"]}
```

## 🌍 판정 — 글로벌 분산 추세 확대 유니버스 (11 슬리브, 계획 ③)

> 검증된 메커니즘(역변동성 + 다중 속도 추세 앙상블) 그대로, 베팅의 폭만
> 3 → 11 슬리브(주식 SPY·QQQ·EFA·EEM / 채권 IEF·TLT·LQD / 실물 GLD·DBC·VNQ
> / 통화 UUP). 성과 ≈ 질 × √N — 제약 안에서 가장 큰 지렛대. ARM E(3자산)와
> 나란히 비교하면 '폭 확장이 우리 체결 기준 forward 로도 이득인가'의 격리된
> 답. 라이브는 검증된 3자산 유지 — 이 트랙이 EDGE_CONFIRMED 를 벌어야 재지정
> 후보가 된다(검증=배치 정합, 헌법 X.4 v5.0.0 사다리).

```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "\ub2e8\uc21c \ubcf4\uc720\ub97c \uc704\ud5d8\uc870\uc815\uc73c\ub85c \ubabb \uc774\uae40; PSR 0.429878 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428)", "n_obs": 39, "min_obs_required": 20, "strategy_sharpe_annual": "-0.258767", "strategy_total_return_pct": "-3.250521", "strategy_max_drawdown_pct": "13.600883", "strategy_calmar": "-1.413632", "benchmark_sharpe_annual": "0.196432", "benchmark_total_return_pct": "0.175593", "benchmark_max_drawdown_pct": "2.049168", "benchmark_calmar": "0.55635", "excess_return_pct": "-3.426114", "beats_benchmark_calmar": false, "psr_vs_benchmark": "0.429878", "dsr": null, "num_trials": 1, "min_track_record_obs": null, "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 40, "legacy_snapshots_excluded": 0, "universe": ["SPY", "QQQ", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD", "DBC", "VNQ", "UUP"]}
```

## TREND-ON 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "GEN", "exchange": "NAS", "fetched": 939, "inserted": 1}, {"symbol": "EVRG", "exchange": "NAS", "fetched": 905, "inserted": 1}, {"symbol": "GEHC", "exchange": "NAS", "fetched": 901, "inserted": 1}, {"symbol": "COHR", "exchange": "NYS", "fetched": 867, "inserted": 1}, {"symbol": "EG", "exchange": "NYS", "fetched": 774, "inserted": 1}, {"symbol": "COO", "exchange": "NAS", "fetched": 719, "inserted": 1}, {"symbol": "DASH", "exchange": "NAS", "fetched": 718, "inserted": 1}, {"symbol": "EXPD", "exchange": "NYS", "fetched": 679, "inserted": 1}, {"symbol": "CPAY", "exchange": "NYS", "fetched": 595, "inserted": 1}, {"symbol": "GEV", "exchange": "NYS", "fetched": 590, "inserted": 1}, {"symbol": "CPB", "exchange": "NAS", "fetched": 494, "inserted": 1}, {"symbol": "EXE", "exchange": "NAS", "fetched": 463, "inserted": 1}, {"symbol": "FISV", "exchange": "NAS", "fetched": 185, "inserted": 1}]}
{"portfolio_id": "forward-paper-canary", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"INTC": "0.100000", "AMD": "0.100000", "GLW": "0.100000", "AMAT": "0.100000", "COHR": "0.100000", "CSCO": "0.100000", "CAT": "0.100000", "ADI": "0.100000", "CRWD": "0.100000", "XOM": "0.100000"}, "results": [{"symbol": "CAT", "side": "BUY", "requested_qty": 1, "routed_qty": 0, "limit_price_usd": "844.08", "state": "SKIPPED_PER_TRADE_CAP", "reason": "per_trade_cap_below_one_share"}], "withheld_orders": []}
(경고: 장부 현금 음수 $-90767.6668 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=590)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-90767.6668", "total_market_value_usd": "98785.9571", "total_nav_usd": "8018.2903", "total_unrealized_pnl_usd": "-3202.710112500000000000000000", "broker_reported_nav_usd": null, "holdings": [{"symbol": "ADI", "qty": 30, "avg_cost_usd": "399.1320466666666666666666667", "mark_price_usd": "389.9352", "market_value_usd": "11698.0560", "marked": true, "weight_pct": "145.8921486042978513761219147", "unrealized_pnl_usd": "-275.9054000000000000000000010"}, {"symbol": "AMAT", "qty": 18, "avg_cost_usd": "558.2801055555555555555555556", "mark_price_usd": "540.6800", "market_value_usd": "9732.2400", "marked": true, "weight_pct": "121.3755007099206672524690207", "unrealized_pnl_usd": "-316.8019000000000000000000008"}, {"symbol": "AMD", "qty": 30, "avg_cost_usd": "523.77984000000000000000000", "mark_price_usd": "482.8000", "market_value_usd": "14484.0000", "marked": true, "weight_pct": "180.6370118577522692088112599", "unrealized_pnl_usd": "-1229.39520000000000000000000"}, {"symbol": "COHR", "qty": 22, "avg_cost_usd": "345.96121875000000000000000", "mark_price_usd": "380.0000", "market_value_usd": "8360.0000", "marked": true, "weight_pct": "104.2616279433035743293055878", "unrealized_pnl_usd": "748.85318750000000000000000"}, {"symbol": "CRWD", "qty": 38, "avg_cost_usd": "195.3712289473684210526315789", "mark_price_usd": "214.2294", "market_value_usd": "8140.7172", "marked": true, "weight_pct": "101.5268454423507215746479022", "unrealized_pnl_usd": "716.6105000000000000000000018"}, {"symbol": "CSCO", "qty": 144, "avg_cost_usd": "116.77784375000000000000000", "mark_price_usd": "121.5985", "market_value_usd": "17510.1840", "marked": true, "weight_pct": "218.3780250510510950195953868", "unrealized_pnl_usd": "694.17450000000000000000000"}, {"symbol": "GLW", "qty": 85, "avg_cost_usd": "185.6028423529411764705882353", "mark_price_usd": "167.0000", "market_value_usd": "14195.0000", "marked": true, "weight_pct": "177.0327522314825643067575141", "unrealized_pnl_usd": "-1581.241600000000000000000000"}, {"symbol": "INTC", "qty": 140, "avg_cost_usd": "115.42981500000000000000000", "mark_price_usd": "101.4800", "market_value_usd": "14207.2000", "marked": true, "weight_pct": "177.1849043679548494271902328", "unrealized_pnl_usd": "-1952.97410000000000000000000"}, {"symbol": "XOM", "qty": 3, "avg_cost_usd": "154.8633333333333333333333333", "mark_price_usd": "152.8533", "market_value_usd": "458.5599", "marked": true, "weight_pct": "5.718923646353886688288150405", "unrealized_pnl_usd": "-6.0300999999999999999999999"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## TREND-OFF 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "GEN", "exchange": "NAS", "fetched": 939, "inserted": 1}, {"symbol": "EVRG", "exchange": "NAS", "fetched": 905, "inserted": 1}, {"symbol": "GEHC", "exchange": "NAS", "fetched": 901, "inserted": 1}, {"symbol": "COHR", "exchange": "NYS", "fetched": 867, "inserted": 1}, {"symbol": "EG", "exchange": "NYS", "fetched": 774, "inserted": 1}, {"symbol": "COO", "exchange": "NAS", "fetched": 719, "inserted": 1}, {"symbol": "DASH", "exchange": "NAS", "fetched": 718, "inserted": 1}, {"symbol": "EXPD", "exchange": "NYS", "fetched": 679, "inserted": 1}, {"symbol": "CPAY", "exchange": "NYS", "fetched": 595, "inserted": 1}, {"symbol": "GEV", "exchange": "NYS", "fetched": 590, "inserted": 1}, {"symbol": "CPB", "exchange": "NAS", "fetched": 494, "inserted": 1}, {"symbol": "EXE", "exchange": "NAS", "fetched": 463, "inserted": 1}, {"symbol": "FISV", "exchange": "NAS", "fetched": 185, "inserted": 1}]}
{"portfolio_id": "forward-paper-canary-notrend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"DELL": "0.100000", "CIEN": "0.100000", "AMD": "0.100000", "GLW": "0.100000", "AMAT": "0.100000", "COHR": "0.100000", "CSCO": "0.100000", "CAT": "0.100000", "ADI": "0.100000", "CRWD": "0.100000"}, "results": [{"symbol": "CAT", "side": "BUY", "requested_qty": 1, "routed_qty": 0, "limit_price_usd": "844.08", "state": "SKIPPED_PER_TRADE_CAP", "reason": "per_trade_cap_below_one_share"}], "withheld_orders": []}
(경고: 장부 현금 음수 $-92466.7535 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=593)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-92466.7535", "total_market_value_usd": "102480.8699", "total_nav_usd": "10014.1164", "total_unrealized_pnl_usd": "-1303.843600000000000000000001", "broker_reported_nav_usd": null, "holdings": [{"symbol": "ADI", "qty": 30, "avg_cost_usd": "399.1284666666666666666666667", "mark_price_usd": "389.9352", "market_value_usd": "11698.0560", "marked": true, "weight_pct": "116.8156583440551979204076358", "unrealized_pnl_usd": "-275.7980000000000000000000010"}, {"symbol": "AMAT", "qty": 17, "avg_cost_usd": "555.8969470588235294117647059", "mark_price_usd": "540.6791", "market_value_usd": "9191.5447", "marked": true, "weight_pct": "91.78587838263993016897626634", "unrealized_pnl_usd": "-258.7034000000000000000000003"}, {"symbol": "AMD", "qty": 30, "avg_cost_usd": "523.7594333333333333333333333", "mark_price_usd": "482.7000", "market_value_usd": "14481.0000", "marked": true, "weight_pct": "144.6058685716894602902758350", "unrealized_pnl_usd": "-1231.782999999999999999999999"}, {"symbol": "CIEN", "qty": 30, "avg_cost_usd": "437.9061366666666666666666667", "mark_price_usd": "415.0000", "market_value_usd": "12450.0000", "marked": true, "weight_pct": "124.3244985648459209042147743", "unrealized_pnl_usd": "-687.1841000000000000000000010"}, {"symbol": "COHR", "qty": 20, "avg_cost_usd": "350.88526000000000000000000", "mark_price_usd": "380.2700", "market_value_usd": "7605.4000", "marked": true, "weight_pct": "75.94679047269712183493293527", "unrealized_pnl_usd": "587.69480000000000000000000"}, {"symbol": "CRWD", "qty": 8, "avg_cost_usd": "191.86375", "mark_price_usd": "214.2294", "market_value_usd": "1713.8352", "marked": true, "weight_pct": "17.11419292070541540739430590", "unrealized_pnl_usd": "178.92520"}, {"symbol": "CSCO", "qty": 144, "avg_cost_usd": "116.7711284722222222222222222", "mark_price_usd": "121.5985", "market_value_usd": "17510.1840", "marked": true, "weight_pct": "174.8550076769628921029917328", "unrealized_pnl_usd": "695.1415000000000000000000032"}, {"symbol": "DELL", "qty": 30, "avg_cost_usd": "412.2568366666666666666666667", "mark_price_usd": "454.5000", "market_value_usd": "13635.0000", "marked": true, "weight_pct": "136.1577942113794483155797949", "unrealized_pnl_usd": "1267.294899999999999999999999"}, {"symbol": "GLW", "qty": 85, "avg_cost_usd": "185.5915470588235294117647059", "mark_price_usd": "167.0100", "market_value_usd": "14195.8500", "marked": true, "weight_pct": "141.7583881888970254030600243", "unrealized_pnl_usd": "-1579.431500000000000000000002"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## RISK-MANAGED-BETA 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "QQQ", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "risk-managed-beta", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"QQQ": "0.500000", "SPY": "0.500000"}, "results": [], "withheld_orders": []}
(경고: 장부 현금 음수 $-322437.2495 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=175)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-322437.2495", "total_market_value_usd": "342017.6788", "total_nav_usd": "19580.4293", "total_unrealized_pnl_usd": "7580.429300000000000000000002", "broker_reported_nav_usd": null, "holdings": [{"symbol": "QQQ", "qty": 239, "avg_cost_usd": "717.4312937238493723849372385", "mark_price_usd": "722.6492", "market_value_usd": "172713.1588", "marked": true, "weight_pct": "882.0703374465849939255417653", "unrealized_pnl_usd": "1247.079599999999999999999998"}, {"symbol": "SPY", "qty": 219, "avg_cost_usd": "744.1605949771689497716894977", "mark_price_usd": "773.0800", "market_value_usd": "169304.5200", "marked": true, "weight_pct": "864.6619407879887495622989226", "unrealized_pnl_usd": "6333.349700000000000000000004"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## MULTI-ASSET-TREND 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "multi-asset-trend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"SPY": "0.500000"}, "results": [], "withheld_orders": []}
(경고: 장부 현금 음수 $-151584.0976 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=127)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-151584.0976", "total_market_value_usd": "169304.5200", "total_nav_usd": "17720.4224", "total_unrealized_pnl_usd": "6332.874000000000000000000006", "broker_reported_nav_usd": null, "holdings": [{"symbol": "SPY", "qty": 219, "avg_cost_usd": "744.1627671232876712328767123", "mark_price_usd": "773.0800", "market_value_usd": "169304.5200", "marked": true, "weight_pct": "955.4203403187499638834794367", "unrealized_pnl_usd": "6332.874000000000000000000006"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## GLOBAL-TREND 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "404.20", "planned_buy_notional_usd": "400.20", "planned_sell_notional_usd": "2046.88", "target_weights": {"SPY": "0.233037", "GLD": "0.050940"}, "results": [{"symbol": "IEF", "side": "SELL", "requested_qty": 22, "routed_qty": 22, "limit_price_usd": "93.04", "state": "PAPER_FILLED", "reason": null}, {"symbol": "GLD", "side": "BUY", "requested_qty": 1, "routed_qty": 1, "limit_price_usd": "400.20", "state": "REJECTED_BY_GATE", "reason": "global exposure would become $71236.5298, exceeds cap $12000.00"}], "withheld_orders": []}
(경고: 장부 현금 음수 $-55192.4231 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=13546)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-55192.4231", "total_market_value_usd": "68804.1200", "total_nav_usd": "13611.6969", "total_unrealized_pnl_usd": "2538.659299999999999999999996", "broker_reported_nav_usd": null, "holdings": [{"symbol": "SPY", "qty": 89, "avg_cost_usd": "744.5557382022471910112359551", "mark_price_usd": "773.0800", "market_value_usd": "68804.1200", "marked": true, "weight_pct": "505.4779026118337971513309263", "unrealized_pnl_usd": "2538.659299999999999999999996"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## GLOBAL-TREND-FIXED 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend-fixed", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "1617.17", "planned_buy_notional_usd": "1601.16", "planned_sell_notional_usd": "0.00", "target_weights": {"SPY": "0.333334", "GLD": "0.166666"}, "results": [{"symbol": "GLD", "side": "BUY", "requested_qty": 4, "routed_qty": 4, "limit_price_usd": "400.29", "state": "REJECTED_BY_GATE", "reason": "global exposure would become $101322.0558, exceeds cap $12000.00"}], "withheld_orders": []}
(경고: 장부 현금 음수 $-84716.4736 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=131)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-84716.4736", "total_market_value_usd": "99720.8958", "total_nav_usd": "15004.4222", "total_unrealized_pnl_usd": "3595.660799999999999999999995", "broker_reported_nav_usd": null, "holdings": [{"symbol": "SPY", "qty": 129, "avg_cost_usd": "745.1568604651162790697674419", "mark_price_usd": "773.0302", "market_value_usd": "99720.8958", "marked": true, "weight_pct": "664.6100360998906042513253193", "unrealized_pnl_usd": "3595.660799999999999999999995"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```

## GLOBAL-TREND-WIDE 준비 로그 (backfill → rebalance → nav-snapshot)

```
{"results": [{"symbol": "DBC", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "EEM", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "EFA", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "GLD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "IEF", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "LQD", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "QQQ", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "SPY", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "TLT", "exchange": "NAS", "fetched": 1000, "inserted": 1}, {"symbol": "UUP", "exchange": "AMS", "fetched": 1000, "inserted": 1}, {"symbol": "VNQ", "exchange": "AMS", "fetched": 1000, "inserted": 1}]}
{"portfolio_id": "global-trend-wide", "mode": "paper", "account_wide": false, "requested_side": "both", "effective_side": "both", "purchasable_cash_usd": null, "required_cash_usd": "0.00", "planned_buy_notional_usd": "0.00", "planned_sell_notional_usd": "0.00", "target_weights": {"DBC": "0.031677", "QQQ": "0.046526", "SPY": "0.072165", "EEM": "0.027389", "VNQ": "0.067357", "UUP": "0.120497", "EFA": "0.055927", "GLD": "0.015748"}, "results": [], "withheld_orders": []}
(경고: 장부 현금 음수 $-126615.9625 — 자본 기준이 누적 순투입보다 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)
(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq=508)
{"schema_version": "1.0", "source": "ledger", "cash_usd": "-126615.9625", "total_market_value_usd": "138225.9000", "total_nav_usd": "11609.9375", "total_unrealized_pnl_usd": "1419.886600000000000000000042", "broker_reported_nav_usd": null, "holdings": [{"symbol": "DBC", "qty": 380, "avg_cost_usd": "27.93493210526315789473684211", "mark_price_usd": "28.9200", "market_value_usd": "10989.6000", "marked": true, "weight_pct": "94.65684031460117679358739011", "unrealized_pnl_usd": "374.3257999999999999999999982"}, {"symbol": "EEM", "qty": 164, "avg_cost_usd": "67.16756219512195121951219512", "mark_price_usd": "65.7800", "market_value_usd": "10787.9200", "marked": true, "weight_pct": "92.91970779343127385483341319", "unrealized_pnl_usd": "-227.5601999999999999999999997"}, {"symbol": "EFA", "qty": 168, "avg_cost_usd": "104.1313916666666666666666666", "mark_price_usd": "108.5500", "market_value_usd": "18236.4000", "marked": true, "weight_pct": "157.0757809850397558126389569", "unrealized_pnl_usd": "742.3262000000000000000000112"}, {"symbol": "SPY", "qty": 28, "avg_cost_usd": "745.29022500000000000000000", "mark_price_usd": "773.0900", "market_value_usd": "21646.5200", "marked": true, "weight_pct": "186.4482043938651693861401063", "unrealized_pnl_usd": "778.39370000000000000000000"}, {"symbol": "UUP", "qty": 1934, "avg_cost_usd": "28.30004906928645294725956565", "mark_price_usd": "28.0800", "market_value_usd": "54306.7200", "marked": true, "weight_pct": "467.7606576262792112360639323", "unrealized_pnl_usd": "-425.5748999999999999999999671"}, {"symbol": "VNQ", "qty": 226, "avg_cost_usd": "97.70249557522123893805309735", "mark_price_usd": "98.4900", "market_value_usd": "22258.7400", "marked": true, "weight_pct": "191.7214455288841994196781852", "unrealized_pnl_usd": "177.9759999999999999999999989"}], "unmarked_symbols": [], "drifts": [], "total_qty_drift": 0, "total_value_drift_usd": "0", "data_quality_warnings": [], "mode": "paper"}
```
