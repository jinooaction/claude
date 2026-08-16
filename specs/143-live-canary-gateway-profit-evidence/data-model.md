# Data Model: Live Canary Gateway And Profit Evidence

## SignedLiveOrderRequest

| Field | Type | Rule |
|------|------|------|
| repository | string | `jinooaction/claude` 고정 |
| workflow | string | `rebalance-live-canary.yml` 고정 |
| run_id | integer string | GitHub run id |
| commit | 40-char hex | main workflow checkout |
| capital_usd | decimal string | 센티넬과 정확히 일치, 0 < capital <= NAV |
| expires_epoch | integer | 현재보다 뒤, 최대 10분 |
| nonce | restricted string | run id + attempt, 한 번만 사용 |
| signature | base64 | 위 필드의 canonical payload Ed25519 서명 |

상태: `UNVERIFIED -> VERIFIED -> CONSUMED -> ORDER_ATTEMPTED`. 어느 검증이든 실패하면 `REJECTED`.

## LiveProfitObservation

| Field | Type | Rule |
|------|------|------|
| observed_at_utc | timestamp | 관측 시각 |
| fills_count | integer | live 체결만 |
| realized_pnl_usd | decimal | 기존 성과 엔진 |
| unrealized_pnl_usd | decimal | KIS mark 기반 |
| total_pnl_usd | decimal | realized + unrealized |
| return_pct | decimal/null | 총투입 0이면 null |
| unmarked_symbols | list | 비어야 수익 달성 가능 |
| data_quality_warnings | list | 비어야 수익 달성 가능 |

## FirstProfitEvidence

상태 전이:

`UNKNOWN -> NO_FILLS_YET -> FILLED_NOT_PROFITABLE -> FIRST_PROFIT_OBSERVED`

어느 상태에서든 시세 결측은 `PNL_INCOMPLETE`로 현재 상태를 표시한다. 단,
`FIRST_PROFIT_OBSERVED`가 한 번 기록되면 최초 시각과 당시 수치는 이후 관측에서도 유지한다.
