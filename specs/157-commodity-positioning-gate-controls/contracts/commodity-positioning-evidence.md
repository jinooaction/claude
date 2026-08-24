# Contract: Commodity Positioning Factory Evidence

The machine payload must bind:

- gate version and synthetic calibration commit;
- Fama-French and AQR control source hashes, fixed windows, actual and demeaned PSRs;
- fixed CFTC dataset, twelve contract codes, EIA series, publication lags, freshness, and source hashes;
- sixteen candidate IDs and fingerprints, development selection, embargo, and untouched holdout;
- 10/25/50bp costs, target weights, economic comparison, and every failed gate;
- 672 prior plus 16 current unique audit records;
- code commit and source, control, split, strategy, and target-weight fingerprints;
- explicit `live_whitelist_authorized=false`, null deploy config, and no-order safety statement.

The probe exits nonzero on malformed controls or strategy inputs. A statistical pass can only nominate a
research canary and cannot authorize GSG, allocate capital, arm live mode, or call a broker.
