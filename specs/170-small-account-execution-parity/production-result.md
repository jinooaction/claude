# Production Result: Small-Account Execution Parity

**Observed**: 2026-08-27 UTC/KST release cycle

## Frozen Public Cross-Check

The preregistered thresholds and symbol pairs were evaluated on 252 common adjusted-close
sessions ending 2026-08-26. This cross-check is independent of the KIS production path and
does not authorize capital by itself.

| Signal -> execution | Return correlation | Tracking error | Annual return gap | Median execution dollar volume | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| SPY -> SCHX | 0.996963 | 1.0011% | 0.6266 percentage points | $396,861,515 | PASS |
| IEF -> SPTI | 0.976240 | 1.5834% | 0.2652 percentage points | $50,572,778 | PASS |
| GLD -> IAUM | 0.999651 | 0.8215% | 0.5123 percentage points | $120,076,079 | PASS |

Frozen floors: correlation at least 0.95, annualized tracking error at most 6%, annualized
return gap at most 3 percentage points, median execution dollar volume at least $1 million,
and 252 aligned sessions.

## Whole-Share Fundability Cross-Check

Public reference prices on 2026-08-26 were SCHX $30.21, SPTI $28.15, and IAUM $45.79. At
approximately $145 research capital, the tested two-active-leg state can buy two SCHX shares
and one IAUM share while satisfying the frozen $20 minimum notional and 15 percentage-point
maximum leg-weight error. A three-active-leg state is still allowed to fail closed when whole
shares cannot satisfy the same error bound.

## KIS Truth Boundary

Branch workflow run `33022326070` ended with `setup_pending`: the guarded KIS workflow only
executes code reachable from `origin/main`. Therefore it did not run the six live read-only
history/quote tests and is not recorded as a KIS pass. The production KIS parity evidence,
common-session canary, and 10% no-order fundability check remain release gates after merge.

## Capital and Orders

No order was submitted and no capital was armed by these checks. First capital remains gated
on a fresh, digest-validated KIS parity document and a passing whole-share fundability result.
