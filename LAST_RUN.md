# Deploy audit_log verification — latest run

서버 audit_log 의 DEPLOY_* 행을 읽기 전용으로 조회한 결과입니다.

| 항목 | 값 |
|------|-----|
| run_id | 29422038963 |
| commit | 01386464f03231b8867ca85da11853587777c4c2 |
| trigger | workflow_dispatch |
| timestamp_utc | 2026-07-15T14:05:53Z |
| ssh_exit | 0 |
| audit_status | ok |
| correlation_id | 457e0a18e08cd528bc2c65934a234e7e |
| deploy_row_count | 2 |
| terminal_event | DEPLOY_COMPLETED |

## Raw query output

```
Warning: Permanently added '202.182.125.132' (ED25519) to the list of known hosts.
AUDIT_STATUS=ok
AUDIT_CORRELATION_ID=457e0a18e08cd528bc2c65934a234e7e
AUDIT_ROW_COUNT=2
AUDIT_TERMINAL_EVENT=DEPLOY_COMPLETED

## DEPLOY audit rows
seq    ts_utc                    event_type        phase  sha_before    sha_after     reason
-----  ------------------------  ----------------  -----  ------------  ------------  ------
16003  2026-07-15T12:21:36.422Z  DEPLOY_STARTED           7be7bde71d6b  158052add91c        
16009  2026-07-15T12:21:41.143Z  DEPLOY_COMPLETED  live   7be7bde71d6b  158052add91c        
```
