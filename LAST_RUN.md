# Deploy audit_log verification — latest run

서버 audit_log 의 DEPLOY_* 행을 읽기 전용으로 조회한 결과입니다.

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | 5fa2e20dae3f45145510ab7b6e4e990f68c33cb9 |
| trigger | workflow_dispatch |
| timestamp_utc | 2026-09-13T23:40:56Z |
| ssh_exit | 0 |
| audit_status | ok |
| correlation_id | f74bdc6b79d0b0846e1c6424e845f6e0 |
| deploy_row_count | 2 |
| terminal_event | DEPLOY_COMPLETED |

## Raw query output

```
AUDIT_STATUS=ok
AUDIT_CORRELATION_ID=f74bdc6b79d0b0846e1c6424e845f6e0
AUDIT_ROW_COUNT=2
AUDIT_TERMINAL_EVENT=DEPLOY_COMPLETED

## DEPLOY audit rows
seq    ts_utc                    event_type        phase  sha_before    sha_after     recovery_basis  recovered_production  reason
-----  ------------------------  ----------------  -----  ------------  ------------  --------------  --------------------  ------
18962  2026-09-13T23:39:25.396Z  DEPLOY_STARTED           cfbd0c34489a  5fa2e20dae3f                                              
18967  2026-09-13T23:39:35.119Z  DEPLOY_COMPLETED  live   cfbd0c34489a  5fa2e20dae3f                                              
```
