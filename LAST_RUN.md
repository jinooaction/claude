# Deploy audit_log verification — latest run

서버 audit_log 의 DEPLOY_* 행을 읽기 전용으로 조회한 결과입니다.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | e05a7ad38452d82b7e84ad47fdfd63b263d9f466 |
| trigger | workflow_dispatch |
| timestamp_utc | 2026-10-10T16:54:25Z |
| ssh_exit | 0 |
| audit_status | ok |
| correlation_id | e64e7a81060ebb077778b0b58bf9445b |
| deploy_row_count | 2 |
| terminal_event | DEPLOY_COMPLETED |

## Raw query output

```
AUDIT_STATUS=ok
AUDIT_CORRELATION_ID=e64e7a81060ebb077778b0b58bf9445b
AUDIT_ROW_COUNT=2
AUDIT_TERMINAL_EVENT=DEPLOY_COMPLETED

## DEPLOY audit rows
seq    ts_utc                    event_type        phase  sha_before    sha_after     recovery_basis  recovered_production  reason
-----  ------------------------  ----------------  -----  ------------  ------------  --------------  --------------------  ------
19960  2026-10-10T16:53:20.373Z  DEPLOY_STARTED           4c1926f8da19  e05a7ad38452                                              
19965  2026-10-10T16:53:24.718Z  DEPLOY_COMPLETED  live   4c1926f8da19  e05a7ad38452                                              
```
