# Feature Specification: Backtest Engine

**Feature Branch**: `008-backtest-engine` (planned)
**Created**: 2026-05-13
**Status**: Draft
**Constitution**: v2.0.0 (this feature is the principle VI "Backtest" stage made real, and the hard prerequisite for spec 007's hardened canary referenced by principle IX.B-2)
**Input**: Operator wants the backtest stage promised by constitution principle VI to actually exist. Today, "backtest" in spec 001 is an explicit OUT-OF-SCOPE placeholder. Without it, no rule change can be evidence-promoted to canary, and spec 007 (hardened canary, principle IX.B-2 gate) cannot ship — autonomous merge therefore stays disabled. v1 covers US-listed equities only (matches spec 001 scope) and changes NO Kernel file.

## Why now

- Constitution VI requires every strategy / parameter change to clear a backtest before it enters canary. Today there is no engine to run that backtest, so the gate is a paper rule.
- Spec 007's synthetic-shock replay, property-fuzz harness, and audit-integrity check all assume a working replay infrastructure. The "Promotion criteria" block at the bottom of `specs/007-canary-hardening/spec.md` names this feature as the hard prerequisite.
- Spec 005's autonomous tuner cannot promote any L2/L3 change without spec 007, which means it cannot promote ANY change without this feature.
- The operator stated goal is "autonomous execution & autonomous improvement." Without backtest evidence, every strategy edit requires operator judgment, and the human-in-the-loop blocks autonomy.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Operator validates a candidate rule change before risking real capital (Priority: P1)

The operator has an existing rule that fired three times last month. They want to tighten its entry condition (e.g., add a 50-day MA filter). Before promoting the change to live, they run a single command that replays the last twelve months of OHLCV against the modified ruleset and produces a per-rule report: total return, max drawdown, Sharpe, order count, fill count, gate-rejection count. They read the report, decide to keep or discard the change, and (if keeping) advance it to canary.

**Why this priority**: This is the core value of the entire feature. Without it, constitution VI's first stage is unimplemented and every strategy change is a guess. It is also the minimum slice that delivers value on its own — even before spec 007 exists, this user story makes the operator's day-to-day rule editing safer.

**Independent Test**: Take a known rule (`config/rules.toml` from the current operator setup), make a trivial semantic change (e.g., raise the entry threshold by one tick), run `auto-invest backtest --from 2024-05-13 --to 2025-05-13` against both versions, and verify the report shows a measurable difference in fill count or PnL between the two runs.

**Acceptance Scenarios**:

1. **Given** a ruleset file and a date range with full OHLCV coverage, **When** the operator runs the backtest command, **Then** the system produces a per-rule report containing total return %, max drawdown %, Sharpe ratio, order count, fill count, and gate-rejection count, AND writes a `BACKTEST_STARTED` and `BACKTEST_COMPLETED` audit row for the run.
2. **Given** a ruleset that names a symbol not on the current whitelist, **When** the operator starts the backtest, **Then** the system refuses to load that rule (same behavior as live worker — principle II) and records the rejection reason in the run report.
3. **Given** a backtest invocation that would re-use an existing `run_id`, **When** the engine starts, **Then** it refuses to start (audit log is append-only — principle IV; results directories are immutable).
4. **Given** a backtest invocation whose date range includes a trading day with missing OHLCV bars for any whitelisted symbol, **When** the engine starts, **Then** it halts with a clear "missing coverage" error listing the affected (symbol, date) pairs and refuses to silently shrink the window.
5. **Given** a backtest invocation while the live worker is running, **When** the engine starts, **Then** it runs without touching the live worker's SQLite database, broker connection, or audit log file; outputs go to `data/backtest/<run_id>/` and audit rows go to the same `audit_log` table with `run_id` as `correlation_id`.

---

### User Story 2 — Synthetic-shock replay produces deterministic evidence for spec 007 (Priority: P1)

The same engine, driven by a slightly different invocation, replays one or more "shock days" (2020-03-12 COVID circuit breakers, 2020-04-20 negative WTI, 2024-08-05 yen-carry unwind, plus the most recent quarterly options-expiration day). The output is a per-day, per-rule report of: orders that would have been submitted, orders rejected by which gate, and any data-quality flags. Spec 007's canary harness consumes this output as one of its five acceptance metrics.

**Why this priority**: This is what unlocks spec 007. P2 only by independence convention — without this user story, autonomous merge stays disabled forever per principle IX.B-2, and the operator's "autonomous improvement" goal is unreachable. From a value standpoint it co-equals P1, but it ships on top of the P1 engine so it cannot be P1 alone.

**Independent Test**: Run the synthetic-shock replay against a deliberately loose ruleset (e.g., no per-trade cap) over 2020-03-12; verify the report contains ≥1 `ORDER_REJECTED_BY_GATE` event from the global-exposure or volatility-halt path. Then tighten the ruleset and re-run; verify the rejection count goes down monotonically.

**Acceptance Scenarios**:

1. **Given** the synthetic-shock date set is fully covered by ingested OHLCV, **When** the operator runs `auto-invest backtest --synthetic-shock`, **Then** the engine replays each shock day and produces one report per day with the same shape as User Story 1's report.
2. **Given** the same shock-day replay invoked twice with identical inputs (ruleset hash, dataset version, replay seed), **When** the second run completes, **Then** the produced `backtest-run.json` is byte-identical to the first run's (modulo `run_id` and `start_ts`).
3. **Given** the most recent quarterly OPEX day has not yet been ingested, **When** the operator runs `--synthetic-shock`, **Then** the engine refuses to start and lists the missing date.

---

### User Story 3 — Operator reads a one-page summary and decides in minutes (Priority: P2)

After any backtest completes, the engine produces a single human-readable summary block (printed to stdout and also saved as `summary.md` next to the structured outputs) that the operator can scan in under two minutes. It surfaces only the per-rule headline metrics, the gate-rejection breakdown, and any data-quality warnings. The raw `backtest-run.json` is available for spot-check forensics but is not the primary read path.

**Why this priority**: P1 produces the structured artefact. P3 makes that artefact actionable for a non-developer operator. Without it, every backtest is a JSON-read exercise; the operator's per-day workload rises and trust erodes — but the underlying gate (principle VI) still works.

**Independent Test**: Run a backtest with five rules of which two are intentionally bad (one violates per-trade-cap, one references a delisted symbol). Verify the summary surfaces both failures with a one-line reason each.

**Acceptance Scenarios**:

1. **Given** a completed backtest run, **When** the operator reads `summary.md`, **Then** they can identify in under 120 seconds: total run return %, the worst-performing rule and its drawdown, and any rule that hit zero fills.
2. **Given** any data-quality issue surfaced during ingest or replay, **When** the summary is generated, **Then** the issue is listed with the affected (symbol, date) and the originating check name.

---

### Edge Cases

- A backtest date range straddles a symbol's delisting: ingest job must tag the symbol-date pair as "delisted-after"; engine must treat trades on or after that date as `RULE_REJECTED — delisted`, not as a gate failure.
- A symbol on the current whitelist did not exist on a historical date (recent IPO): same handling — `RULE_REJECTED — pre-listing`, not a gate failure. Distinct event from delisting so reconciliation reports stay clean.
- The judgment-point modules from spec 004 (when they ship) must never make real Anthropic API calls during backtest. The engine MUST short-circuit any LLM call site with a deterministic fixture or a hard fail — never a real network call (principle III + cost discipline).
- A backtest accidentally calls the real system clock (e.g., a developer adds `datetime.now()` somewhere in the strategy path). The engine MUST detect this and fail the run. Replay determinism is a non-negotiable safety property for spec 007.
- The historical OHLCV dataset version changes mid-run (operator runs ingest in parallel). The engine MUST snapshot the dataset version at run start and refuse to read newer rows; the run is bound to one dataset version.
- A rule fires on a partial-session day (NYSE early close on day after Thanksgiving). Replay must respect the historical session schedule, not the standard 09:30–16:00.
- The operator runs a backtest on a date set that intersects a constitutional amendment date (e.g., a date when principle II's whitelist was different). v1 always uses the CURRENT whitelist — historical whitelist drift is OUT OF SCOPE for v1; document the assumption in the report header.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-B01**: System MUST replay historical OHLCV bars against the existing `Worker.tick` code path WITHOUT modifying any file listed in `.specify/memory/kernel.toml`. The replay MUST be implemented by injecting a different time source and market-data feed into `Worker.tick`, not by editing `worker/schedule.py` (group K6).
- **FR-B02**: Replay clock MUST be injectable. During a backtest, no production code path executed by `Worker.tick` or its risk gates may read the system clock; an offending call MUST cause the run to fail with a `WALL_CLOCK_LEAK` error. (Determinism is a spec 007 prerequisite.)
- **FR-B03**: Historical OHLCV ingest MUST cover, at minimum, every symbol on the operator's current whitelist for every trading day in the requested range, PLUS every date in the synthetic-shock date set defined in FR-B09.
- **FR-B04**: System MUST emit a `BACKTEST_STARTED` audit row at run start carrying: `run_id`, ruleset SHA-256, date range, dataset version, replay seed, invoker (CLI or canary harness).
- **FR-B05**: System MUST emit a `BACKTEST_COMPLETED` audit row at run end carrying: `run_id`, end-of-run summary metrics (per-rule and aggregate), and outcome (`completed` | `failed`).
- **FR-B06**: Backtest MUST NOT issue any real broker order. The order-router MUST be wired to a deterministic in-memory broker that produces fills (or rejections) based ONLY on the replayed OHLCV and the configured fill model (see FR-B07). Defense-in-depth: a backtest run that produces an `ORDER_SUBMITTED` audit row whose adapter is anything other than the in-memory mock MUST cause the run to fail.
- **FR-B07**: Limit-order fill model in v1 MUST be: [NEEDS CLARIFICATION: optimistic (any bar that touches the limit price within the range counts as a full fill) vs. pessimistic (require the limit price to be inside the bar AND the bar's volume to exceed the order quantity)]. Default per Assumptions: pessimistic with zero slippage.
- **FR-B08**: Backtest MUST NOT make any real Anthropic API call. Any spec-004 judgment-point call site reached during replay MUST be served from [NEEDS CLARIFICATION: a per-run fixture file recorded from a prior live capture vs. a deterministic stub keyed on input hash vs. an unconditional `BACKTEST_JUDGMENT_DISALLOWED` failure]. Default per Assumptions: deterministic stub (returns the rule's documented "no-op" branch).
- **FR-B09**: Synthetic-shock date set MUST at minimum include `2020-03-12`, `2020-04-20`, `2024-08-05`, and the most recent quarterly options-expiration day relative to today's run date. Date set MUST be configurable but adding/removing a date is itself a safety-surface change (operator-only; constitution-amendment-adjacent — see spec 007's promotion criteria).
- **FR-B10**: Engine MUST refuse to start when any (symbol, date) pair in the requested range lacks OHLCV coverage. The error message MUST list missing pairs and MUST NOT silently shrink the window.
- **FR-B11**: Backtest outputs MUST be written under `data/backtest/<run_id>/` with this deterministic structure: `backtest-run.json` (run header + final metrics), `summary.md` (human-readable, see User Story 3), `metrics.csv` (per-rule row), `per-rule/<rule_id>/orders.json`, `per-rule/<rule_id>/fills.json`, `per-rule/<rule_id>/gate-rejections.json`. The directory MUST be immutable after `BACKTEST_COMPLETED` is emitted.
- **FR-B12**: Backtest CLI MUST consult the kernel manifest (`.specify/memory/kernel.toml`) at startup and MUST refuse to run if its own working tree contains any uncommitted modification to a Kernel-listed path. (Defense-in-depth: the operator should not be running an experimental backtest against a Kernel-edited working tree.) The existing `auto_invest.deploy.kernel_guard` module from spec 006 satisfies this consultation requirement.
- **FR-B13**: OHLCV ingest MUST validate at load time and emit `DATA_QUALITY_ISSUE` audit rows for: negative or zero prices, zero-volume bars during regular session hours that are not the result of a documented halt, gap detection between consecutive trading days exceeding one calendar week without a documented exchange-closure reason.
- **FR-B14**: Per-rule backtest report MUST include: total return % (gross), max drawdown %, Sharpe ratio (assuming 0% risk-free rate; documented in summary), order count, fill count, gate-rejection count grouped by gate, slippage assumption used, and total notional traded.
- **FR-B15**: Re-running a backtest with identical inputs — same ruleset SHA-256, same dataset version, same replay seed — MUST produce byte-identical `metrics.csv`, `per-rule/**/orders.json`, `per-rule/**/fills.json`, and `per-rule/**/gate-rejections.json`. The `backtest-run.json` MAY differ only in `run_id` and `start_ts`. This is the determinism contract spec 007's hardened canary depends on.
- **FR-B16**: OHLCV vendor for v1: [NEEDS CLARIFICATION: yfinance (free, redistributed Yahoo data, terms-of-service grey zone for production) vs. KIS historical endpoint (already-authenticated, but limited overseas-equity history) vs. paid IEX Cloud (clean licensing, ~$10/mo) vs. operator-provided CSV ingest only (zero vendor dependency, manual maintenance)]. Default per Assumptions: operator-provided CSV ingest in v1; vendor adapter pluggable so a later spec can add yfinance/IEX without re-doing the engine.
- **FR-B17**: Backtest results MUST be queryable from the same audit-log table the live worker uses; `correlation_id = run_id`. The live `auto-invest report` and `auto-invest status` CLIs MUST NOT count backtest rows toward live PnL or live position state — they are filtered by event type.

### Key Entities

- **BacktestRun**: unique `run_id`, ruleset SHA-256, date range, dataset version, replay seed, invoker, start_ts, end_ts, status, aggregate metrics. Lives in `audit_log` as paired `BACKTEST_STARTED` / `BACKTEST_COMPLETED` rows and in `data/backtest/<run_id>/backtest-run.json`.
- **OHLCVBar**: (symbol, session_date, open, high, low, close, volume, session_schedule_tag). Immutable once ingested. Belongs to a HistoricalDataset version.
- **HistoricalDataset**: a versioned snapshot of all OHLCV data on disk at one point in time. Versioning is a content hash over the on-disk ingest output. A backtest binds to one version; concurrent ingest does not affect a running backtest.
- **ReplayClock**: deterministic time source injected into Worker.tick. NEVER reads the system clock during a run.
- **SyntheticShockDay**: a named (date, expected-gate-trip) pair documenting what spec 007's replay is meant to surface. e.g., `(2020-03-12, exchange_halt_trigger)`.
- **RuleBacktestResult**: per-rule structured outcome — return %, drawdown %, Sharpe, order/fill/gate-reject counts, slippage assumption, notional. Written to `metrics.csv` (one row) and the per-rule subdirectory.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-B01**: A full-year backtest of the operator's current ruleset (≤10 rules, ≤20 whitelisted symbols) completes in under 5 minutes on the operator's local machine.
- **SC-B02**: Re-running any backtest with identical inputs produces byte-identical per-rule artefacts (modulo run_id and start_ts). Verified by hash comparison in a test harness.
- **SC-B03**: A backtest run never produces an audit row whose event type or payload corresponds to a real broker submission. A test harness MUST be able to assert this property holds across every backtest run.
- **SC-B04**: The synthetic-shock replay on 2020-03-12, against a deliberately loose ruleset (no per-trade cap), produces ≥1 `ORDER_REJECTED_BY_GATE` event — i.e., the gates trip when they should. (Sanity property for spec 007.)
- **SC-B05**: An operator can read the per-rule summary block for a 5-rule backtest and answer "which rule should I keep?" in under 2 minutes, measured by direct timing on the operator's first 3 backtest runs.
- **SC-B06**: Operator can audit any backtest run retroactively from `data/backtest/<run_id>/` and the audit-log rows alone — no other system state is required to reconstruct the run.

## Assumptions

- v1 covers US-listed equities only (matches spec 001 scope). FX, futures, options, crypto are all out of scope. A future spec extends the engine to additional asset classes.
- Slippage defaults to zero in v1; configurable per rule in a later iteration. Documented in every summary header so the operator does not over-trust the result.
- Backtest runs on the operator's machine (or a CI runner). No production worker process is involved; no live broker connection is opened.
- Historical OHLCV ingest is a separate one-shot job (`auto-invest ingest-history`), not part of the live worker loop. The job is itself outside the Kernel.
- Judgment-point modules from spec 004 (when they ship) MUST short-circuit during a backtest run — see FR-B08 and Q3 in clarifications.
- The current whitelist applies to ALL historical dates in v1. Historical whitelist drift is out of scope; documented in the summary header so the operator knows.
- Existing audit-log infrastructure (principle IV, K4) is reused by adding new event types; NO change to `persistence/audit.py` table schema beyond appending two new event-type literals. Migration 0001 / 0002 SQL is NOT touched (those are K4 — Kernel).
- Determinism contract (FR-B15) is non-negotiable because spec 007's hardened canary depends on it.
- "Most recent quarterly OPEX day" is resolved at engine-startup time, not hard-coded.

## Dependencies & Out of Scope

### Hard prerequisite for

- **Spec 007 (hardened canary)** — directly. Spec 007's synthetic-shock replay, audit-integrity baseline computation, and property-fuzz harness all use this engine.
- **Spec 005 (autonomous tuner)** — transitively through 007. The tuner cannot promote any L2/L3 change without the hardened canary, which cannot ship without this engine.

### Not blocking but related

- **Spec 006 (deploy automation)** — the deploy runner's pre-flight check could optionally include a quick backtest against the last N days of data to validate that the new code path produces the same fills as the previous version on identical inputs. v1 of spec 008 does not require this integration; spec 006 may add it later.

### Constitutional fit

- **NOT a Kernel change.** The engine introduces new files (under `src/auto_invest/backtest/`) and new audit event types, but modifies zero file listed in `.specify/memory/kernel.toml`. The kernel-touch guard from spec 006 verifies this automatically.
- **Principle IV satisfied.** New audit events (`BACKTEST_STARTED`, `BACKTEST_COMPLETED`) are append-only; no UPDATE/DELETE.
- **Principle VI satisfied.** This feature IS the "backtest" stage referenced by principle VI; before this feature, the stage was a paper rule.
- **Principle III defended.** FR-B08 prevents real LLM calls during a backtest, defending the "Claude only at judgment points, with bounded cost" contract from autonomous misuse.

### Out of scope (this feature)

- Multi-asset (FX / futures / options / crypto) backtests.
- Live data feed comparison ("did the backtest pick a fill price that the live feed would have?").
- Strategy parameter optimization / sweeps (spec 005 territory; backtest is an input to that).
- A backtest CI integration that runs on every PR (separate runtime concern; would be a spec 006 follow-on).
- Tax-aware return calculation. Gross returns only in v1.
- Backtest of judgment-point cost (i.e. "what would spec 004 have cost on the last 90 days of decisions?"). That is a useful future feature but it is a token-telemetry replay, not an OHLCV replay; out of scope for this spec.
- Backtest UI / web view. CLI + on-disk artefacts only in v1.
- Historical whitelist drift (using the whitelist as it was on the backtest date rather than today's whitelist). v2 candidate.

## Promotion criteria

This spec is promoted to implementation only after:

1. `/speckit-clarify` resolves the three NEEDS CLARIFICATION markers in FR-B07, FR-B08, and FR-B16 (fill model, judgment-point fixture, OHLCV vendor).
2. Operator approves the four-date synthetic-shock set in FR-B09 (or amends it).
3. Operator confirms v1 may use today's whitelist for all historical dates (Assumption #6).
