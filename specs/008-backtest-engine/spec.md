# Feature Specification: Backtest Engine

**Feature Branch**: `008-backtest-engine` (planned)
**Created**: 2026-05-07
**Status**: Draft
**Constitution**: v2.0.0 — implements the historical-replay infrastructure required by principle IX.B-2 (via spec 007). Strictly outside the Kernel.
**Input**: User description: "Backtest engine for auto-invest. Hard prerequisite for spec 007 (hardened canary, constitution IX.B-2). Replays historical OHLCV against the existing Worker.tick / risk-gate stack to produce a deterministic returns/drawdown/Sharpe report. NOT a Kernel change. Vendor for OHLCV TBD during /speckit-clarify."

## Clarifications

### Session 2026-05-07

- Q: OHLCV vendor (FR-B06) → A: yfinance and KIS historical, both supported. Engine reads via a vendor-agnostic OHLCV adapter interface; concrete adapters for the two vendors are part of v1 scope. Adapter selection per backtest run is an input field. Polygon and CSV remain follow-ups, not v1.
- Q: Fill model (FR-B07) → A: Hybrid. For limit orders (the v1 default order type per constitution domain constraint), fill iff the trigger bar's [low, high] range straddles the limit price; if so, fill at the limit price exactly (range-aware-at-limit). For market orders (which require a per-symbol opt-in per constitution domain constraint), fill at the next bar's open ± a configurable slippage in basis points (default 5 bps). The fill-model choice per order is keyed off the existing live order_type, so backtest and live take the same branch.
- Q: New audit-log migration kernel-touch policy (FR-B17) → A: the new migration file (`0003_backtest_events.sql` or whatever number is next at land time) is added to `kernel.toml` group K4 in the same change set as 008's first landing. Adding a file to `kernel.toml` is itself a K-meta touch, so spec 008's first landing is treated as a one-time human-merge event (consistent with constitution IX.B-1 and IX.C). All subsequent non-Kernel work on the engine — adapters, reporting, vendor extensions — is autonomous-merge-eligible once spec 007 ships.
- Q: Promotion verdict thresholds (FR-B21) → A: v1 defaults are confirmed and frozen for the engine's advisory verdict — `total_return_pct ≥ 0`, `max_drawdown_pct ≤ 10`, `sharpe ≥ 0.5`. The verdict is advisory only in v1; spec 007 takes over as the binding gate for autonomous merge. Operators MAY override per-run via input fields but the defaults are the project-level baseline.
- Q: Synthetic-shock dataset OPEX freeze (FR-B18) → A: the most-recent quarterly OPEX at dataset-freeze time (2026-05-07) is **2026-03-20** (third Friday of March 2026). The frozen `synthetic_shock_v1` membership is therefore: 2020-03-12, 2020-04-20, 2024-08-05, 2026-03-20. Adding/removing a date is L4 (per spec 005) and requires operator action; subsequent quarterly OPEX days do not auto-roll into the named dataset.

## Why this feature exists

Constitution v2.0.0 principle IX.B-2 conditions every autonomous merge on a hardened canary (spec 007), and the hardened canary itself depends on three replay-driven gates:

1. **Synthetic-shock replay** — running the candidate code against pre-selected historical stress days (e.g. 2020-03-12 COVID circuit breakers, 2020-04-20 negative-oil, 2024-08-05 yen-carry, the most recent quarterly OPEX) and verifying zero risk-gate violations.
2. **Reproducible acceptance metrics** — drawdown, Sharpe, and per-rule returns computed over a fixed window so that bands defined in spec 007 (FR-C01) are computable at all.
3. **Determinism for forensics** — the canary harness's `canary-run.json` must be byte-identical when re-run on the same inputs (spec 007 SC-C04). That guarantee bottoms out at the backtest engine.

Until this feature ships, autonomous merge stays disabled in production (constitution IX.B-2) and the existing 10-day spec-001 canary remains the upper bound on autonomy.

Beyond spec 007, the same engine also closes spec 001's deliberately deferred Option D from `HANDOFF.md`: operators have no way today to evaluate a new rule before canary capital is committed. Constitution principle VI explicitly requires `Backtest → Canary → Full Live`; this feature is the first arrow.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Spec 007 canary harness replays a candidate change against synthetic-shock days (Priority: P1)

The operator (or, post-007, the autonomous tuner) submits a non-Kernel change set. Before live capital is exposed, the canary harness invokes the backtest engine in `synthetic-shock` mode against the four pre-declared stress days. The engine drives the candidate code through the live order-routing pipeline using historical OHLCV, observes every order the new code would have submitted, and reports per-day outcomes: orders proposed, risk-gate rejections, would-be fills, would-be PnL, and any audit-integrity anomalies.

**Why this priority**: this is the gate that constitution IX.B-2 conditions autonomous merge on. The feature has zero usefulness for its consumer (spec 007) without it, and spec 007 has zero usefulness without 007 + 008 together. P1 is non-negotiable.

**Independent Test**: feed a known-good rule (e.g. a comment-only edit to a previously-promoted rule) through synthetic-shock mode and verify zero risk-gate violations and a stable PnL curve. Then feed a deliberately-broken rule (e.g. one whose per-trade cap was raised 100×) and verify the engine surfaces the violation without ever submitting an order.

**Acceptance Scenarios**:

1. **Given** a candidate change set and the four synthetic-shock dates, **When** the harness calls the backtest engine in synthetic-shock mode, **Then** the engine drives the candidate code against historical OHLCV for each date and emits a structured per-date report including `orders_proposed`, `gate_rejections`, `simulated_fills`, `pnl_usd`, `audit_integrity_failures`.
2. **Given** the same inputs run twice, **When** seeds and OHLCV snapshots are identical, **Then** the two reports are byte-identical (modulo a `start_ts_utc` stamp).
3. **Given** an OHLCV dataset that is missing a required date, **When** the engine starts, **Then** it refuses to run and emits a clear data-completeness error rather than silently dropping the date.

---

### User Story 2 — Operator backtests a new rule before promoting it to canary (Priority: P1)

The operator drafts a new rule in TOML, points the backtest engine at a configurable historical window (e.g. the last 12 months of daily bars across the rule's symbol whitelist), and reads a returns/drawdown/Sharpe report. The report tells them whether to promote the rule to canary or scrap it.

**Why this priority**: closes the constitution-VI hole that spec 001 explicitly deferred. Without this, every new rule goes straight to canary with real capital — exactly the failure mode principle VI was written to prevent.

**Independent Test**: load a deterministic synthetic OHLCV fixture (e.g. a sine-wave price series over 252 trading days), run a single SMA-cross rule, verify the engine reports the closed-form expected number of fills and the closed-form PnL within numerical tolerance.

**Acceptance Scenarios**:

1. **Given** a rule TOML and a historical window with complete OHLCV, **When** the operator invokes the backtest engine, **Then** the engine produces a report containing total return, max drawdown, annualized Sharpe ratio, per-rule fill count, per-rule PnL, and a per-symbol exposure timeline.
2. **Given** a rule whose configuration would fail risk gates (e.g. a per-trade cap exceeding the global cap), **When** the engine starts, **Then** it surfaces the gate failure with the same error semantics as live trading would, before any historical replay begins.
3. **Given** a backtest report and the same rule + window inputs, **When** the engine is rerun, **Then** the produced report is byte-identical (same numerical values, same ordering, same hash).

---

### User Story 3 — Audit log records every backtest run for retroactive operator review (Priority: P2)

Every backtest run emits append-only audit rows (`BACKTEST_STARTED` / `BACKTEST_COMPLETED` / `BACKTEST_FAILED`) into the existing audit log, with payloads that identify the run id, candidate-code git sha, OHLCV dataset hash, rule set hash, and final headline metrics. The operator can months later answer "what did backtest run X return?" without re-running the engine.

**Why this priority**: required by constitution principle IV (every judgment-equivalent decision is auditable). Without this, autonomous-tuner promotion decisions referencing past backtests have no forensic surface.

**Independent Test**: run two distinct backtests, then query the audit log directly; verify exactly two `BACKTEST_STARTED` rows and two corresponding `BACKTEST_COMPLETED` rows, each with monotonic sequence ids, with payloads referencing the right run ids.

**Acceptance Scenarios**:

1. **Given** a backtest invocation, **When** it starts, **Then** a `BACKTEST_STARTED` row is appended with `run_id`, `code_sha`, `dataset_hash`, `rules_hash`, `window_start`, `window_end`.
2. **Given** the run completes successfully, **When** it returns, **Then** a `BACKTEST_COMPLETED` row is appended with the headline metrics (`total_return_pct`, `max_drawdown_pct`, `sharpe`).
3. **Given** the run aborts mid-flight (data gap, cancelled, exception), **When** the failure is surfaced, **Then** a `BACKTEST_FAILED` row is appended with `phase` and `reason`; the engine never exits silently.

---

### User Story 4 — Operator inspects a per-day artifact for any past backtest (Priority: P2)

The engine writes a structured directory under `data/backtests/<run_id>/` containing the input snapshot (rule TOML, OHLCV manifest with content hashes), the headline report, the per-day series, and the per-fill ledger. The directory is the single source of truth that downstream consumers (spec 007 canary harness, operator daily report) read.

**Why this priority**: the canary harness's reproducibility guarantee (spec 007 SC-C04) requires a stable on-disk artifact format. Auditing decisions weeks later requires the artifact to outlive the engine process.

**Independent Test**: run a backtest, locate `data/backtests/<run_id>/`, verify the manifest, headline, per-day, and per-fill files exist and parse against a published schema.

**Acceptance Scenarios**:

1. **Given** any completed backtest run, **When** the operator opens `data/backtests/<run_id>/`, **Then** they find: `manifest.json` (inputs + hashes), `report.json` (headline metrics), `daily.csv` (per-day P&L, exposure, drawdown), `fills.csv` (per-fill ledger), `audit-events.json` (subset of the global audit_log scoped to this run).
2. **Given** two backtests on identical inputs, **When** their `data/backtests/<run_id>/` directories are diffed, **Then** every file is byte-identical except for `run_id`, `start_ts_utc`, and `end_ts_utc`.

---

### Edge Cases

- **Missing OHLCV for a required date** — engine refuses to start (User Story 1 #3); never silently shrinks the window.
- **OHLCV with a known split or dividend on the window** — engine consumes adjusted OHLCV and records the adjustment provenance in the manifest. Unadjusted OHLCV produces a clearly-labelled error rather than wrong PnL.
- **Rule references a symbol that exited the whitelist mid-window** — replay against that symbol stops on the date the symbol left the whitelist; report makes the truncation explicit.
- **Rule references a symbol delisted during the window** — same handling as above; the engine never invents synthetic post-delisting prices.
- **Live worker is running while a backtest is invoked** — both share the SQLite audit log via WAL; a backtest run never writes order/fill rows, only `BACKTEST_*` rows. The audit-append-only invariant (principle IV) is preserved.
- **Backtest invoked with an OHLCV dataset whose content hash differs from the canary harness's snapshot** — engine surfaces the hash mismatch and refuses to run; spec 007's reproducibility guarantee depends on this.
- **A historical bar's high/low straddles a rule's limit price** — fill model (FR-B07) is the single source of truth for what counts as a fill; the spec 007 canary harness depends on this being deterministic, not heuristic.
- **OHLCV vendor returns a `NaN` or a zero volume for a required bar** — engine treats this as a data-quality failure (`DATA_QUALITY_ISSUE` audit row) rather than substituting prior close.
- **Rule timeframe exceeds the bar resolution provided by OHLCV (e.g. rule wants 1m, dataset has 1d)** — engine refuses to run with a clear "insufficient resolution" error rather than producing degenerate-but-plausible output.

## Requirements *(mandatory)*

### Functional Requirements

#### Pipeline reuse (constitution-critical)

- **FR-B01**: Backtest engine MUST drive the candidate code through the **same** rule-evaluation, gate, and order-routing logic that live trading uses. Any forked "backtest-only" copy of risk-gate or order-routing logic is forbidden — it would defeat the purpose of using backtests as a safety gate (constitution IX.B-2).
- **FR-B02**: Backtest engine MUST NOT modify any file listed in `.specify/memory/kernel.toml`. The replay must inject a historical clock and a historical quote source through existing extension seams (e.g. dependency-injectable broker / clock), not by editing K6 (`worker/schedule.py`) or any other Kernel file. The deploy guard (spec 006 FR-D13) will enforce this; the spec author MUST design accordingly.
- **FR-B03**: Backtest engine MUST execute every risk-gate check (per-trade cap, per-symbol cap, global cap, whitelist, halt flag, stage-uniqueness) exactly as live trading does. A rule that would be rejected in live trading MUST be rejected in backtest with the same rejection reason.

#### Inputs

- **FR-B04**: System MUST accept as input: a candidate rule TOML (or live config), a historical-OHLCV dataset reference, a window `[start_date, end_date]`, optional symbol filter, and a deterministic random seed.
- **FR-B05**: System MUST validate the OHLCV dataset before replay: every required (date, symbol) pair present, no `NaN`/zero-volume bars on required pairs, content hash recorded in the run manifest.
- **FR-B06**: System MUST support two OHLCV vendors in v1 — `yfinance` (free, daily-adjusted, US equities) and `KIS historical` (already-integrated KIS overseas-equity historical endpoint). Selection per backtest run is an explicit input. Both vendors are accessed through a vendor-agnostic OHLCV adapter interface so future vendors (Polygon, CSV ingest, others) can be added without changing the replay engine. The KIS adapter MUST NOT cause live-broker side effects during replay (FR-B09 still binds); reading historical bars is permitted, placing orders is not.
- **FR-B06a**: Vendor adapter contract MUST normalise output into a single canonical OHLCV row shape (date, symbol, open, high, low, close, volume, adjusted_flag, vendor_id), with content-hash computed over the canonical form so that two vendors returning equivalent bars for a given (date, symbol) produce the same `dataset_hash` (FR-B05).

#### Replay semantics

- **FR-B07**: Fill model is **hybrid**, branched on the live `order_type` so that backtest and live take the same code path:
  - **Limit orders** (v1 default per constitution domain constraint): fill IFF the trigger bar's `[low, high]` range straddles the rule's declared limit price; on a fill, fill quantity goes through at the limit price exactly. If the range does not straddle, the order is treated as no-fill on that bar (the engine MUST NOT carry the open limit forward across bars in v1; carrying-forward is a follow-up).
  - **Market orders** (v1 per-symbol opt-in per constitution domain constraint): fill at the next bar's `open` price adjusted by a configurable slippage in basis points (default `5` bps; configurable per backtest run).
  - The fill-model choice is **never** configurable in a way that would let backtest take a more lenient path than live — the live worker submits limit by default and market only on opt-in, and the backtest engine MUST mirror exactly that choice from the rule TOML.
- **FR-B07a**: For both fill types, the engine MUST record on every `SimulatedFill`: `fill_model_branch` (`limit_range_aware` | `market_next_open`), the slippage in bps applied (0 for limit), and the bar identifier the fill is attributed to. This is what makes spec 007's reproducibility (SC-C04) checkable.
- **FR-B08**: System MUST advance simulated time deterministically across the window using only timestamps derived from the OHLCV bars. The live-trading market-hours guard (`worker/schedule.py`, K6) MUST NOT be modified; the backtest invokes the existing scheduling logic with a synthetic `now()` callable instead of system time.
- **FR-B09**: System MUST NOT contact the live broker, live market-data feed, or any external network endpoint during replay. A backtest that requires network egress to evaluate a rule MUST fail loudly. (This is also a Kernel-adjacent guarantee: it is the property that lets us trust 007's synthetic-shock replay.)
- **FR-B10**: System MUST simulate cash and positions starting from a configured opening cash balance (default: $100,000) and never permit negative cash, partial fills below the configured minimum, or short positions (constitution: short selling is out of scope, v1.0.0).

#### Reporting & determinism

- **FR-B11**: System MUST produce a report containing at minimum: total return %, max drawdown %, annualized Sharpe ratio (rf = 0 by default; configurable), per-rule fill count, per-rule realized PnL, per-symbol exposure time series (daily resolution), and a daily P&L curve.
- **FR-B12**: Two backtest runs against identical inputs (same code sha, same OHLCV content hash, same rule TOML, same seed) MUST produce byte-identical `report.json`, `daily.csv`, and `fills.csv` (modulo a `run_id`, `start_ts_utc`, and `end_ts_utc` field). Reproducibility is the contract spec 007 SC-C04 ultimately depends on.
- **FR-B13**: System MUST persist every backtest under `data/backtests/<run_id>/` with `manifest.json`, `report.json`, `daily.csv`, `fills.csv`, `audit-events.json`. Schemas for these files MUST be published as a contract under `specs/008-backtest-engine/contracts/`.

#### Audit integration (constitution IV)

- **FR-B14**: System MUST emit `BACKTEST_STARTED` to the existing append-only `audit_log` before any replay work, with payload: `run_id`, `code_sha`, `dataset_hash`, `rules_hash`, `window_start`, `window_end`, `seed`.
- **FR-B15**: System MUST emit `BACKTEST_COMPLETED` on success, with payload: `run_id`, `total_return_pct`, `max_drawdown_pct`, `sharpe`, `fills_count`, `gate_rejections_count`.
- **FR-B16**: System MUST emit `BACKTEST_FAILED` on any abort, with payload: `run_id`, `phase` (one of `validate_inputs`, `replay`, `report`), `reason`. The engine MUST NEVER exit without emitting one of `BACKTEST_COMPLETED` or `BACKTEST_FAILED` for any started run.
- **FR-B17**: New audit-event types (`BACKTEST_STARTED`, `BACKTEST_COMPLETED`, `BACKTEST_FAILED`) MUST be added under the append-only invariants of the existing `audit_log` table. Their schema additions MUST go through a new SQLite migration (next sequential number at land time, e.g. `0003_backtest_events.sql`). Because the new migration extends the audit-log surface that is the safety invariant of K4, the migration file MUST be added to `kernel.toml` group K4 in the **same change set** as the migration itself. Editing `kernel.toml` is by construction a K-meta touch, so spec 008's first landing is treated as a one-time human-merge event (consistent with constitution IX.B-1 and IX.C — "adding a file to the Kernel is always a forward-compatible safety improvement"). After this initial landing, all non-Kernel work on the engine (adapters, reporting code, vendor extensions, fill-model defaults) is autonomous-merge-eligible once spec 007 ships.

#### Synthetic-shock dataset (consumer: spec 007)

- **FR-B18**: System MUST support a named-dataset mode in which the operator (or the canary harness) names a curated subset of historical days rather than a contiguous window. The initial named dataset is `synthetic_shock_v1`, frozen on 2026-05-07, containing exactly four dates: **2020-03-12** (COVID circuit breakers), **2020-04-20** (negative oil futures), **2024-08-05** (yen-carry unwind), **2026-03-20** (most recent quarterly OPEX at freeze time, third Friday of March 2026). Subsequent quarterly OPEX days do NOT auto-roll into `synthetic_shock_v1`; mutating membership is L4 per spec 005 and requires operator action.
- **FR-B19**: The named-dataset manifest MUST be persisted as `data/ohlcv/datasets/<name>.json` with each date's OHLCV content hash, so spec 007's harness can detect drift.
- **FR-B20**: Adding or removing a day from `synthetic_shock_v1` is operator-only (L4 in spec 005 terms — affects the safety surface). The engine MUST refuse to silently mutate a named dataset. **Runtime enforcement**: `data/ohlcv/datasets/synthetic_shock_v1.json` is added to `kernel.toml` as a new group `[K7_named_datasets]` in the same change set as 008's first landing, so spec 006's deploy guard blocks any change set that mutates this file from being autonomously merged — even before spec 005's L4 classification logic ships. Adding K7 is itself a K-meta touch handled within the documented one-time human-merge event for 008's first landing (constitution IX.C — "adding a file to the Kernel is always a forward-compatible safety improvement").

#### Promotion gate output (consumer: constitution principle VI canary stage)

- **FR-B21**: System MUST produce a machine-readable promotion verdict (`promote_eligible: bool`, `reason: str`) computed from acceptance thresholds. The v1 baseline thresholds are **frozen** at: `total_return_pct ≥ 0`, `max_drawdown_pct ≤ 10`, `sharpe ≥ 0.5`. Operators MAY override per backtest-run via input fields, but if no override is provided, these baseline values apply. The verdict is **advisory only in v1**; it does not gate any deploy or promotion by itself. Spec 007's hardened canary, once shipped, becomes the binding gate (constitution IX.B-2); the backtest verdict is one input among many at that point.

### Key Entities

- **BacktestRun**: a single replay invocation. Identified by `run_id` (UUID v4 via the deterministic seed). Owns: `code_sha`, `rules_hash`, `dataset_hash`, `window_start`, `window_end`, `seed`, `start_ts_utc`, `end_ts_utc`, `verdict`.
- **OhlcvDataset**: a named or window-specified collection of (date, symbol, open, high, low, close, volume) rows with a vendor identifier and a content hash. Immutable once frozen for a `BacktestRun`.
- **NamedDataset**: a curated `OhlcvDataset` like `synthetic_shock_v1`. Frozen; modifications are L4.
- **SimulatedFill**: per-trigger row recording symbol, qty, price, timestamp, rule_id, gate-outcome, simulated cash impact. Append-only within a `BacktestRun`.
- **DailyState**: per-day snapshot of cash, per-symbol exposure, cumulative P&L, drawdown.
- **BacktestReport**: aggregation of `DailyState` and `SimulatedFill` series into the headline metrics consumed by FR-B11.
- **BacktestAuditEvent**: rows in the existing `audit_log` table with `event_type ∈ {BACKTEST_STARTED, BACKTEST_COMPLETED, BACKTEST_FAILED}`. Uses the existing append-only invariant.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-B01**: An operator with a valid rule TOML and a 1-year daily-OHLCV dataset can produce a complete backtest report (returns, drawdown, Sharpe, per-rule breakdown) in a single command, without writing any glue code.
- **SC-B02**: 100% of risk-gate code paths exercised in live trading are exercised in backtest mode against an equivalent input (verified by code-coverage diff between live and backtest harnesses on the gate package).
- **SC-B03**: Two backtest runs against identical inputs produce reports whose stable-fields hash to the same value across at least 100 consecutive runs (reproducibility — the floor that spec 007 SC-C04 sits on).
- **SC-B04**: A deliberately-broken rule (per-trade cap > global cap; symbol off the whitelist; price-source missing data) is rejected by the backtest engine with the same rejection reason a live worker would emit, in 100% of injected-fault test cases.
- **SC-B05**: Synthetic-shock replay over the four pre-declared dates completes in under 30 seconds wall-clock on the operator's reference machine (single-laptop SQLite + local OHLCV CSV), so spec 007's canary harness incurs negligible per-run overhead.
- **SC-B06**: The audit log can answer "show me every backtest run in the last 30 days, its verdict, and its dataset hash" using a single SQL query against the existing `audit_log` table — no parallel backtest log permitted.
- **SC-B07**: Zero `BACKTEST_*` audit-row insertions ever fail the append-only invariant in property-fuzz testing (≥ 10,000 randomized run/abort sequences).

## Assumptions

- **Operator runs the engine on the same machine as the live worker.** The backtest engine targets the operator's local dev machine and the same SQLite file, with WAL ensuring backtests don't block live writes. No distributed-execution path in v1.
- **Daily bars are the v1 default.** The first usable engine consumes daily-OHLCV. Intraday (1m / 5m) bar replay is a follow-up; spec 001's existing `timeframe = "1d"` rules cover the v1 surface and the four synthetic-shock dates exist at daily resolution. The OHLCV-vendor clarification (FR-B06) may extend this.
- **Adjusted OHLCV.** The engine assumes splits/dividends are applied in the ingested data; raw-OHLCV ingestion produces a clear error rather than wrong PnL. Adjustment provenance is recorded in `manifest.json`.
- **Fees and taxes are out of scope for v1 reporting.** The engine surfaces gross PnL only. A configurable per-fill fee model is a follow-up; documented now so that operator interpretation of `total_return_pct` is unambiguous.
- **No Kernel files are modified.** The replay achieves clock injection via existing dependency-injectable seams in `worker/loop.py` and the broker module. `worker/schedule.py` (K6), `risk/gates.py` (K1), `config/whitelist.py` (K2), and `persistence/audit.py` (K4) are read-only. Spec 006's kernel-touch guard will catch violations on the deploy path; the spec author catches them at design time.
- **Engine is invoked synchronously by the canary harness (spec 007).** No async-orchestration framework in v1; a single-process Python invocation that the harness `await`s on. Parallel/multi-strategy canaries are out of scope (spec 007 already scopes them out).
- **Time discipline.** Backtests are I/O-bound on local SQLite + local OHLCV; there is no "deploy during market hours" concern (constitution VIII.A) because no live trading code is being changed by *running* a backtest. Modifying engine code is, of course, subject to VIII.A like everything else.

## Dependencies & Out of Scope

### Hard prerequisites (already in main)

- Spec 001 risk-gate stack (`src/auto_invest/risk/gates.py`).
- Spec 001 worker loop (`src/auto_invest/worker/loop.py`) — `Worker.tick`, the rule evaluator, the order-routing call site.
- Spec 001 audit log (`src/auto_invest/persistence/audit.py`).
- Constitution v2.0.0 (Kernel manifest at `.specify/memory/kernel.toml`).

### Hard consumer

- **Spec 007 — Hardened Canary**. Spec 007 cannot ship without this engine (FR-C03, FR-C04 of spec 007 both depend on historical replay).

### Out of scope for spec 008

- The hardened-canary multi-metric battery itself (lives in spec 007).
- The autonomous-tuner promotion logic (lives in spec 005).
- Intraday (sub-daily) bar replay; deferred to a follow-up after the v1 daily engine is verified end-to-end.
- Multi-strategy / parallel backtest orchestration; v1 is single-process, single-strategy.
- Walk-forward optimization, parameter sweeps, hyperparameter search; the engine produces a single report per invocation. A driver script can sweep externally if needed.
- Benchmark comparison (vs SPY, vs equal-weight); the report emits absolute metrics only.
- Fee/commission/tax model; deferred (see Assumptions).
- Live broker fee schedule; out of scope.
- Order-book / level-2 simulation; OHLCV-only fidelity is the v1 contract.

## Constitution touchpoints (informational; full Constitution Check belongs in `/speckit-plan`)

| Principle | How this spec relates |
|-----------|-----------------------|
| I (Position Sizing) | Backtest exercises the *same* sizing-cap gates as live (FR-B01, FR-B03). No new caps; no Kernel touch on K1. |
| II (Whitelist) | Backtest exercises the *same* whitelist gate (FR-B03). No Kernel touch on K2. |
| III (LLM at judgment points only) | This feature invokes no LLM. Out of scope. |
| IV (Append-only audit) | Adds three new event types via a new migration (FR-B14..B17). All append-only. The migration filename addition needs the Q3 clarification. |
| V (Secret isolation) | Backtest must NOT call live broker (FR-B09). No KIS credential is loaded by the engine in any code path. |
| VI (Backtest → Canary → Full Live) | This is the "Backtest" arrow. The engine's promotion verdict (FR-B21) is the input to canary. |
| VII (External API robustness) | OHLCV ingest contacts an external vendor; the ingest path inherits the existing rate-limit / retry / circuit-breaker primitives. |
| VIII.A (No market-hours deploys) | Engine code, like everything else, is deployed off-hours. *Running* a backtest does not deploy anything. |
| VIII.B (Deploy automation) | Engine deploys are non-Kernel and become autonomous-merge-eligible once spec 007 ships. Until 007, engine code lands via human merge like any other change. |
| **IX (Self-Modification Boundary)** | **NOT a Kernel change.** No file under any group in `kernel.toml` appears in this feature's diff. The clock-injection seam is non-Kernel. |

## Promotion criteria

This spec is ready for `/speckit-plan` when:

1. The two open clarifications (vendor for OHLCV, fill model) are resolved via `/speckit-clarify`.
2. The migration-naming clarification (FR-B17) is resolved — likely by adding the new migration file to `kernel.toml` group K4 in the same change set, executed as a one-time human merge.
3. Operator has confirmed the v1 promotion-verdict thresholds in FR-B21 (default acceptance bands).
