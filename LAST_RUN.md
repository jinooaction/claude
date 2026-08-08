# 백테스트 앵커드 엣지 판정 — 깊은 OOS + 짧은 forward 지속성 (최신 실행)

> 전략 규칙은 깊은 walk-forward 표본외(OOS)로 이미 검증됐다. 이 판정은 그
> 검증된 엣지가 라이브 forward 페이퍼에서 *지속*하는지만 5~10일로 확인한다
> (일별 20일 재발견 불필요 — 운영자 지적 해법). bars-export→ingest-history
> →forward-verdict-anchored 체인, /tmp 격리, 읽기 전용. **주문 0·돈 0·무장 0·
> 게이트 변경 0**(판정 발행만). 게이트 소비는 별도 단계(실제 돈 게이트).

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | 758dda2534af38f444ac75361295fb49b489e234 |
| trigger | schedule |
| timestamp_utc | 2026-08-08T00:02:22Z |
| GLOBAL-TREND ssh_exit | 0 |

## GLOBAL-TREND (3자산 SPY·IEF·GLD — 라이브 지정 전략)

```
--- anchored verdict (json via observe gateway) ---
{"schema_version": "1.0", "method": "backtest_anchored", "verdict": "INSUFFICIENT_DATA", "reason": "OOS \uc720\uc758\uc131 \uacc4\uc0b0 \ubd88\uac00(\uad00\uce21<2 \ub610\ub294 \ubd84\uc0b0 0).", "oos_n_obs": 748, "oos_sharpe_annual": null, "oos_significance": null, "forward_n_obs": 39, "forward_mean_daily": null, "oos_mean_daily": null, "consistency_z": null, "dsr_threshold": "0.95", "num_trials": 1, "mode": "paper", "dataset_version": "2022-11-20", "wf_segments": 3, "wf_verdict": "\uac15\uac74\ud55c \uc5e3\uc9c0 \uc5c6\uc74c: \uad6c\uac04 \uacfc\ubc18 \uc2e4\ud328(0/3); \ud3c9\uade0 \uc0e4\ud504\uac00 \ub2e8\uc21c \ubcf4\uc720 \uc774\ud558; \ub514\ud50c\ub808\uc774\ud2f0\ub4dc \uc0e4\ud504 \ubbf8\ub2ec(DSR=N/A < 0.95) \u2014 \uc2dc\ub3c4 \ud69f\uc218 \ubcf4\uc815 \ud6c4 \uc6b0\uc5f0\uacfc \uad6c\ubcc4 \uc548 \ub428. \ub77c\uc774\ube0c \ubc30\ud3ec \uc815\ub2f9\ud654 \uc548 \ub428."}
--- ssh_exit=0 ---
```
