"""Exact six-basis-point intraday limit prices for paper and execution."""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal


def limit_price(mark: Decimal, *, buy: bool) -> Decimal:
    if not isinstance(mark, Decimal) or not mark.is_finite() or mark <= 0 or type(buy) is not bool:
        raise ValueError("INVALID_LIMIT_PRICE_INPUT")
    return (mark * Decimal("1.0006" if buy else "0.9994")).quantize(
        Decimal(".01"), rounding=ROUND_FLOOR if buy else ROUND_CEILING,
    )
