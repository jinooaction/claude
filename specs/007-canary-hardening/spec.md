# Feature Specification: Hardened Canary for Autonomous Production-Deploy

**Feature Branch**: `claude/start-spec-007-6GntK`
**Created**: 2026-05-06 (stub) — promoted 2026-05-14 (constitution v3.0.0)
**Status**: Active
**Constitution**: v3.0.0 (this feature implements the production-deploy gate referenced by principle IX.B-2; under v3.0.0 the canary protects real money at the live-worker boundary, not the merge boundary)
**Input**: Operator wants zero intervention for production-deploy of code that has already landed on `main`. Under constitution v3.0.0 (IX.B-2) the hardened canary is the sole acceptance signal for autonomous production-deploy. Merges land freely via the autonomous-workflow policy in CLAUDE.md; this feature defines what gates the bits actually reaching the live worker.

## Why "hardened"

Spec 001's canary is the existing baseline: 10 trading days, 5 % capital share, drawdown < 3 %, single PnL metric. That is sufficient when a human reviews promotion. Once a human is removed from the loop (constitution v3.0.0 IX.B-2 — the canary is now the production-deploy gate), a single PnL metric on a short window is too narrow — it cannot catch:

- A code change that introduces a position-sizing bug surfacing only on high-volatility days.
- An audit-log integrity regression (silent loss of a fill record).
- A judgment-point prompt change that increases LLM cost by 10× without changing PnL.
- A latency regression that causes intermittent missed triggers.

This feature replaces the single-metric canary with a multi-metric, multi-window, adversarial canary that an operator-instructed session (or eventually spec 005's autonomous tuner) uses as the sole acceptance signal for autonomous production-deploy.

## Clarifications

### Session 2026-05-14

Resolved during stub→active promotion under autonomous-workflow + IX.D supremacy. No operator pause was needed; defaults below are derivable from the spec text and from spec 008 patterns already shipped, and they are amendable via a future PR if the operator wants to revisit them.

- Q: How is the change set identified at canary entry (for diff vs. baseline and for kernel-touch detection)? → A: Two-argument git ref pair. The canary CLI takes `--candidate-rev` (default: `HEAD`) and `--baseline-rev` (default: the commit SHA of the last `CANARY_PASSED` audit row whose `payload.outcome == "passed"`; falls back to `origin/main` if no prior pass is recorded). The harness runs `git diff <baseline-rev>..<candidate-rev>` to determine touched paths and kernel-group intersection.
- Q: What is the baseline source for `latency_p95_regression_pct` and `llm_cost_regression_pct`? → A: For replay-derived runs, baseline = backtest run of `<baseline-rev>` over the same window, using spec 008's `replay.py`. The harness produces TWO `backtest-run.json` outputs (candidate + baseline) and compares. Production telemetry (spec 002/003) is NOT used in v1 because the candidate-rev has not been deployed yet.
- Q: What is the canary's invocation surface? → A: CLI module `python -m auto_invest.canary` mirroring spec 008's `python -m auto_invest.backtest`. Subcommands: `run` (full battery), `shock` (synthetic-shock only), `fuzz` (property-fuzz only). Exit codes: `0` = pass, `1` = fail, `2` = data-incomplete / refuse-to-start, `3` = internal error.
- Q: How is "the most recent quarterly OPEX day" (FR-C03 fourth date) computed? → A: Static at canary entry. The harness computes `most_recent_quarterly_opex(canary_start_ts.date())` = the third Friday of the most recent quarter-end month (Mar/Jun/Sep/Dec) on or before `canary_start_ts`. This date is recorded in `canary-run.json` so reruns reproduce.
- Q: What is the property-fuzz target scope? → A: Pure-math against the K1 module (`src/auto_invest/risk/gates.py`) only. The post-condition `per_trade ≤ per_symbol ≤ global` is asserted as a Hypothesis property over uniformly-sampled qty/exposure tuples in plausible ranges (per-trade ∈ [1, 10_000] shares; exposure caps ∈ [0.001, 1.0]). Integrated order-flow fuzz is out of scope (the synthetic-shock replay already exercises integrated flow on volatile days).

## User Scenarios & Testing

### User Story 1 — Operator-instructed session promotes a winning prompt edit without further intervention (Priority: P1)

A change set has landed on `main` (e.g., a prompt template edit that adds a stronger cache-friendly preamble for `news_screen`). The operator instructs the session to deploy the new `main` to production. The session invokes the hardened canary at 5 % capital. Over 30 trading days of historical replay (powered by spec 008's backtest engine) plus the synthetic-shock + property-fuzz adversarial battery, all multi-metric thresholds stay inside their acceptance bands. The session emits `CANARY_PASSED` and proceeds to the live deploy via spec 006's deploy automation. The operator sees the outcome in the audit log; no further input was needed.

**Independent Test**: feed a known-good change (no semantic difference, e.g. a comment-only edit) through the canary harness; verify it passes all gates and reports `accept`. Feed a known-bad change (introduces an off-by-one in `per_trade_cap_gate`) through the same harness; verify property fuzz catches it and reports `reject` with the offending rule config attached.

**Acceptance Scenarios**:

1. **Given** a change set that has landed on `main`, **When** the operator-instructed session (or future tuner) submits it to the canary, **Then** all five acceptance metrics evaluate to within their bands for ≥30 trading days AND synthetic-shock replay flags zero risk-gate violations AND property fuzz produces zero sizing-math counterexamples → the harness emits `CANARY_PASSED` and the change set becomes deploy-eligible.
2. **Given** the same change set, **When** any single acceptance metric drifts outside its band, **Then** the harness emits `CANARY_FAILED` with the offending metric, observed value, and band; the change set is NOT marked deploy-eligible; the previously deploy-eligible version remains canonical for the live worker.
3. **Given** a change set whose diff intersects `kernel.toml`-listed paths, **When** the session submits it to the canary, **Then** the canary accepts the run AND emits an additional `CANARY_KERNEL_TOUCH_DETECTED` audit row recording the kernel groups touched (K1..K6, K-meta) — under constitution v3.0.0 the Kernel is a forensic-attention list, not a barrier. The five acceptance metrics still apply; passing the canary remains the gate to deploy.

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
- **FR-C05**: Canary MUST run as **historical replay using spec 008's backtest engine** (`src/auto_invest/backtest/replay.py`) over the ≥30/≥45-trading-day window. The replay runs the new change set's code against the same historical bars/quotes the live system would have seen. Live trading continues in parallel on the previous version until the canary passes; capital share for any LIVE follow-on canary (out of scope for v1, see Out of scope) would default to 5% per spec 001.
- **FR-C06**: Acceptance MUST be all-or-nothing across the five metrics. There is no "fails 1/5, passes 4/5 → promote" path; this is intentional defense-in-depth against tuner over-eagerness.
- **FR-C07**: All canary outcomes MUST be persisted under `data/canary/<run_id>/` with a deterministic structure: `canary-run.json`, `metrics.csv`, `shock-replay/<date>/audit_log.json`, `property-fuzz/seeds.txt`, `property-fuzz/counterexamples.json`.
- **FR-C08**: Canary harness MUST accept change sets whose diff intersects `kernel.toml`-listed paths (under constitution v3.0.0 the Kernel is a forensic-attention list, not a merge or deploy barrier). When such intersection is detected the harness MUST emit `CANARY_KERNEL_TOUCH_DETECTED` with the groups touched (K1..K6, K-meta) before running the metric battery. The five acceptance metrics still determine pass/fail.
- **FR-C09**: System MUST emit `CANARY_ENTERED`, `CANARY_PASSED`, `CANARY_FAILED`, and (when applicable) `CANARY_KERNEL_TOUCH_DETECTED` audit rows; payloads carry the run_id and the metric-bands snapshot.

## Success Criteria

- **SC-C01**: Across any rolling 90-day window once 007 is in production, zero auto-merged change sets cause a risk-gate violation in live trading.
- **SC-C02**: A change set that introduces a position-sizing bug (off-by-one in a cap gate) is rejected by property fuzz with probability ≥ 0.99 within 10,000 fuzz iterations.
- **SC-C03**: A change set that introduces a 10× LLM cost regression on any decision_class is rejected within ≤ 7 trading days (well before the 30-day window completes).
- **SC-C04**: Canary harness re-running against identical seeds produces identical pass/fail outcomes (reproducibility for forensics).

## Dependencies & Out of Scope

### Hard prerequisite — SATISFIED

Spec 008's backtest engine shipped on `main` at commit `7f8fb99` (Merge PR #4, 2026-05-14). The historical-replay infrastructure is available at `src/auto_invest/backtest/replay.py`; this spec is the consumer.

### Out of scope (this feature)

- The backtest engine itself (delivered by spec 008).
- A LIVE follow-on canary at 5% capital share on the real KIS account. v1 of spec 007 is **replay-based only** — it validates against the past N trading days of historical bars. A future v2 may layer a parallel live-capital canary on top, but that is a separate spec.
- Adversarial robustness against operator-injected bad data (assume the operator is honest; principle V handles secret theft).
- Tuner-side decision logic (lives in spec 005, still a stub).
- Multi-strategy parallel canaries; v1 runs one canary at a time and queues the rest.

## Promotion criteria

This spec is promoted from stub → active per constitution v3.0.0 / autonomous-workflow policy (CLAUDE.md). The historical "Operator approval at merge" gate that v2.0.0 carried is repealed under IX.D; default acceptance bands and the synthetic-shock date set ship with this spec and the operator may amend them via a follow-on PR.

The defaults landed by this spec (subject to operator amendment via future PR):

1. Acceptance metric bands: drawdown ≤ 3.0%, risk-gate violations = 0, audit-integrity failures = 0, latency p95 regression ≤ +20%, LLM cost regression ≤ +10% (per FR-C01).
2. Window: 30 trading days L2 / 45 L3 (per FR-C02).
3. Synthetic-shock date set: 2020-03-12, 2020-04-20, 2024-08-05, plus the most recent quarterly OPEX day relative to canary start (per FR-C03).
4. Property-fuzz iterations: 10,000 (per FR-C04).
