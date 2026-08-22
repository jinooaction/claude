# Contract: Reconciliation Halt Recovery

```json
{
  "schema_version": "1.0",
  "status": "RECOVERED",
  "observed_at_utc": "2026-08-22T04:00:00Z",
  "halt_present_before": true,
  "halt_present_after": false,
  "reconciliation_state": "OK",
  "measurement_contract_id": "sha256:...",
  "evidence_quality": "VALID",
  "halt_cleared": true,
  "orders_submitted": 0,
  "reasons": []
}
```

- `orders_submitted`는 항상 0이어야 한다.
- `halt_cleared=true`는 정합성 오류 halt, 최신 OK, 유효한 동일 측정 계약을 모두 만족할 때만 가능하다.

