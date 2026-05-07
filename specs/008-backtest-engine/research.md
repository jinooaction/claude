# Phase 0 Research: Backtest Engine

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Date**: 2026-05-07

The five clarifications from `/speckit-clarify` (Q1–Q5) closed the largest unknowns. This document captures the remaining technology / pattern decisions that the planner faced *after* those clarifications, plus the three or four design questions that surfaced during plan-writing. Each entry follows the speckit pattern: Decision → Rationale → Alternatives considered.

## R-1. Worker.tick injection seam — kwargs vs subclass vs dependency object

**Decision**: add two **optional kwargs** to `Worker.__init__`: `quote_provider: Callable[[str, datetime], Awaitable[Quote]] | None = None` and `clock: Callable[[], datetime] | None = None`. Default `None` preserves byte-identical live behaviour. Backtest constructs the worker with both populated.

**Rationale**:
- Smallest possible diff to a non-Kernel file (`worker/loop.py`). No subclass hierarchy to reason about.
- The DI seam shows up at exactly one call site (`_evaluate_and_route`'s `get_quote(...)`); a guard `if self.quote_provider is None: ...` is the entire live-vs-replay branch.
- Tests already drive `Worker.tick(now=...)`, so the precedent for clock injection is established.
- A dependency object (`Worker(deps=BacktestDeps(...))`) would touch every constructor caller in tests and `__main__` to add an empty `LiveDeps()`. Net negative ergonomics for zero design benefit.

**Alternatives considered**:
- **Subclass `BacktestWorker(Worker)`** overriding `_evaluate_and_route`: rejected — duplicates the rule-evaluation code path, which is exactly what FR-B01 forbids ("any forked backtest-only copy of risk-gate or order-routing logic is forbidden").
- **Module-level monkeypatch** of `broker.overseas.get_quote` from inside the engine: rejected — not thread-safe, would corrupt a parallel live worker if one ran in the same process, and leaves a foot-gun for future devs.
- **Inject through a global `Settings` singleton**: rejected — globals are one of the harder things to reason about determinism around; the engine would also need to teardown the global on every test, which is exactly the dynamic that property-based fuzz tends to expose as flaky.

## R-2. yfinance vs `yfinance` (the package) — pinning and robustness

**Decision**: depend on `yfinance ~= 0.2` (current minor at time of writing), wrapped behind `auto_invest.backtest.ohlcv.yfinance_adapter`. The adapter exposes the canonical OHLCV row shape from R-3; nothing outside the adapter imports `yfinance`. Network calls go through the adapter's `tenacity`-retried, rate-limited transport which lives in the adapter file.

**Rationale**:
- yfinance is a thin wrapper over Yahoo's public endpoints; it has periodically broken when Yahoo changed their pages. Containing the dependency to a single file means a yfinance breakage is one adapter swap, not a feature-wide refactor.
- `tenacity` and the rate-limit pattern are already in spec 001; reusing them on a new transport keeps the operational vocabulary small.
- `~= 0.2` (compatible-release) admits patch updates without breaking pinning discipline.

**Alternatives considered**:
- **`yfinance == 0.2.X` exact pin**: rejected — too aggressive; defeats security patches.
- **Strip yfinance entirely; ship our own scraper**: rejected — that adds a maintenance surface we explicitly do not want.
- **Choose Polygon instead of yfinance**: rejected — operator's clarification chose A+B (yfinance + KIS historical); Polygon stays a follow-up.

## R-3. Canonical OHLCV row shape (FR-B06a)

**Decision**: a frozen `pydantic.BaseModel` named `OhlcvBar` with fields `(date: date, symbol: str, open: Decimal, high: Decimal, low: Decimal, close: Decimal, volume: int, adjusted: bool, vendor_id: str)`. Sort-stable by `(symbol, date)`. Each adapter is responsible for emitting bars in this shape. Content hash (FR-B05) is computed by the engine over the canonical-form JSON of all bars consumed by a run, so two vendors returning numerically equal bars produce the same hash.

**Rationale**:
- Decimal (not float) on prices because Sharpe / drawdown reproducibility is bit-sensitive; floating-point summation order is the leading cause of cross-platform drift in backtest reports.
- `adjusted: bool` is non-optional because the engine's correctness depends on whether splits/dividends were applied, and the `manifest.json` records this explicitly (User Story 4 acceptance).
- `vendor_id` lets the manifest record which adapter produced each bar even when two vendors agree (audit trail for FR-B19 hash drift detection).

**Alternatives considered**:
- **NumPy structured arrays** for performance: rejected for v1 — the spec scale (≤ 50 symbols × 5 years daily ≈ 63k rows) is comfortably within pydantic's range, and reproducibility is more valuable than µs-grade speed.
- **Use yfinance's native dataclass shape**: rejected — couples the engine to a specific vendor.

## R-4. Fill model (FR-B07) — "range-aware-at-limit" precise semantics

**Decision**: for limit orders, on the trigger bar `B = (open, high, low, close)` and a rule's limit price `L`:

- For a **buy** with limit `L`: fill iff `low ≤ L`. Fill price = `min(L, open)` — i.e. if the bar opens below the limit (gap-down), the buy fills at the better-than-limit open; otherwise at the limit `L`.
- For a **sell** with limit `L`: fill iff `L ≤ high`. Fill price = `max(L, open)` — symmetric.

Quantity is the rule's declared quantity, computed once per trigger; partial fills are not modelled in v1 (FR-B10 forbids). If the bar does not straddle, the order is treated as no-fill; the rule's "armed" state for the next bar is the live state machine, unmodified.

For market orders (per-symbol opt-in only), fill at the *next* bar's `open ± slippage_bps × open / 10_000`; default `slippage_bps = 5`.

**Rationale**:
- The "open if better than limit, else limit" rule mirrors the way real exchanges fill limit orders that arrive before the market opens at a price more advantageous than the limit. It is more honest than always-fill-at-limit, and remains deterministic.
- Symmetrising buy and sell prevents a class of accidental backtest bias where one side gets the favourable open and the other doesn't.
- 5 bps slippage default is operator-tunable; the value matches the conservative-adapter-side rate spec 001 used in informal sizing studies.

**Alternatives considered**:
- **Idealized (option A from /speckit-clarify)** — fill at trigger bar's close at `L` exactly: rejected per Q2 answer.
- **Conservative (option B)** — fill at next bar's open ± slippage for both order types: rejected because it overstates limit-order slippage, which is what limit orders exist to bound.
- **Fill at limit even if bar doesn't straddle, with probability proportional to volume**: rejected — non-deterministic in practice; defeats SC-B03.

## R-5. Determinism floor (FR-B12) — what counts as "input"

**Decision**: a backtest run's deterministic-input set is exactly:

1. `code_sha` (git HEAD of the working tree at run time; the engine refuses to start with a dirty tree unless the operator passes `--allow-dirty`, in which case `code_sha = "<sha>+dirty"`).
2. `dataset_hash` — content hash over the canonical OHLCV JSON for every (date, symbol) pair the run consumed.
3. `rules_hash` — content hash over the rule TOML, normalised by rendering to canonical TOML before hashing.
4. `seed` — explicit operator-provided integer (default `0`).
5. `caps_hash` — content hash over `config/caps.py` constants in effect (catches K1 drift).
6. `whitelist_hash` — content hash over `config/whitelist.py` (catches K2 drift).

The `manifest.json` records all six. `report.json`, `daily.csv`, `fills.csv` are byte-identical across reruns when these six are identical (FR-B12). Non-input-derived fields (`run_id`, `start_ts_utc`, `end_ts_utc`) are excluded from the FR-B12 byte-identity contract.

**Rationale**:
- Including `caps_hash` and `whitelist_hash` makes silent K1/K2 drift visible — if someone edits `config/caps.py` between two runs, the hashes differ and the backtests diverge audibly.
- `seed` is included even though daily-bar replay has no random source today; we include it now so introducing one later (e.g. partial-fill probability v2) is non-breaking.
- A "dirty tree" `+dirty` suffix loses the determinism contract on purpose — operators running ad-hoc explorations get a usable engine, but the canary harness will reject `+dirty` runs (spec 007's harness will assert the suffix is absent).

**Alternatives considered**:
- **Hash entire repo tree**: rejected — too coarse, breaks even when an unrelated test file moves.
- **Hash only `auto_invest.backtest`**: rejected — misses K1/K2 drift, which is the exact silent-bug class the canary exists to catch.

## R-6. SQLite WAL concurrency with the live worker

**Decision**: backtest runs always open the SQLite connection in WAL mode (already the project default per spec 001), use `BEGIN IMMEDIATE` for the `BACKTEST_*` audit append, and otherwise hold no long transactions. The engine never UPDATEs or DELETEs `audit_log`; only INSERT-only appends through `persistence/audit.append`.

**Rationale**:
- The live worker is the only writer to `orders` / `fills`; the backtest engine writes only `BACKTEST_*` events. Two writers on the same WAL file are safe as long as transactions are short and INSERT-only (which both are).
- `BEGIN IMMEDIATE` lets the engine fail fast if the live worker happens to be holding a long transaction, surfacing the issue rather than blocking.

**Alternatives considered**:
- **Separate SQLite file for backtest**: rejected — would need a parallel audit_log, violating SC-B06 ("answer 'show me every backtest run in the last 30 days' using a single SQL query").
- **`BEGIN EXCLUSIVE`**: rejected — would block live writes, an unacceptable side-effect of running a backtest.

## R-7. Sharpe ratio formula and risk-free rate

**Decision**: annualised Sharpe = `mean(daily_returns) / stdev(daily_returns) × sqrt(252)` with `risk_free_rate = 0` by default and `risk_free_rate` configurable per run as an annualised decimal. `daily_returns` is the daily P&L divided by the previous day's portfolio equity. Equity at t=0 is the configured opening cash (FR-B10 default $100,000). Days where equity is zero (bankruptcy) terminate the metric stream and Sharpe is reported as `null` with a `bankruptcy_at: <date>` note in the report.

**Rationale**:
- Annualisation factor 252 is the US-equity convention.
- rf=0 default is explicitly chosen for v1; once spec 007 starts using Sharpe in its FR-C01 metric battery, that's the moment to revisit. A non-zero rf would be operator-set.
- Reporting `null` rather than `inf` on bankruptcy is the only honest choice — `inf` would propagate into the verdict and yield a meaningless `promote_eligible = true` for a strategy that bankrupted the account.

**Alternatives considered**:
- **Sharpe per-rule rather than portfolio-level**: rejected for v1 headline; it's available as a per-rule slice in `daily.csv` but the headline is portfolio-level (matches user-story 2 expectation).
- **Sortino instead of Sharpe**: rejected for v1 — spec 007 uses Sharpe as one of its five FR-C01 metrics, and adding a metric inconsistent with the consumer's vocabulary is gratuitous.

## R-8. Synthetic-shock day boundaries — "what does '2020-04-20' replay actually consist of?"

**Decision**: a synthetic-shock day for a given date `D` consists of the OHLCV bar with `bar.date == D` for every symbol on the rule's whitelist *plus* the prior `N` bars needed for indicator priming, where `N = max(rule.warmup_bars for rule in rules)` (default 50, configurable). The replay drives `Worker.tick` once for the shock day itself with `now = bar(D).timestamp_close`, after the indicator state machine has been primed by the prior bars (run silently — no rule firings recorded).

**Rationale**:
- Indicators (SMA, RSI, etc.) need history; running a single bar without warmup gives the rule an empty indicator state and is meaningless.
- The "tick once on the shock day" pattern matches spec 007's intent: the synthetic-shock test is "given everything we knew on 2020-03-11 close, what would the strategy do on 2020-03-12?" — not a full multi-day window.
- 50-bar warmup default covers the longest indicator window we expect (a 50-day SMA); operator can lengthen via TOML.

**Alternatives considered**:
- **Replay the entire month containing the shock day**: rejected — defeats the "synthetic-shock" semantics (single-day stress test) and bloats the canary harness's per-run cost.
- **No warmup, just the shock day**: rejected — most rules would have null indicators and produce nonsense outcomes, masking real bugs.

## R-9. Engine entry point — library function vs CLI vs both

**Decision**: ship both. The library entry is `auto_invest.backtest.run_backtest(config: BacktestConfig) -> BacktestResult`, a pure-Python coroutine. The CLI `auto-invest backtest` is a thin click wrapper that loads a `BacktestConfig` from CLI flags + a TOML file and calls `run_backtest`. Spec 007's harness imports `run_backtest` directly; the operator uses the CLI.

**Rationale**:
- The canary harness wants in-process invocation for determinism (avoid subprocess ordering / env nondeterminism).
- The operator wants a CLI for ad-hoc exploration.
- Two entry points sharing one config object means one set of validators, one set of error messages.

**Alternatives considered**:
- **CLI only**: rejected — forces the canary harness to subprocess, fragile.
- **Library only**: rejected — operators don't (and shouldn't) write Python to evaluate a rule.

## R-10. Property-fuzz strategy for FR-B12 / SC-B03

**Decision**: use `hypothesis` with a `strategies` module that generates `(rules_toml, ohlcv_dataset, seed)` triples, runs the engine twice with the same triple, and asserts the four byte-comparison files (`report.json`, `daily.csv`, `fills.csv`, `manifest.json` minus `run_id`/`*_ts_utc`) are identical. Minimum 100 examples in CI; ≥ 10 000 examples in the nightly smoke job (matching spec 007's FR-C04 cardinality vocabulary).

**Rationale**:
- 100 in CI is small enough to keep the test suite under 30 s and large enough to surface most reproducibility regressions on the first push.
- Nightly 10 000 catches the long-tail floating-point or dict-ordering regressions that 100-example runs miss; this is also where spec 007's FR-C04 ≥ 10 000 fuzz iterations enter the canary harness as a separate concern.

**Alternatives considered**:
- **Single golden-file regression test**: rejected — catches one regression class, misses the long tail.
- **Symbolic execution**: rejected for v1 — overkill; the input space is tame enough that random sampling reaches good coverage cheaply.

## R-11. Migration `0003_backtest_events.sql` — schema additions

**Decision**: the migration adds three new event-type values to whatever event-type discipline the audit_log uses today (no schema change to columns; the audit_log is already a `(seq_id, ts_utc, event_type, payload_json)` shape per spec 001). It also adds an index on `event_type` if one doesn't exist yet, scoped to the new event types via a partial index, to make SC-B06 ("single SQL query for last 30 days of backtests") fast. The migration is added to `kernel.toml` K4 in the same change set.

**Rationale**:
- No column additions means no audit-log invariant change; the append-only contract is mechanically preserved.
- Partial index is cheap (event_type cardinality is low) and turns SC-B06 from a table scan to a seek.

**Alternatives considered**:
- **Materialised-view of backtests**: rejected — adds a moving part for what a partial index handles.
- **Add a `backtest_id` column to audit_log**: rejected — would require an ALTER TABLE, which is a Kernel-level concern far larger than the K4 manifest update; the existing JSON payload already carries `run_id`.

## R-12. Order-router substitution — `BacktestBroker`

**Decision**: introduce `auto_invest.backtest.broker.BacktestBroker`, a class that implements the same call surface the order router calls on `ResilientClient` for order submission (`submit_order` etc.) but persists `SimulatedFill` rows to an in-memory ledger and never makes network calls. `BacktestBroker` is constructed by the engine and passed to `Worker.__init__(broker=...)`. The order router is unchanged.

**Rationale**:
- The order router (`execution/order_router.py`) is non-Kernel; substituting its broker dependency is a clean DI seam.
- Reusing the same call signatures means adding a new broker call site in live (e.g. cancel-replace, post-launch) automatically requires the BacktestBroker to grow the same call site, surfacing missing coverage as a type error rather than a silent omission.

**Alternatives considered**:
- **Reuse `ResilientClient` with a recorded-response transport**: rejected — would still go through HTTP serialisation paths, slower and noisier than a direct in-memory ledger; also leaks broker-specific error semantics into the backtest where they don't belong.

---

**All `NEEDS CLARIFICATION` markers resolved**: yes (all five from `/speckit-clarify` Q1–Q5 are integrated; the planning-time questions R-1..R-12 are now decisions).

**Ready for Phase 1**: yes.
