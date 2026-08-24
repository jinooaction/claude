# Data Model: Independent Commodity Term Structure

## CommoditySourceBundle

- BlackRock fund and benchmark monthly growth levels, benchmark identity, source metadata, and digest.
- World Bank Total Index monthly levels, workbook update date, source metadata, and digest.
- Common complete month range and freshness status.

## CommodityTermStructurePolicy

- `family`: four preregistered grammars applied to total return minus spot and cash.
- `carry_lookback_months`: 3 or 12.
- `max_commodity_weight`: 0.5 or 1.0.
- fixed 12-month momentum/volatility and 36-month rank/regime windows.

## CommodityTermStructureCandidate

- candidate/trial ID, policy, strategy fingerprint, target-weight fingerprint.
- execution representative `GSG`; cash representative `USD`.
- source and instrument basis-risk disclosures; whitelist authorization false.

## CommodityTermStructureDecision

- development-only winner and immutable split fingerprint.
- holdout PSR, costs, correlation, blend utility, and gate details.
- verdict: `FACTORY_EDGE`, `PAPER_CHALLENGER`, or `NO_FACTORY_EDGE`.

State: `PREREGISTERED -> EVALUATED -> one verdict`. Any material policy change creates a new family.
