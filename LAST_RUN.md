# Deploy audit_log verification — latest run

서버 audit_log 의 DEPLOY_* 행을 읽기 전용으로 조회한 결과입니다.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | 738583ddf7a204b1c775de2d29a36ed20c1b5139 |
| trigger | workflow_dispatch |
| timestamp_utc | 2026-10-02T20:01:47Z |
| ssh_exit | 0 |
| audit_status | ok |
| correlation_id | 703b76cc720d9d60e318175ea3723191 |
| deploy_row_count | 2 |
| terminal_event | DEPLOY_COMPLETED |

## Raw query output

```
AUDIT_STATUS=ok
AUDIT_CORRELATION_ID=703b76cc720d9d60e318175ea3723191
AUDIT_ROW_COUNT=2
AUDIT_TERMINAL_EVENT=DEPLOY_COMPLETED

## DEPLOY audit rows
seq    ts_utc                    event_type        phase  sha_before    sha_after     recovery_basis  recovered_production  reason
-----  ------------------------  ----------------  -----  ------------  ------------  --------------  --------------------  ------
19716  2026-10-02T20:00:44.197Z  DEPLOY_STARTED           bde560036e8d  738583ddf7a2                                              
19721  2026-10-02T20:00:47.938Z  DEPLOY_COMPLETED  live   bde560036e8d  738583ddf7a2                                              
```
