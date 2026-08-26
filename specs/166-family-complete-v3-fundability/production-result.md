# Production Replay: Family Complete V3

**Source sidecar commit**: `0143c66f3ba0bdcf7c18ef71ebc7e2db6d80e418`  
**Evidence timestamp**: `2026-08-26T09:30:43Z`  
**Evaluated code commit**: `e1728ca5178e05478358ebae43552f94b5e7cb02`  
**Batch**: `options-variance-risk-premium-00648d091825`

## Method

The current production `strategy_factory.json` was replayed through the new consumer. The replay
changed only the fields changed by the new producer code: `gate_version=3.0` and the four audit
gate `actual`/`required` values from booleans to their exact counts. No return, candidate, decision,
parity, or criterion value was changed.

## Result

`eligible=false`; capital remains rung 0 and this evaluation creates no order.

The consumer independently confirmed all of the following:

- 16/16 current-family records are complete.
- 752/752 cumulative audit records are present and complete.
- All 752 candidate identifiers and strategy fingerprints are unique.
- The current 16 records are the exact tail of the cumulative audit.
- The producer's four cumulative counts match the raw records.
- Thresholds were not changed after results and prior candidates were not reclassified.

The exact failed checks are:

- no final `FACTORY_EDGE` or selected deploy candidate;
- public history is not point-in-time and historical samples were reused;
- benchmark execution and research/live execution are not equivalent;
- selected standardized PSR/DSR/PBO are absent;
- therefore family DSR, family PBO, and program-wide multiplicity cannot pass.

The review also found a concrete implementation defect in the released producer: it split the
development period into seven segments, while the PBO implementation requires an even number of
segments. Released PBO was therefore mechanically `null` regardless of strategy quality. The v3
producer uses eight segments and publishes both raw matrices; the consumer recomputes DSR and PBO.
This was a real impossible gate, not evidence that every strategy was bad.

At 752 unique trials, the conservative program-wide threshold requires selected PSR of at least
`0.9999335106382978723404255319`. This threshold is mechanically passable, but the current result
does not reach it because there is no promotion-eligible selected statistic at all.

## What The Data Does Show

The conclusion is not "every strategy has no economic signal":

- Full PUT exposure beat cash by 5.177143% annualized with PSR 0.964744 in the reused PUT sample.
- The nested PUT portfolio beat cash by 2.312035% with PSR 0.950439, but broad-equity Sharpe
  improvement was only 0.036908 versus the frozen 0.05 requirement.
- The independent WPUT replay was much weaker: 0.476446% annual cash excess, PSR 0.669454, and
  Sharpe improvement -0.322830 for portfolio adoption.
- Automated timing did not beat matching passive PUT exposure in either PUT or WPUT.

So an options premium appears in one historical source, but it does not survive independent-index
replay as a portfolio/timing edge and it still lacks executable options-policy parity. Relaxing one
threshold would not repair those missing contracts.

## Next Evidence

The next eligible family must use point-in-time executable history, exact assignment/collateral/
margin/tax/cost behavior, a preregistered objective, a live-expressible deploy config, and a current
small-capital preview. The first production workflow run after merge is the authoritative v3 sidecar;
this pre-release replay is retained so its before/after values can be compared exactly.
