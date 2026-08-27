# Production Verification: Parallel Regime Edge Challenger

## Final State

- Strategy verdict: `NO_RESEARCH_EDGE`.
- Capital ladder verdict: `WAIT_EDGE`, rung `0 -> 0`.
- Account NAV: `$1447.51`; target capital: none.
- Execution readiness: true.
- Capital changed: false.
- Orders submitted: 0.

## Strategy Evidence

The preregistered winner was `regime-corr24-thr0p2-weak6-cash`. On the 234-month
holdout it beat the incumbent after symmetric 50bp annual and 10bp one-way turnover costs:

| Metric | Challenger | Incumbent | Gate |
| --- | ---: | ---: | --- |
| CAGR | 8.695121% | 8.548482% | PASS |
| Sharpe | 1.841788 | 1.802237 | PASS |
| Max drawdown | 5.659028% | 5.659028% | PASS |
| Latest 60-month Sharpe | 2.188585 | 2.027655 | PASS |

Family PBO was `0.171429`, active-return PSR was `0.998215`, and annual one-way turnover
was `1.683761`. The only failed preregistered gate was recent time dispersion: the challenger
beat the incumbent in 1 of 3 recent segments instead of the required 2.

The diagnosis is stronger than a gate label. All nonzero monthly return differences occurred in
only three months: 2022-09, 2022-12, and 2023-03. The largest month supplied `64.1856%` of total
absolute effect. This is promising historical behavior, but not repeated independent regime evidence.

## Gate Calibration

- 16-candidate family: null admission `1.0%`, planted annual Sharpe 0.60 detection `84.0%`.
- 64-candidate family: null admission `0.4%`, planted annual Sharpe 0.60 detection `80.4%`.
- Negative control rejected; planted positive control detected; one-month delay and higher costs
  moved results in the expected direction.

The present failure is therefore not evidence that the statistical gate is impossible to pass. The
system found a candidate that passed the statistical and economic core, then rejected it because its
incremental return was too concentrated in time.

## Production Repair Chain

1. Run `33088105605` exposed helper/package deploy skew: the helper used a new
   `--token-cache` option while the server package remained one version old during the market-hours
   deploy delay. It failed closed with an empty parity result and no capital or orders.
2. PR #693 made the temporary parity DB share the existing `data/kis_token.json` under both CLI
   versions. Run `33090550150` restored all three parity pairs and execution readiness.
3. The same run exposed an unnecessary `live-canary-profit 0` call. PR #694 restricted that read-only
   probe to positive numeric capital.
4. Run `33092282493` exposed a missing skipped-probe stderr file and a leaked function-local RETURN
   trap. It stopped before capital decision and changed no capital or orders.
5. PR #695 made skipped evidence deterministic, preserved explicit temporary DB cleanup, and cleared
   the trap before leaving the function.

## Final No-Order Run

Run `33093842870` at merge `32807f4` completed through decision and sidecar publication.

- Exact log scan found none of: `capital must be positive`, `unbound variable`, `No such option`,
  `403 Forbidden`, `Process completed with exit code`, or `ERROR:`.
- GLD -> IAUM, IEF -> SPTI, and SPY -> SCHX each passed all 252-session parity checks.
- `execution_proxy_parity_passed=true`, `entry_execution_ready=true`, `fundable=true`.
- The 144-dollar dry-run could represent IAUM 1 share and SCHX 2 shares.
- Those are planned dry-run orders only. The ladder chose `WAIT_EDGE`, target capital was null,
  the sentinel did not change, no PR opened, and no order was submitted.

## Release Evidence

- Strategy merge: `598be96` (#692).
- Deploy-skew fix merge: `0365b3b` (#693).
- Zero-capital probe fix merge: `0f1cc9f` (#694).
- Observer lifecycle fix merge: `32807f4` (#695).
- Guarded deploy: `33093767500`; SSH helpers refreshed, server package deploy deferred during the
  NYSE session until `2026-08-27T20:00:00Z` without bypass.
- Final autoarm: `33093842870`, success.
- Verification: 3132 passed, 6 skipped; Ruff; shell and JSON checks; strict harness 14/14;
  HANDOFF facts OK; PR quality gates passed.

## Conclusion

There are historically useful strategies in the repository, especially the deployed global trend
incumbent, and the new challenger was not broadly bad. There is still no strategy with enough current,
time-dispersed, independently confirmed evidence to receive live capital. The correct next research
family must create return differences across multiple periods by construction; lowering the gate after
seeing these three months would approve concentration, not discover edge.
