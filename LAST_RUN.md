# Deploy audit_log verification — latest run

서버 audit_log 의 DEPLOY_* 행을 읽기 전용으로 조회한 결과입니다.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | dda232fbe07638a39b46a5d93d9593ec93c00bfd |
| trigger | workflow_dispatch |
| timestamp_utc | 2026-09-25T02:02:24Z |
| ssh_exit | 0 |
| audit_status | ok |
| correlation_id | 0279dd91abe3af75fda78723d8aa9382 |
| deploy_row_count | 2 |
| terminal_event | DEPLOY_COMPLETED |

## Raw query output

```
AUDIT_STATUS=ok
AUDIT_CORRELATION_ID=0279dd91abe3af75fda78723d8aa9382
AUDIT_ROW_COUNT=2
AUDIT_TERMINAL_EVENT=DEPLOY_COMPLETED

## DEPLOY audit rows
seq    ts_utc                    event_type        phase  sha_before    sha_after     recovery_basis  recovered_production  reason
-----  ------------------------  ----------------  -----  ------------  ------------  --------------  --------------------  ------
19372  2026-09-25T02:01:08.874Z  DEPLOY_STARTED           9c3acd02697a  dda232fbe076                                              
19377  2026-09-25T02:01:14.272Z  DEPLOY_COMPLETED  live   9c3acd02697a  dda232fbe076                                              
```
