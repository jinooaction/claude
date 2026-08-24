# Research: Independent FX Carry and Gate Power

## Decision: Use four long-history developed-market currencies plus USD

Use AUD, CAD, JPY, GBP, and USD. Federal Reserve H.10 spot series begin in 1971. OECD immediate-rate
series through FRED provide at least 400 monthly observations from 1990 onward for every selected currency.

**Rationale**: This gives the full 1990-2006 development window and 2007+ untouched holdout without
splicing the euro or using future-filled rates.

**Alternatives considered**: EUR was rejected because a consistent euro spot history begins in 1999.
CHF was rejected because the selected immediate-rate series ends in 2024 and cannot pass freshness.

## Decision: Model unlevered foreign cash, not leveraged forward carry

Each foreign sleeve earns prior-month local short interest plus the USD value change of the currency. USD
earns the prior-month U.S. immediate rate. The portfolio is long-only and unlevered.

**Rationale**: It is reproducible from official public series and avoids hidden leverage, margin, and synthetic
forward assumptions. It still measures the economic source of funding-rate differences and currency moves.

**Alternatives considered**: Leveraged long-short forwards were rejected because broker availability,
margin, rollover, and executable forward history are not available in the current KIS path.

## Decision: Reduce the family from 64 to 16 candidates

Use four fixed economic grammars, signal lookback 3/12 months, and maximum foreign allocation 50/100%.
Select the top two currencies; use a 12-month risk estimate. Do not add threshold grids after results.

**Rationale**: Fewer choices reduce selection error and make the gate more likely to identify a real moderate
signal without increasing false acceptance.

**Alternatives considered**: Repeating 64 combinations was rejected as unnecessary parameter fishing.

## Decision: Four grammars

- `pure_carry`: rank positive local-minus-U.S. rates.
- `carry_momentum`: combine rate differential with same-direction spot momentum.
- `carry_value`: combine carry with a fixed 36-month exchange-rate value correction.
- `defensive_carry`: combine carry and momentum but move to USD when point-in-time FX volatility exceeds its trailing 60-month median.

**Rationale**: Carry, momentum, value, and crash defense are established, distinct economic hypotheses.

## Decision: Keep live 0.95 and add a capital-free paper tier

`FACTORY_EDGE` retains holdout PSR 0.95 and all economic gates. `PAPER_CHALLENGER` requires PSR 0.80,
positive 50bp returns, low incumbent correlation, non-declining blend Sharpe, and bounded drawdown, but it
cannot arm, allocate capital, or pass broker evidence validation.

**Rationale**: A 0.95 one-shot gate correctly limits false live positives but has low power for moderate
effects. The paper tier accumulates new forward evidence without spending that safety budget.

## Decision: Calibrate a power curve, not one planted effect

For family sizes 16 and 64, repeat null and planted annual Sharpe 0.20, 0.30, 0.40, 0.50, 0.60, and 0.80.
Report false acceptance, planted-candidate selection, live detection, and paper-tier admission.

**Rationale**: This directly answers whether repeated no-edge outcomes come from weak candidates or an
insensitive gate. The minimum reliably detectable effect becomes visible instead of assumed.

## Decision: Record execution basis risk and keep the whitelist closed

Map AUD/CAD/JPY/GBP/USD weights to FXA/FXC/FXY/FXB/UUP only as intended representatives. Do not add them
to the active whitelist.

**Rationale**: Currency trusts and a dollar ETF do not exactly reproduce foreign-cash interest and spot
returns. A research pass therefore needs a separate executable-instrument validation before live use.

## Sources

- Federal Reserve H.10 via FRED for daily spot rates; direct and inverse quote units are part of the data contract.
- OECD Main Economic Indicators via FRED for monthly immediate call-money/interbank rates; citation is required.
- Brunnermeier, Nagel, and Pedersen for carry crash and negative-skew risk.
- Berge, Jorda, and Taylor for carry, value, and momentum as combined currency predictors.
