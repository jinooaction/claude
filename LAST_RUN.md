# 자본 사다리 게이트 — 최신 실행 (스펙 050; 스펙 049 승계)

운영자 위임(2026-06-11) 헌법 X.4 v5.0.0. 단0=0% → 단1=25% → 단2=50% → 단3=100%
(실계좌 NAV 대비). 내려가는 건 낙폭 하나로 즉시, 올라가는 건 세 증거 전부.
판정 계산은 read-only — 서버 상태 무변경, 주문 0건.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| timestamp_utc | 2026-08-08T00:32:12Z |
| trigger | schedule |
| **결정(action)** | **WAIT_EDGE** |
| 단(rung) | 0 → 0 |
| 자본 | $? (실계좌 NAV $1458.99000000) |
| 엣지 출처 | none |
| 센티넬 변경 | false |
| PR | (없음 — 변경 없음) |
| 머지 | n/a |

## 의미

⏳ **배치 보류** — 아직 forward EDGE_CONFIRMED 아님(더 쌓여야 함, 정상). 돈 0 이동.

- 사유: 단 0 + forward 판정='NO_EDGE' — EDGE_CONFIRMED 아님. 배치 보류(정상, 더 쌓여야 함).

## 결정 JSON
```json
{"schema_version": "1.0", "action": "WAIT_EDGE", "current_rung": 0, "target_rung": 0, "reason": "\ub2e8 0 + forward \ud310\uc815='NO_EDGE' \u2014 EDGE_CONFIRMED \uc544\ub2d8. \ubc30\uce58 \ubcf4\ub958(\uc815\uc0c1, \ub354 \uc313\uc5ec\uc57c \ud568).", "account_nav_usd": "1458.99000000", "target_capital_usd": null, "live_dd_pct": "0.000000", "live_obs": 6, "edge_source": "none"}
```

## forward 판정 JSON (검증된 앙상블, read-only)
```json
{"schema_version": "1.1", "verdict": "NO_EDGE", "reason": "PSR 0.567128 < 0.95(\uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428) [\ub2e8, \uce7c\ub9c8 \uc6b0\uc704: \uc804\ub7b5 10.409768 > \ubca4\uce58 4.464288 \u2014 \ub4dc\ub85c\ub2e4\uc6b4 \ubc29\uc5b4\ub294 \ub354 \ub098\uc74c]", "n_obs": 39, "min_obs_required": 20, "strategy_sharpe_annual": "1.793629", "strategy_total_return_pct": "13.033776", "strategy_max_drawdown_pct": "11.595110", "strategy_calmar": "10.409768", "benchmark_sharpe_annual": "1.375764", "benchmark_total_return_pct": "2.100226", "benchmark_max_drawdown_pct": "3.219720", "benchmark_calmar": "4.464288", "excess_return_pct": "10.933550", "beats_benchmark_calmar": true, "psr_vs_benchmark": "0.567128", "dsr": null, "num_trials": 1, "min_track_record_obs": "3597.797192", "dsr_threshold": "0.95", "has_benchmark": true, "mode": "paper", "snapshot_count": 40, "legacy_snapshots_excluded": 4, "universe": ["SPY", "IEF", "GLD"]}
```

## 앵커드 판정 JSON (깊은 OOS + 짧은 forward 지속성, read-only)
```json
{"schema_version": "1.0", "method": "backtest_anchored", "verdict": "INSUFFICIENT_DATA", "reason": "OOS \uc720\uc758\uc131 \uacc4\uc0b0 \ubd88\uac00(\uad00\uce21<2 \ub610\ub294 \ubd84\uc0b0 0).", "oos_n_obs": 748, "oos_sharpe_annual": null, "oos_significance": null, "forward_n_obs": 39, "forward_mean_daily": null, "oos_mean_daily": null, "consistency_z": null, "dsr_threshold": "0.95", "num_trials": 1, "mode": "paper", "dataset_version": "2022-11-20", "wf_segments": 3, "wf_verdict": "\uac15\uac74\ud55c \uc5e3\uc9c0 \uc5c6\uc74c: \uad6c\uac04 \uacfc\ubc18 \uc2e4\ud328(0/3); \ud3c9\uade0 \uc0e4\ud504\uac00 \ub2e8\uc21c \ubcf4\uc720 \uc774\ud558; \ub514\ud50c\ub808\uc774\ud2f0\ub4dc \uc0e4\ud504 \ubbf8\ub2ec(DSR=N/A < 0.95) \u2014 \uc2dc\ub3c4 \ud69f\uc218 \ubcf4\uc815 \ud6c4 \uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428. \ub77c\uc774\ube0c \ubc30\ud3ec \uc815\ub2f9\ud654 \uc548 \ub428."}
```

## 라이브 실적 JSON (현재 단 진입 이후, read-only)
```json
{"schema_version": "1.0", "mode": "live", "snapshot_count": 6, "first_at_utc": "2026-07-20T16:26:54.253Z", "last_at_utc": "2026-08-07T15:59:49.240Z", "starting_nav_usd": "500.0", "current_nav_usd": "500.0", "absolute_change_usd": "0.0", "total_return_pct": "0.000000", "max_drawdown_pct": "0.000000", "period_days": "17.981191979166667", "cagr_pct": "0.0"}
```
