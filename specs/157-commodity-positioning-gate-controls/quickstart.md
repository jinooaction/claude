# Quickstart: Commodity Positioning and Real-World Gate Controls

1. Download official Fama-French, AQR TSMOM, CFTC disaggregated futures-only, EIA `WCESTUS1`, GSG, and existing incumbent inputs.
2. Run synthetic gate calibration for the exact code commit.
3. Run `scripts/commodity_positioning_factory_probe.py` with all source files, 672-record prior payload, and calibration JSON.
4. Require the empirical control audit to pass independently of the strategy verdict.
5. Confirm exactly 16 current trials, 688 unique audit records, 96 development months, one embargo month, and at least 120 holdout months.
6. Confirm no broker import, GSG whitelist authority false, deploy config null unless research-only evidence passes, and capital/orders unchanged.
7. Run focused tests, full pytest, ruff, YAML, diff, strict harness, handoff facts, and PR quality gate.
8. After merge, verify deployment, production sidecar replay, 688-record audit catalog, and KIS read-only no-order smoke.
