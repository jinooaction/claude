# Deploy audit_log verification — latest run

서버 audit_log 의 DEPLOY_* 행을 읽기 전용으로 조회한 결과입니다.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | 68f09490ff4d9fbb678155b48735525cc82efa05 |
| trigger | workflow_dispatch |
| timestamp_utc | 2026-09-12T09:30:02Z |
| ssh_exit | 0 |
| audit_status | ok |
| correlation_id | 4fd252fe4c0399244381ae3b58bde36c |
| deploy_row_count | 2 |
| terminal_event | DEPLOY_COMPLETED |

## Raw query output

```
AUDIT_STATUS=ok
AUDIT_CORRELATION_ID=4fd252fe4c0399244381ae3b58bde36c
AUDIT_ROW_COUNT=2
AUDIT_TERMINAL_EVENT=DEPLOY_COMPLETED

## DEPLOY audit rows
seq    ts_utc                    event_type        phase  sha_before    sha_after     recovery_basis  recovered_production  reason
-----  ------------------------  ----------------  -----  ------------  ------------  --------------  --------------------  ------
18848  2026-09-12T09:10:13.681Z  DEPLOY_STARTED           6986ca9b9ff7  2f7c11ff2522                                              
18853  2026-09-12T09:10:20.228Z  DEPLOY_COMPLETED  live   6986ca9b9ff7  2f7c11ff2522                                              
```
