# Research: Public Data Input Quality Contract

## Decision: Build a focused read-only input-quality report

**Rationale**: The selected autonomous work packet asks for a contract, not a new data collection run. A focused report lets the next session and automation see whether existing public-data and regime evidence are good enough for downstream investment research.

**Alternatives considered**:

- Extend only `autonomous_work_execution.py`. Rejected because the input-quality contract needs its own gates, probe, and failure cases.
- Re-run `collect-public-data`. Rejected because the selected work packet is read-only and must not create fresh external side effects.

## Decision: Use `CONTRACT_READY`, `OBSERVATION_WAIT`, and `BLOCKED`

**Rationale**: Recent no-live experiment contracts already use a three-way distinction. Public-data quality needs the same split: malformed or missing core input blocks implementation, stale but parseable sidecars can be observation wait, and fully passing evidence is contract ready.

**Alternatives considered**:

- Use only PASS/FAIL. Rejected because liveness delay and small regime-stratify sample are not the same as malformed core data.
- Use autonomous-work statuses directly. Rejected because this report describes data input quality, not work packet selection.

## Decision: Treat publication completeness and cross-checks as core gates

**Rationale**: public-data `summary.json` already exposes `published`, `total_items`, item `ok`, and cross-check `status` fields. Those are the strongest current indicators that the public-data snapshot is internally coherent.

**Alternatives considered**:

- Require all probes to be `ok=true`. Rejected because the current sidecar intentionally records vendor probe failures such as unauthenticated FRED API checks while still publishing validated fallback data.
- Ignore cross-checks and count only files. Rejected because duplicated-source agreement is the main protection against stale or distorted public inputs.

## Decision: Use regime timeline rows and regime-stratify return days as coverage gates

**Rationale**: The downstream investment experiments rely on the public regime labels being joinable to strategy returns. `regime_timeline.csv` row count and `regime-stratify` `total_return_days` give a simple, deterministic coverage check without external calls.

**Alternatives considered**:

- Validate every individual CSV series here. Rejected for this slice because summary item rows already hold per-source coverage, and deep series-level validation can be a later data evidence candidate.
- Block on every regime label having 20 observations. Rejected because rare labels can be a normal observation-wait condition rather than a malformed input.

## Decision: Complete this candidate and advance to the next data evidence frontier entry

**Rationale**: This spec implements `candidate-public-data-input-quality-contract`. Once released, autonomous-work should stop selecting it and move to `candidate-regime-timeline-coverage-contract` unless a higher-priority packet exists.

**Alternatives considered**:

- Leave candidate advancement to manual interpretation. Rejected because released-work exists to prevent repeated work.
- Complete all data evidence candidates in one spec. Rejected because timeline coverage and liveness deserve separate contracts.
