# Data Model: Forward Paper Ledger Integrity

## LedgerMeasurement

- `mode`: paper or live.
- `capital_basis_usd`: declared measurement capital when present.
- `ledger_cash_usd`: capital plus cumulative sell cash minus cumulative buy cash.
- `total_market_value_usd`: marked long holdings.
- `total_nav_usd`: cash plus market value.
- `measurement_valid`: true unless a capital-based paper ledger has cash below -$0.01.
- `invalid_reason`: `negative_paper_cash` when rejected.

Validation transition:

- non-paper or no capital basis -> existing measurement path.
- paper and cash >= -$0.01 -> valid, snapshot may append.
- paper and cash < -$0.01 -> invalid, command exits and snapshot does not append.

## ForwardMeasurementEpoch

- `epoch_id`: `v2-clean-unlevered`.
- `track_key`: trend, notrend, rmbeta, multiasset, global, globalfixed, or wide.
- `database_path`: `data/forward_v2_<track>.db`.
- `legacy_database_path`: prior `data/forward_<track>.db`, retained and ineligible.
- `portfolio_path`: unchanged strategy TOML.
- `halt_path`: unchanged track-specific halt flag.

## TrackBinding

Each track has exactly one active database path. Forward run, verdict, candidate history, ladder, anchored verdict, signal IC, and ML analysis must resolve to that same epoch where applicable. No fallback edge exists from clean to legacy.

## Evidence Eligibility

- Historical holdout: unchanged and separately eligible as historical evidence.
- Legacy forward PSR/observations: ineligible after the epoch switch.
- Clean forward evidence: insufficient until its own required observations exist.
- Money path: rung 0 and preview only when clean evidence is absent or insufficient.
