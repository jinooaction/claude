# Research: Independent Options Variance Risk Premium

## Decision 1 - Use Cboe PUT as the direct return target

**Decision**: Use the official Cboe S&P 500 PutWrite Index daily history and methodology.

**Rationale**: PUT represents a cash-secured account that writes monthly at-the-money SPX
puts over Treasury-bill collateral. It tests the actual insurance-premium concept instead
of inferring option returns from equity prices.

**Sources**:

- History: `https://cdn.cboe.com/api/global/us_indices/daily_prices/PUT_History.csv`
- Methodology: `https://cdn.cboe.com/api/global/us_indices/governance/Cboe_PutWrite_Indices_Methodology.pdf`
- Factsheet: `https://cdn.cboe.com/resources/indices/factsheet/CboeGlobalIndices_PUT-Index.pdf`

**Rejected alternatives**: Reconstructing historical option chains would require paid
or incomplete data and introduce strike, quote, assignment, and survivorship assumptions.
An ETF-only history is too short for a long holdout.

**Coverage correction frozen before returns**: The current official PUT CSV has isolated
rows in 1991, 1994, 1997, 2001, and 2004, but its continuous daily history begins on
2007-01-03. The parser must ignore those isolated rows rather than manufacture returns
across multi-year gaps. Before any candidate return was calculated, the fixed split was
therefore changed from 120 development plus 180 holdout months to 84 development months,
one embargo month, and at least 120 holdout months. The candidate grammar, costs, models,
and gates were not changed.

## Decision 2 - Measure implied minus realized variance directly

**Decision**: Use official Cboe VIX closes for annualized implied variance and Kenneth
French daily market returns for annualized realized variance.

**Rationale**: Squared VIX and annualized daily realized variance are comparable economic
objects. Their difference is a direct insurance-compensation signal. Month `t` inputs are
shifted to target month `t+1`.

**Sources**:

- VIX history: `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv`
- VIX description: `https://www.cboe.com/tradable-products/vix/vix-historical-data`
- Daily market factors: `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip`

**Rejected alternatives**: VIX futures term structure begins later and would materially
shorten the untouched period. Current-only option-chain snapshots cannot backtest the
historical premium.

## Decision 3 - Keep cash and equity comparisons independent

**Decision**: Use Fama-French market plus risk-free return as the long-history equity
proxy and FRED `DGS3MO` as an independent cash-rate cross-check.

**Rationale**: PUT must beat cash economically and improve risk-adjusted results versus
broad equities. Neither comparator alone answers both questions.

**Source**: `https://fred.stlouisfed.org/series/DGS3MO`

**Limitation**: The Fama-French market is not exact SPX total return, so all output must
name benchmark basis risk.

## Decision 4 - Use 16 candidates with one genuine passive family

**Decision**: Freeze four passive allocations and twelve dynamic policies:

- passive PUT at 25/50/75/100%;
- positive variance-premium signal at 6/12 months and max 50/100%;
- variance-premium plus equity-trend and VIX-shock tail guard at 6/12 months and max 50/100%;
- expanding ridge prediction at 6/12 months and max 50/100%.

**Rationale**: The passive family tests whether the known risk premium itself is recognized.
Dynamic families test whether automation improves it. No duplicate horizon labels are
attached to an identical passive return stream.

## Decision 5 - Separate standalone premium and timing enhancement

**Decision**: A standalone pass requires robust cash excess plus better equity Sharpe,
drawdown, and 95% expected shortfall. Dynamic candidates also receive a non-blocking timing
audit against passive PUT at the same maximum allocation.

**Rationale**: An always-on compensated risk premium need not time the market. Conversely,
a timing claim must demonstrate improvement over simply holding the premium reference.
This resolves the same objective-routing error identified in spec 163 without weakening
tail controls.

## Decision 6 - Charge explicit implementation haircuts

**Decision**: Preserve PUT index returns as published, then test extra annual haircuts of
25/50/100bp and allocation-turnover costs of 10/25/50bp. Select and gate on 50bp annual
plus 25bp turnover.

**Rationale**: Cboe publishes benchmark methodology, not this system's executable fills.
The extra haircut covers tracking, fund expense, tax, spread, and operational uncertainty
without pretending to reconstruct option-chain fills.

## Decision 7 - Audit prior adoption without retroactive promotion

**Decision**: Consume released family JSON evidence and classify each frozen decision as
negative economics, statistically unconfirmed, post-hoc only, objective mismatch already
corrected, missing forward evidence, or missing executable parity.

**Rationale**: This answers whether prior strategies were lost to bad routing while
preserving their original holdout contracts. No prior candidate gains eligibility from
this descriptive audit.

## Decision 8 - Keep live parity closed

**Decision**: No output can authorize PUTW or SPX options.

**Rationale**: Exact assignment, cash collateral, margin, tax, instrument history,
whitelist, hardened-canary, and consumer-fingerprint contracts do not exist. Research
success and executable safety are separate claims.

## Decision 9 - Treat continuous public coverage as a source contract

**Decision**: Require at least 205 aligned monthly returns after the continuous PUT start,
use exactly 84 months for development, embargo one month, and keep at least 120 later
months untouched.

**Rationale**: This preserves a long out-of-sample majority while using only public values
that can be independently reproduced. The correction was made from source coverage before
candidate returns or rankings were inspected, so it is not a result-driven split change.

## First Frozen Result Audit

The first official-source replay used 232 aligned months from 2007-03 through 2026-06,
84 development months, one embargo month, and 147 untouched holdout months. It selected
the 12-month, 50% maximum tail-guarded policy before holdout inspection.

The selected policy passed every paper lane gate but failed the live lane on cash-excess
PSR, 2% annual cash excess, and 0.05 broad-equity Sharpe improvement. Its holdout cash
excess was 0.662141% annualized, PSR was 0.803758, Sharpe improvement was 0.039261,
maximum drawdown was 6.427959%, and monthly 95% expected shortfall was -2.166609%.

The full PUT reference earned 5.177143% annual cash excess with PSR 0.964744 and had
smaller drawdown and expected shortfall than broad equities. It nevertheless failed the
same adoption gate solely because its Sharpe was 0.124261 below the unusually strong
2014-2026 broad-equity comparator. The mean-zero null failed, while the preregistered
simulation produced 2.4% null acceptance and 81.6% planted-edge detection.

This is an objective-routing diagnosis, not a threshold change. A post-result diagnostic
now labels the cash premium as economically present while preserving the original
portfolio-adoption failure. The verdict is `GATE_OR_REFERENCE_SUSPECT`; no current or
post-hoc candidate is promoted. Two candidates that passed all live numeric gates only
after holdout inspection remain descriptive evidence for a separately preregistered
selection-repair study.
