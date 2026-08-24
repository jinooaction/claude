# Research: Commodity Positioning and Real-World Gate Controls

## Decision 1 - add empirical controls without loosening the threshold

Synthetic calibration proves type-I and type-II behavior under its assumptions but does not prove the gate
recognizes historical market effects. Use two independent actual return controls: Fama-French `Rm-Rf` and
AQR diversified monthly TSMOM. Freeze January 2007 onward and PSR 0.95 before the binding audit. Demeaned
copies are null controls. Controls diagnose the gate only and never enter candidate selection or promotion.

Exploratory source access before preregistration confirmed schemas and feasibility. Those measurements are
not candidate evidence and will be recomputed by the binding implementation after this document is frozen.

## Decision 2 - use CFTC disaggregated futures-only positions

CFTC's official dataset `72hh-3qpy` supplies weekly producer and managed-money positions. Fix twelve liquid
contracts spanning energy, metals, grains, softs, and livestock. Normalize net positions by open interest,
standardize each contract over 26 or 52 weeks, then take the median so contract size cannot dominate.

CFTC says disaggregated classifications are backcast for older history and can become less accurate farther
back. This is retained as source risk rather than hidden or treated as exact trader identity history.

## Decision 3 - use EIA commercial crude inventory as the inventory leg

Use keyless official workbook series `WCESTUS1`, U.S. weekly commercial crude stocks excluding the Strategic
Petroleum Reserve. Low inventory relative to its 26/52-week history is positive tightness. Current history
can be revised, so it is not described as vintage-perfect. The target month only receives a period after a
fixed five-day publication lag.

## Decision 4 - freeze a small long-only family

Four grammars x 26/52 weeks x 50/100% maximum GSG allocation produce exactly 16 trials. The grammars are
managed-money trend, producer scarcity, inventory tightness, and joint positioning-inventory confirmation.
GSG/cash keeps execution comparable with spec 156 while the signal source is economically independent.

## Decision 5 - preserve the corrected gate and data split

Keep live PSR 0.95, paper PSR 0.80, 10/25/50bp costs, positive 50bp excess economics, and diversifier blend
requirements. Use 96 development months, one embargo month, and at least 120 untouched holdout months. A
failed empirical gate audit blocks promotion but does not rewrite a strategy's measured result.

## Sources

- CFTC Disaggregated Futures Only API and historical compressed files.
- CFTC explanatory notes and Friday publication schedule.
- EIA weekly U.S. commercial crude stocks excluding SPR, `WCESTUS1`.
- Kenneth French Data Library monthly Fama-French research factors.
- AQR Time Series Momentum Factors, Monthly.
- Existing official GSG, DGS3MO, incumbent market, bond, and gold sources.
