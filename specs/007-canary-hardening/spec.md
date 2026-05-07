# Feature Specification: Hardened Canary for Autonomous Merge

**Feature Branch**: `007-canary-hardening` (planned)
**Created**: 2026-05-06
**Status**: Draft
**Constitution**: v2.0.0 (this feature implements the gate referenced by principle IX.B-2)
**Input**: Operator wants zero merge intervention. Constitution v2.0.0 principle IX permits autonomous merge for non-Kernel change sets ONLY after a hardened canary passes. Spec 005's tuner cannot merge L2/L3 changes until this feature defines and implements that canary.

## Why "hardened"

Spec 001's canary is the existing baseline: 10 trading days, 5 % capital share, drawdown < 3 %, single PnL metric. That is sufficient when a human reviews promotion. Once a human is removed from the loop (constitution IX.B), a single PnL metric on a short window is too narrow — it cannot catch:

- A code change that introduces a position-sizing bug surfacing only on high-volatility days.
- An audit-log integrity regression (silent loss of a fill record).
- A judgment-point prompt change that increases LLM cost by 10× without changing PnL.
- A latency regression that causes intermittent missed triggers.

This feature replaces the single-metric canary with a multi-metric, multi-window, adversarial canary that the autonomous tuner uses as the sole acceptance signal for non-Kernel auto-merges.

## User Scenarios & Testing

### User Story 1 — Autonomous tuner promotes a winning prompt edit without operator action (Priority: P1)

The tuner detects that decision_class `news_screen` has cache_hit_rate stuck at Tier B (0.71). It generates a prompt template edit that adds a stronger cache-friendly preamble. The change set enters the hardened canary at 5 % capital. Over 30 trading days, all multi-metric thresholds remain inside their acceptance bands; synthetic-shock replay produces no new orders that would have failed risk gates; property fuzz on rule configs surfaces zero sizing-math regressions. The tuner auto-merges the change set; the operator finds out from the daily auto-tuner-report.

**Independent Test**: feed a known-good change (no semantic difference, e.g. a comment-only edit) through the canary harness; verify it passes all gates and reports `accept`. Feed a known-bad change (introduces an off-by-one in `per_trade_cap_gate`) through the same harness; verify property fuzz catches it and reports `reject` with the offending rule config attached.

**Acceptance Scenarios**:

1. **Given** a non-Kernel change set, **When** the tuner submits it to the canary, **Then** all five acceptance metrics evaluate to within their bands for ≥30 trading days AND synthetic-shock replay flags zero risk-gate violations AND property fuzz produces zero sizing-math counterexamples → tuner emits `AUTO_TUNED_L2_CANARY_PASSED` and proceeds to deploy.
2. **Given** the same change set, **When** any single acceptance metric drifts outside its band, **Then** tuner emits `AUTO_TUNED_L2_CANARY_FAILED` with the offending metric, observed value, and band; the change set is rolled back; the previous version remains canonical.
3. **Given** a change set that touches the Kernel, **When** the tuner attempts to enter the canary, **Then** the canary harness refuses (defense-in-depth — Kernel changes never reach the canary in the first place).

---

### User Story 2 — A regression that survives PnL alone is caught by audit-integrity check (Priority: P1)

A code change makes the order-router silently drop one in 1000 fills (a real-world failure mode). PnL during canary is unaffected (the dropped fills are tiny). But `data_quality_issue` audit rows accumulate. The audit-integrity acceptance metric trips and the canary fails.

**Independent Test**: inject a synthetic test that drops 1/1000 fills; verify the canary's audit-integrity check rejects.

---

### User Story 3 — Operator can audit any auto-merge decision retroactively (Priority: P2)

For every canary outcome (pass or fail), the harness writes a structured `canary-run.json` artifact under `data/canary/<run_id>/` containing: change set diff stats, all observed metric time series, synthetic-shock per-day outcomes, property-fuzz random seeds and counterexamples (if any), final pass/fail decision. The operator can spot-check any auto-merge by reading this artifact.

**Acceptance Scenarios**: full reproducibility — re-running the harness against the same inputs and seeds produces a byte-identical artifact (modulo the start_ts).

---

### Edge Cases

- A 30 trading-day window straddles a quarterly options expiration with unusual volatility: the synthetic-shock replay covers this case explicitly so the live canary doesn't have to depend on it.
- The new code adds a column to a non-Kernel SQLite table (e.g., adds a `latency_p99_ms` column to a future `judgment_metrics` table): the canary's audit-integrity check considers schema additions OK as long as no UPDATE/DELETE reaches an append-only table.
- The change set is a pure dependency upgrade (e.g., `httpx` 0.28 → 0.29): canary still runs the full multi-metric battery so transient network behaviour changes are caught.
- The historical-replay data set is incomplete for a recent date: the canary refuses to start until the operator runs the data-ingest job, rather than silently shrinking the window.

## Requirements

- **FR-C01**: System MUST evaluate FIVE acceptance metrics over the canary window:
  1. `pnl_drawdown_pct` ≤ pre-declared threshold (default 3.0%, configurable per change class).
  2. `risk_gate_violation_count` = 0 (any violation rolls the change back).
  3. `audit_integrity_failures` = 0 (zero `DATA_QUALITY_ISSUE` rows above the baseline running mean of the previous 30 days; baseline computed once per canary entry).
  4. `latency_p95_regression_pct` ≤ +20% relative to previous version's running p95 (configurable per change class).
  5. `llm_cost_regression_pct` ≤ +10% relative to previous version's `usd_per_decision_mean` for any decision_class touched by the change.
- **FR-C02**: Canary window MUST be ≥ 30 trading days for L2 changes and ≥ 45 trading days for L3 changes (per spec 005 v2.0.0 §Tiered authority).
- **FR-C03**: Synthetic-shock replay MUST run the new code against at least these historical days: 2020-03-12 (COVID circuit breakers), 2020-04-20 (negative oil futures — sanity check that limit-order-only enforcement holds), 2024-08-05 (yen-carry unwind), plus the last quarterly OPEX day. Any new order that would fail any risk gate, OR any audit-integrity failure during replay, MUST reject the change set.
- **FR-C04**: Property-based fuzz MUST exercise risk-gate math against ≥ 10,000 randomly generated rule configurations (per-trade qty, per-symbol exposure, global exposure all randomized within plausible ranges). Any counterexample where the mathematical post-condition (`per_trade ≤ per_symbol ≤ global`) is violated rejects the change.
- **FR-C05**: Canary MUST run on a SHADOW deployment that mirrors the live worker but uses 5% canary capital share (already enforced by the existing canary in spec 001). Live trading continues in parallel on the previous version until the canary passes.
- **FR-C06**: Acceptance MUST be all-or-nothing across the five metrics. There is no "fails 1/5, passes 4/5 → promote" path; this is intentional defense-in-depth against tuner over-eagerness.
- **FR-C07**: All canary outcomes MUST be persisted under `data/canary/<run_id>/` with a deterministic structure: `canary-run.json`, `metrics.csv`, `shock-replay/<date>/audit_log.json`, `property-fuzz/seeds.txt`, `property-fuzz/counterexamples.json`.
- **FR-C08**: Canary harness MUST refuse to start a canary on a change set whose diff intersects `kernel.toml` (defense-in-depth).
- **FR-C09**: System MUST emit `CANARY_ENTERED`, `CANARY_PASSED`, `CANARY_FAILED` audit rows; payloads carry the run_id and the metric-bands snapshot.

## Success Criteria

- **SC-C01**: Across any rolling 90-day window once 007 is in production, zero auto-merged change sets cause a risk-gate violation in live trading.
- **SC-C02**: A change set that introduces a position-sizing bug (off-by-one in a cap gate) is rejected by property fuzz with probability ≥ 0.99 within 10,000 fuzz iterations.
- **SC-C03**: A change set that introduces a 10× LLM cost regression on any decision_class is rejected within ≤ 7 trading days (well before the 30-day window completes).
- **SC-C04**: Canary harness re-running against identical seeds produces identical pass/fail outcomes (reproducibility for forensics).

## Dependencies & Out of Scope

### Hard prerequisite

A backtest engine (option D from main `HANDOFF.md`) is required to produce the historical-replay infrastructure. Spec 007 cannot ship until the backtest engine exists. Until then, autonomous merge in production stays disabled per constitution IX.B-2 → the existing 10-day spec-001 canary (single-metric PnL) is the upper bound on what evolves autonomously, and that bound applies only to L1 changes which already skip the canary entirely.

### Out of scope (this feature)

- The backtest engine itself (separate feature; option D in HANDOFF.md).
- Adversarial robustness against operator-injected bad data (assume the operator is honest; principle V handles secret theft).
- Tuner-side decision logic (lives in spec 005).
- Multi-strategy parallel canaries; v1 runs one canary at a time and queues the rest.

## Promotion criteria

This stub is promoted to a full spec only after:

1. The backtest engine (option D) ships and is verified against at least one historical date with a known-good outcome.
2. Operator has approved the five acceptance metrics and their default bands.
3. Operator has approved the synthetic-shock date set; new dates added later are themselves L4 (kernel-meta-adjacent) since they affect the safety surface.
