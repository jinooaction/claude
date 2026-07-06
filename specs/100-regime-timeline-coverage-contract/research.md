# Research: Regime Timeline Coverage Contract

## Decision: Build a focused read-only regime timeline coverage report

**Rationale**: The selected autonomous work packet asks for a contract over `regime_timeline.csv` and `regime-stratify`, not a new data collection or strategy experiment. A focused report keeps the evidence reusable by the next session and avoids mixing public-data publication quality with timeline-specific join quality.

**Alternatives considered**:

- Extend only `public_data_input_quality.py`. Rejected because spec 099 intentionally kept regime coverage broad; this candidate needs every stratified JSON section, label floors, and forward join checks.
- Re-run `collect-public-data` or `regime-stratify`. Rejected because the candidate is read-only and must not create fresh external side effects.

## Decision: Parse every `regime-stratify` stratified JSON block

**Rationale**: The current sidecar contains `GLOBAL-TREND` and `GLOBAL-TREND-WIDE` sections. A last-block-only parser can accidentally hide a malformed or sparse primary strategy section. The contract must preserve section-level evidence and fail if any section breaks the forward join or count consistency contract.

**Alternatives considered**:

- Parse only the live-designated `GLOBAL-TREND` section. Rejected because the sidecar already publishes multiple strategy sections and downstream interpretation compares them.
- Parse only the last JSON block. Rejected because it can mask section drift.

## Decision: Treat sparse per-label observations as `OBSERVATION_WAIT`

**Rationale**: `regime_stratified.MIN_OBS_FOR_RATIOS` is 20. The latest real sidecar has total 751 joined return days, but `RISK_OFF` has 7 days. This is not malformed input; it is a truthful rare-regime observation gap. The report should say "wait for more evidence" instead of "ready" or "blocked".

**Alternatives considered**:

- Mark any label below 20 as `BLOCKED`. Rejected because rare regimes can be structurally sparse without data corruption.
- Ignore per-label floors and require only total_return_days. Rejected because it produces false confidence exactly where regime analysis is weakest.

## Decision: Require explicit forward join rule and count consistency

**Rationale**: The regime performance claim is only meaningful if the sidecar preserves d-day label to d+1 return joining and the by-label buckets sum to total return days. These two checks catch future-leak regressions and malformed stratified outputs without re-running the strategy.

**Alternatives considered**:

- Trust prose outside the JSON. Rejected because the report should be machine-verifiable.
- Recompute stratification from raw NAV and timeline in this contract. Rejected because that would duplicate a heavier research workflow and expand scope beyond sidecar validation.

## Decision: Complete this candidate and advance to data evidence liveness

**Rationale**: This spec implements `candidate-regime-timeline-coverage-contract`. Once released, autonomous-work should stop selecting it and move to `candidate-data-evidence-liveness-contract` unless a higher-priority packet exists.

**Alternatives considered**:

- Leave candidate advancement to manual interpretation. Rejected because released-work exists to prevent repeated work.
- Complete liveness in the same spec. Rejected because liveness deserves a separate contract over freshness/recovery behavior.
