# Research: Broad NO_EDGE Regime Cost Robustness

## Decision: Treat regime-stratify as the primary regime evidence

**Rationale**: The current sidecar already joins d-day public-data regime labels to d+1 strategy returns and explicitly marks the output as research-only. This matches the candidate's goal without fresh data collection or live signal generation.

**Alternatives considered**:

- Recompute regime labels locally: rejected because it would duplicate the public-data/regime pipeline and widen scope.
- Use forward tournament rows only: rejected because forward rows do not explain which macro regime produced weakness.

## Decision: Treat execution-quality as a cost-observability input, not a trade gate

**Rationale**: The execution-quality sidecar contains broker rejection count, parsed KIS message codes, KIS smoke state, and live gate context. That is enough to define no-live cost stress criteria while keeping real orders closed.

**Alternatives considered**:

- Read live broker fills directly: rejected because this candidate must not call broker APIs.
- Require complete fill-level cost basis before reporting: rejected because sparse live fills should be a wait/observation signal, not a blocker for no-live planning.

## Decision: Emit fixed 10/25/50bp stress rows

**Rationale**: Fixed basis-point rows are deterministic, easy to compare across future reports, and match earlier cost-adjusted experiments. They are planning thresholds only and do not alter order prices or capital.

**Alternatives considered**:

- Infer stress levels from recent fills: rejected because live fill evidence may be sparse and would make the contract unstable.
- Use a single stress level: rejected because cost sensitivity needs at least mild, medium, and severe cases.

## Decision: Mark low-observation regimes as WAIT

**Rationale**: A regime with fewer than 20 observations cannot support a strong pass/fail claim. Treating it as wait avoids overfitting while preserving the weakness for later evidence.

**Alternatives considered**:

- Drop low-observation regimes: rejected because hidden regime gaps are exactly what this contract needs to surface.
- Treat low-observation regimes as failure: rejected because missing sample size is not the same as poor performance.
