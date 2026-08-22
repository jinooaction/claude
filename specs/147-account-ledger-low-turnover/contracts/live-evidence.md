# Contract: Live Strategy Evidence

```json
{
  "schema_version": "1.1",
  "measurement_contract_id": "sha256:...",
  "measurement_scope": "strategy",
  "evidence_quality": "VALID",
  "excluded_symbols": ["BHP", "MRK", "ORANY", "RELX"],
  "excluded_fills_count": 3,
  "excluded_pnl_usd": "15.93000000"
}
```

- 제외는 기록 삭제가 아니라 보고 범위 분리다.
- 계약 ID가 다른 NAV 스냅샷은 같은 forward 곡선에 포함하지 않는다.
- 설정 누락·충돌은 `evidence_quality=BLOCKED`이며 자본 승격 표본이 아니다.

## Resume readiness

```json
{
  "status": "RESUME_ELIGIBLE",
  "halt_present": true,
  "reconciliation_state": "OK",
  "orders_submitted": 0,
  "halt_cleared": false,
  "reasons": []
}
```
