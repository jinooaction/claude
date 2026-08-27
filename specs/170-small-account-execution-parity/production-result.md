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
executes code reachable from `origin/main`, so that run was not recorded as a pass. PR #689
then merged as `ecc84b93abda36efc5c104cf5894be664d70f15a`; deploy run `33024089353`
completed successfully. Main KIS run `33024089368` executed all six live read-only tests and
reported `6 passed in 28.52s`, including zero open unfilled orders.

The fresh KIS smoke database passed all three pairs. It measured GLD->IAUM correlation
0.999613 and tracking error 0.8614%, IEF->SPTI correlation 0.976618 and tracking error
1.5799%, and SPY->SCHX correlation 0.996965 and tracking error 1.0015%.

## Post-Merge Truth Audit

Manual capital-ladder run `33024217264` exposed two defects that the initial release did not
catch. Its long-lived production bar database contained older first-write-wins rows and
therefore produced a failing parity document. More importantly, the consumer authenticated
that internally consistent failure document but treated authentication as a passing gate,
reporting `entry_execution_ready=true`. The separate strategy verdict remained `NO_EDGE`, so
the decision was still `WAIT_EDGE`; capital stayed zero and no order was submitted.

The follow-up fix requires the parity document itself to pass and computes each production
parity audit from a clean temporary KIS database. The long-lived first-write-wins market-data
store remains unchanged for strategy reproducibility.

## Capital and Orders

No order was submitted and no capital was armed by these checks. Run `33024217264` confirmed
that 10% research capital, $145 on current NAV $1,456.75, is fundable with one IAUM and two
SCHX shares. First capital remains blocked because the exact deployed strategy is `NO_EDGE`
on the current anchored test and has only one forward observation.
