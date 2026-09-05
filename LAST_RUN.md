# Deploy audit_log verification — latest run

서버 audit_log 의 DEPLOY_* 행을 읽기 전용으로 조회한 결과입니다.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | 4a5f43add677155382487f23a8a47debd2daa378 |
| trigger | workflow_dispatch |
| timestamp_utc | 2026-09-05T02:27:29Z |
| ssh_exit | 0 |
| audit_status | ok |
| correlation_id | c8d8b44bfe54d984f493310a7dd7f5fd |
| deploy_row_count | 2 |
| terminal_event | DEPLOY_COMPLETED |

## Raw query output

```
AUDIT_STATUS=ok
AUDIT_CORRELATION_ID=c8d8b44bfe54d984f493310a7dd7f5fd
AUDIT_ROW_COUNT=2
AUDIT_TERMINAL_EVENT=DEPLOY_COMPLETED

## DEPLOY audit rows
seq    ts_utc                    event_type        phase  sha_before    sha_after     recovery_basis  recovered_production  reason
-----  ------------------------  ----------------  -----  ------------  ------------  --------------  --------------------  ------
17798  2026-09-05T02:26:58.163Z  DEPLOY_STARTED           7acd7093583d  4a5f43add677                                              
17803  2026-09-05T02:27:01.462Z  DEPLOY_COMPLETED  live   7acd7093583d  4a5f43add677                                              
```
