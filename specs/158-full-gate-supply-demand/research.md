# Research: Full-Gate Audit and Commodity Supply-Demand

## Decision 1: Audit the whole decision, not PSR alone

- **Decision**: Run AQR diversified time-series momentum through the exact five live diversifier gates after a 50bp annual haircut, and run its demeaned null through the same calculations.
- **Rationale**: Spec 157 proved only that PSR 0.95 can pass. Candidate promotion also requires positive post-cost excess, low correlation, blend Sharpe improvement, and drawdown control.
- **Observed preregistration check**: On common 2007-02 through 2026-05 months, the positive control produced PSR about 0.959, annual excess about 4.46%, correlation about -0.134, blend Sharpe improvement about 0.196, and lower drawdown. The demeaned null produced PSR about 0.435, annual excess about -1.38%, and negative blend Sharpe improvement. These values establish feasibility before the new candidate holdout is run.

## Decision 2: Keep the diversifier standard

- **Decision**: Do not lower PSR 0.95, blend improvement 0.05, correlation 0.80, or the positive-return rule.
- **Rationale**: A real investable-style control passes all of them. Lowering a rule after candidate failures would increase false discovery risk without evidence that the rule is impossible.
- **Alternative considered**: Objective-specific replacement gates. Rejected for this family because the preregistered objective is portfolio diversification, not incumbent replacement.

## Decision 3: Use four official EIA petroleum balance series

- **Decision**: Use `WCESTUS1`, `WCRFPUS2`, `WGIRIUS2`, and `WRPUPUS2` with five-day publication lag.
- **Rationale**: They provide long weekly histories for stocks, supply, refinery pull, and demand proxy without a paid API key.
- **Alternative considered**: USDA crop stocks/use. Deferred because mixing separate crop release calendars and revision contracts would enlarge the first family and weaken reproducibility.

## Decision 4: Freeze a small economically distinct grammar

- **Decision**: Four signal grammars, 52/104-week normalization, and 50/100% maximum GSG weight, exactly 16 trials.
- **Rationale**: This covers meaningful supply-demand hypotheses while keeping multiplicity bounded and preserving an untouched holdout.

## Known Limitations

- EIA current history may contain revisions; publication lag prevents release lookahead but not vintage-revision lookahead.
- Product supplied is a demand proxy, not final consumption.
- Petroleum fundamentals and broad GSG index weights have basis mismatch.
