# Data Model

## Recovery Report

- `schema_version`: 보고 계약 버전.
- `status`: `RECOVERED`, `CLEAR`, `BLOCKED`, `INCONCLUSIVE`.
- `observed_at_utc`: production에서 새 검사가 끝난 시각.
- `halt_present_before`, `halt_present_after`: 전후 중지 상태.
- `halt_reason_before`: 민감정보가 없는 기존 이유.
- `reconciliation_state`: `OK`, `MISMATCH`, `INCONCLUSIVE`.
- `measurement_contract_id`: 최신 전략 측정 계약 식별자.
- `evidence_quality`: `VALID` 또는 `BLOCKED`.
- `halt_cleared`: 이번 실행의 실제 해제 여부.
- `orders_submitted`: 항상 0.
- `reasons`: 차단·판정 근거.

## Recovery Audit Event

- 이벤트 종류: `RECONCILIATION_HALT_RECOVERED`.
- 기존 halt 이유, 최신 정합성 완료 시각, 측정 계약 ID, 주문 0건을 기록한다.

