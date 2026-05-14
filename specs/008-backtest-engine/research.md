# Phase 0 — Research: Backtest Engine

Resolves the open technical questions implied by the clarified spec
(`spec.md` § Clarifications, 2026-05-13) and the plan. Each entry is
intentionally short: a decision, the reasoning, and what was rejected.

## R-B1 — Clock injection without touching K6 (`worker/schedule.py`)

**Decision**: introduce `auto_invest.backtest.clock.Clock` (Protocol) and `ReplayClock` (concrete). The engine threads the clock through `Worker.tick(now=...)` and every existing function in `worker/schedule.py` (all of which already take `now: datetime` as a parameter). No edit to `worker/schedule.py`.

**Rationale**: `worker/schedule.py` is already pure-functional with explicit `now` parameters (`is_session_open(now)`, `next_session_open(now)`, `last_session_close(now)`, …). The engine simply supplies the `now` values from the `ReplayClock`. This is the cheapest possible non-Kernel design.

**Rejected alternatives**:
- *Monkey-patch `datetime.now` globally for the run* — works but is fragile under threading, and any code that captures `datetime.now` at import time (none currently, but future-proofing) would be missed.
- *Edit `schedule.py` to read a module-level clock* — would be a K6 touch. Disallowed.

## R-B2 — Wall-clock leak detection (`WALL_CLOCK_LEAK`)

**Decision**: implement `WallClockGuard` as a context manager that monkey-patches `datetime.datetime` and `time.time` in `auto_invest.*` module namespaces during the replay run. On any call from within the replay's call stack, raise `WallClockLeakError` and record an `ERROR` audit row with `reason="WALL_CLOCK_LEAK"`. The guard is in effect ONLY inside `backtest.run.run_backtest()`; live worker code paths are unaffected.

**Rationale**: detection must catch a developer accidentally adding `datetime.now()` deep in an indicator or risk-gate path. A namespace-scoped patch is precise enough and doesn't require code-coverage instrumentation. Performance overhead is one attribute lookup per `now()` call (negligible).

**Rejected alternatives**:
- *`freezegun`* — works for tests but freezes time to a single value; replay needs time to advance with each bar, which `freezegun` can do via `tick=True` but adds an unnecessary dep and obscures intent.
- *AST scan at test time* — catches the static case but misses dynamic imports / `getattr(datetime, 'now')`.
- *Subprocess sandboxing* — overkill for v1 single-machine use.

## R-B3 — Pessimistic limit-order fill semantics (FR-B07)

**Decision**: a limit BUY fills at price `min(limit, bar.open)` (i.e., the more conservative of the two) iff `bar.low ≤ limit` AND `bar.volume ≥ order.qty`. A limit SELL fills at `max(limit, bar.open)` iff `bar.high ≥ limit` AND `bar.volume ≥ order.qty`. No partial fills in v1; orders that fail either condition remain open. Time-in-force values supported: `DAY` (cancels at session close) and `GTC` (carries to next session).

**Rationale**: the open-anchored choice is more conservative than mid- or close-anchored because intraday adverse drift is more likely than favourable when a limit is touched. Volume gate prevents the "single-share micro-bar fills 10,000 shares" failure mode. Spec 007's audit-integrity check considers slippage assumption deviations from this default a spec-level decision; this default is recorded in every report header so the operator cannot misread the result.

**Rejected alternatives**:
- *Mid-of-bar fill* — easier but unrealistically optimistic.
- *Partial fills proportional to volume share* — adds complexity to v1; provably reduces fill counts only marginally for the operator's profile (≤10 rules, ≤20 symbols, daily bars).
- *VWAP fill* — requires minute-level data v1 does not have.

## R-B4 — Sharpe ratio convention

**Decision**: per-rule daily returns, geometric mean, annualised by `sqrt(252)`, risk-free rate `0.0` (documented in every report header). Aggregate Sharpe uses the same convention on the per-rule-weighted return series.

**Rationale**: matches the convention in most retail backtest reporting. Operator is non-developer; consistency with what they will read elsewhere outweighs theoretical refinement. Zero RFR is the simplest defensible choice for a v1 that is comparing to "do nothing" rather than to bonds.

**Rejected alternatives**:
- *Sortino instead of Sharpe* — better for asymmetric returns but harder to interpret for the operator; can be added later non-breakingly.
- *Annualisation by trading-day count of the actual window* — varies per run, harder to compare across windows.

## R-B5 — Determinism boundary (FR-B15)

**Decision**: byte-identical contract covers `metrics.csv`, `per-rule/*/orders.json`, `per-rule/*/fills.json`, `per-rule/*/gate-rejections.json`. `backtest-run.json` and `summary.md` MAY differ in three fields only: `run_id`, `start_ts`, `end_ts`. `audit_log` rows for `BACKTEST_STARTED` / `BACKTEST_COMPLETED` are not part of the byte-identical contract (they carry the same volatile fields).

**Rationale**: spec 007's hardened canary needs reproducibility of decision outputs (orders, fills, gate rejections, metrics) — those are what the canary's metric-bands compare. Volatile fields are necessary for forensics (each run has a unique id; each run records when it ran). Hashes computed by spec 007's replay verifier MUST exclude those three fields.

**Rejected alternatives**:
- *Include `start_ts`/`end_ts`* — would require freezing the clock, which is the opposite of what `WallClockGuard` enforces. Bad coupling.
- *Hash `audit_log` rows too* — would force the operator into a separate SQLite for backtest, breaking the "one audit log, filtered by event-type" simplicity.

## R-B6 — CSV ingest format

**Decision**: see `contracts/ohlcv-csv.md`. Header row required, lowercase column names: `session_date`, `open`, `high`, `low`, `close`, `volume`, `session_schedule_tag`. Dates ISO-8601 (`YYYY-MM-DD`). Prices are decimal strings up to 6 dp. Volume integer. `session_schedule_tag` ∈ {`regular`, `early_close`, `holiday`, `halted`}. One file per symbol; file name `<SYMBOL>.csv`. Sort by `session_date` ascending; duplicate dates rejected at ingest.

**Rationale**: simplest format the operator can produce from any vendor export. Lowercase columns avoid case-sensitivity bugs. `session_schedule_tag` lets the engine handle NYSE early-close days (e.g., day after Thanksgiving) without hard-coding them.

**Rejected alternatives**:
- *Parquet ingest* — better long-term but operator's vendor exports are CSV; convert once at ingest.
- *Single multi-symbol CSV* — harder to update one symbol; rejected.

## R-B7 — Replay granularity

**Decision**: v1 ticks at bar boundaries — one `Worker.tick` per (symbol, session_date). The clock advances to the bar's `session_close` (or `early_close` if tagged) for indicator/strategy evaluation, and fills are settled at that same instant. Sub-bar (intraday minute) granularity is OUT of v1.

**Rationale**: the operator's spec-001 strategies are end-of-day or threshold-on-close types. Spec 001 already operates on daily bars (`market_data/feed.py` polls quotes, not high-frequency). Bar-level replay matches the live engine's resolution; sub-bar would require minute data v1 doesn't have.

**Rejected alternatives**:
- *Minute-bar replay* — requires vendor minute data, raises ingest complexity 10×. Defer.
- *Event-driven (trade tape)* — out of scope for retail rules.

## R-B8 — Kernel-guard integration (FR-B12)

**Decision**: at the very top of `backtest/run.run_backtest()`, call `subprocess.run(["git", "status", "--porcelain"], …)`, parse the changed paths, then call `auto_invest.deploy.kernel_guard.kernel_diff_check(paths)`. If the report has `touched=True`, write an `ERROR` audit row with `reason="BACKTEST_BLOCKED_KERNEL_TOUCH"` and exit code 78 (specific to kernel touch). The check is bypassable only with `--allow-kernel-edits` for the spec author's own development; the flag itself is logged.

**Rationale**: defense-in-depth. The operator should not silently run an experimental backtest against a kernel-edited working tree. Re-using spec 006's shipped guard keeps a single source of truth for "what counts as Kernel".

**Rejected alternatives**:
- *No pre-flight check* — relies on operator discipline. Constitution IX.B-1 implies defense-in-depth.
- *Hard refuse without bypass flag* — blocks legitimate spec-008 self-development. Hence the audited bypass flag.

## R-B9 — Spec-004 judgment-point stub interface

**Decision**: `backtest/judgment_stub.py` exposes `class JudgmentStub` with method `decide(decision_class: str, inputs: dict) -> dict`. Each call emits `LLM_CALL_STUBBED` (decision_class, input_hash, stubbed_return) and returns the rule's documented "safe default" branch. Spec 004's future judgment-point modules MUST accept a `JudgmentStub` instance as their LLM client when `BACKTEST_MODE=1` env var is set; the live `AnthropicClient` is forbidden when that env var is set, raising `BACKTEST_JUDGMENT_LEAK` (logged as an `ERROR` audit row).

**Rationale**: the contract is minimal — one method, two args, one return — so spec 004 isn't constrained in design. The env-var switch is checked once at process start in spec-004 code (when it ships), keeping the backtest engine's interface stable.

**Rejected alternatives**:
- *Per-call fixture file recorded from production* — useful for reproducing exact past decisions but adds a fragile capture pipeline; defer to v2.
- *Unconditional refusal (`BACKTEST_JUDGMENT_DISALLOWED`)* — too strict; defeats backtesting of a strategy that uses a judgment point.

## R-B10 — Multi-rule concurrency

**Decision**: rules are evaluated sequentially per (session_date, rule) in declaration order. Inside each (date, rule) the existing `Worker.tick` semantics apply. No parallelism in v1.

**Rationale**: spec 001's live worker is single-threaded over rules in a tick; matching that semantic in replay is the only way to guarantee the determinism contract (FR-B15) without introducing async-ordering subtleties. Ten rules × ≤5 years × ≤252 bars is ≈ 12,600 evaluations — comfortably under the 5-minute SC-B01 budget on the operator's machine.

**Rejected alternatives**:
- *Parallel rule evaluation* — would require a separate ordering oracle for the audit log; not worth the complexity for v1's scale.

## R-B11 — Sharpe / drawdown computation library choice

**Decision**: use `pandas` + `numpy` only (already in `pyproject.toml`). No `empyrical` or `quantstats` dependency.

**Rationale**: drawdown and Sharpe are 10 LOC each in numpy. Adding a backtest-stats library increases supply-chain surface and pins us to that library's annualisation convention.

**Rejected alternatives**:
- *`empyrical`* — widely used but unmaintained (last release 2020-10).
- *`quantstats`* — heavyweight; pulls in plotting which we don't need.

## R-B12 — Dataset versioning

**Decision**: `dataset_version` is the hex SHA-256 of a deterministic manifest: sorted list of `(symbol, file_size_bytes, file_sha256)` for every CSV in the ingest source directory. Manifest is recorded under `data/history/<dataset_version>/manifest.json` at ingest time. The backtest CLI accepts `--dataset-version` (explicit) or resolves to the latest if omitted.

**Rationale**: lets the operator see which set of CSV files a backtest ran against. SHA-256 of the manifest is stable across renames (file_sha256 captures content), letting two operators on different machines verify they ran against the same data.

**Rejected alternatives**:
- *Use ingest timestamp* — not reproducible across machines.
- *Git LFS* — too heavyweight for v1.
