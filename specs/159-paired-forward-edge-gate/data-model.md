# Data Model: Paired Forward Edge Gate

## PairedActiveReturnEvidence

- `significance_method`: `paired_active_return_psr_v1`
- `strategy_returns`: aligned period simple returns, internal only
- `benchmark_returns`: aligned period simple returns, internal only
- `active_returns`: strategy minus benchmark by period, internal only
- `active_information_ratio_annual`: annualized mean active return divided by active-return standard deviation
- `psr_vs_benchmark`: probability active information ratio is above zero
- `dsr`: optional multiple-testing-adjusted probability on active returns
- `min_track_record_obs`: observations required for requested confidence on active returns

Validation: all three return arrays have equal nonzero length; active variance must be positive; missing or mismatched data cannot produce confirmed evidence.

## EdgeVerdictV12

Existing strategy, benchmark, return, drawdown, Calmar, threshold, and verdict fields remain. New fields are `significance_method` and `active_information_ratio_annual`; `schema_version` becomes `1.2`.

State transitions:

- aligned and significant plus all economic gates -> `EDGE_CONFIRMED`
- aligned and measured but any gate fails -> `NO_EDGE`
- misaligned, too short, or zero variance -> `INSUFFICIENT_DATA`

## ForwardGateCalibrationReport

- scenario: seeds, observations, repetitions, benchmark distribution, active volatility, planted active Sharpe
- thresholds: paper 0.80 and live 0.95
- null: legacy and paired acceptance rates
- planted: legacy and paired detection rates
- checks: paper nominal rate, live false acceptance, paired power improvement
- verdict: `CALIBRATED` only when every check passes
- safety: no broker, no order, no capital change

## Downstream evidence

Tournament rows and profit evidence preserve `significance_method`. Exploration readiness and direct forward-confirmed ladder admission require the paired method; legacy rows remain visible but are ineligible.
