# Contract: Money Path Halt Gate

- 복구 보고 누락·파싱 실패·36시간 초과·`halt_present_after=true`는 `BLOCKED`다.
- `status`가 `RECOVERED` 또는 `CLEAR`, `reconciliation_state=OK`, `evidence_quality=VALID`, `halt_present_after=false`일 때만 기존 돈 경로 판정을 계속한다.
- 차단 상태에서 `can_submit_real_orders`는 반드시 false다.

