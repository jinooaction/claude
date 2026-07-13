# Data Model: Account Exposure Reservation

## OpenOrderReservation

Represents unresolved BUY notional that can still become deployed capital.

Fields:
- `correlation_id`: order identifier, used to exclude the currently evaluated order.
- `symbol`: order symbol.
- `qty`: positive share quantity.
- `price_usd`: conservative notional price, normally the LIMIT price.
- `notional_usd`: `qty * price_usd`.
- `state`: unresolved order state.

Validation:
- Only BUY orders increase reserved exposure.
- SELL orders never reduce reserved exposure until fills update positions.
- `SUBMISSION_UNKNOWN` is unresolved and must be included.

## ReservedExposure

Aggregate exposure used by K1 gates.

Fields:
- `symbol_exposure_usd`: current symbol position exposure plus open BUY notional for the symbol.
- `global_exposure_usd`: current global position exposure plus open BUY notional across symbols.
- `open_order_count`: number of open BUY orders included.

## State Rules

Included states:
- `INTENT`
- `SUBMITTED`
- `PARTIALLY_FILLED`
- `SUBMISSION_UNKNOWN`

Excluded states:
- `REJECTED_BY_GATE`
- `REJECTED_BY_BROKER`
- `FILLED`
- `CANCELLED`
- terminal states proven by lifecycle or fill sync

Current-order exclusion:
- The correlation id being evaluated is excluded so the current request is counted only once by the existing risk gate delta.
