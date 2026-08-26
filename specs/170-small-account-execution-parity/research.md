# Research: Small-Account Execution Parity

## Current Diagnosis

- Current execution ETFs `SPYM`, `IEF`, and `GLDM` are roughly 90 dollars per share while the
  research-capital per-trade ceiling is roughly 72 dollars. This is a whole-share execution mismatch,
  not evidence that the strategy itself has no historical merit.
- The current hardened-canary integrity count is produced from a union-ended window. A lagging latest
  symbol is therefore counted as missing even when no completed common session is absent.
- `globalfixed` remains a historical candidate, not a live edge: its recent anchored daily comparison
  currently has zero of three segment Sharpe wins against buy-and-hold. This feature does not change
  that verdict or its thresholds.

## Preregistered Proxy Set

| Signal | Execution | Economic basis | Official source |
|---|---|---|---|
| SPY | SCHX | broad US large-cap equities, about 750 holdings | https://www.schwabassetmanagement.com/products/schx |
| IEF | SPTI | intermediate US Treasury bonds, Bloomberg 3-10 year index | https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-portfolio-intermediate-term-treasury-etf-spti |
| GLD | IAUM | physical gold exposure based on the LBMA Gold Price | https://www.ishares.com/us/products/306979/ishares-gold-trust-micro |

These products are not assumed identical. The historical return gate exists because SCHX is broader
than the S&P 500 and SPTI has a wider maturity range than IEF.

## Frozen Acceptance Thresholds

- common adjusted-close sessions: at least 252
- daily return correlation: at least 0.95 for every pair
- annualized tracking error: at most 0.06 for every pair
- absolute annualized return gap: at most 0.03 for every pair
- execution ETF median daily dollar volume: at least USD 1,000,000
- latest signal/execution session: equal and no older than 7 calendar days
- KIS current quote: positive and resolvable to a supported order exchange
- exact current-NAV allocation: existing constitutional fundability thresholds unchanged

The thresholds were fixed before KIS branch-smoke results were observed. A failed pair is rejected;
the threshold is not adjusted to rescue it.

## Broker Quantity Boundary

The official KIS open-trading sample repository documents overseas orders with integer `ORD_QTY`.
The separate decimal wording on `OVRS_ORD_UNPR` concerns order price, not a verified fractional-share
quantity route. Therefore this feature preserves whole-share planning rather than assuming a broker
capability that the current adapter and official sample set do not expose.

Official sample source: https://github.com/koreainvestment/open-trading-api

