# Phase 0 Research: Automated US-Equity Trading MVP

This document records the research-and-decision step for every technical
unknown surfaced by `plan.md`. Each entry follows the required shape:
**Decision** / **Rationale** / **Alternatives considered**.

---

## R-1. KIS OpenAPI Python adapter

**Decision**: Build a minimal in-house adapter over `httpx` covering only the endpoints v1 needs (overseas-stock quote, overseas-stock order, overseas-stock balance/positions, token issue/refresh).

**Rationale**:
- The surface area we need is small (≈6 endpoints for v1). A focused in-house wrapper is reviewable end-to-end and easy to fit with our risk/audit scaffolding.
- Keeps dependency footprint minimal — material for constitution V (secrets) and VII (robustness), since every external library is a potential leak / failure mode we must audit.
- We control the retry/rate-limit/circuit-breaker integration (constitution VII) without fighting an upstream library's defaults.

**Alternatives considered**:
- **`python-kis` (community PyPI package)** — broader feature surface, active community. Rejected because v1 needs only a fraction of the surface, and we would still need to wrap it for retry/breaker semantics; the wrapping would be larger than the in-house client itself.
- **Official `koreainvestment/open-trading-api` Python samples** — these are reference scripts, not a packaged library. Useful as a documentation source for endpoint shapes and headers, but not as a runtime dependency.

---

## R-2. Indicator computation library

**Decision**: `ta` (bukosabino/ta), accessed through a thin facade module (`strategy/indicators.py`) that validates inputs (sufficient bar count, monotonic timestamps, no NaNs) before delegating.

**Rationale**:
- Pure Python on top of `pandas`/`numpy`; no C compilation required, so the install story is friction-free across operator hosts.
- Covers EMA, SMA, RSI, MACD, Bollinger, etc. — the v1 trigger set will not exhaust it.
- The facade keeps the public dependency a single name and lets us swap implementations later (e.g., to a vectorized in-house impl) without disturbing strategies.

**Implementation-time amendment (2026-05-02)**: this entry originally chose `pandas-ta`. At dependency-install time we found PyPI only publishes `pandas-ta>=0.4.67b0`, which requires Python 3.12+; our `requires-python` is `>=3.11`. We considered (a) bumping `requires-python` to 3.12, (b) reverting to a yanked `pandas-ta<0.4`, (c) switching to `ta`. We chose (c): `ta` covers the same indicator surface, supports Python ≥3.7, and the facade pattern made the substitution local. This deviation does not affect spec, plan structure, or tasks beyond a single dependency name.

**Alternatives considered**:
- **`pandas-ta`** — original choice; not viable on Python 3.11 as of 2026-05.
- **TA-Lib** — battle-tested, but requires a system-level C library; install pain on operator machines is a recurring support tax.
- **In-house only (numpy + pandas)** — fine for SMA/EMA, but quickly reinvents the wheel for RSI/MACD/Bollinger. Reject for v1.

---

## R-3. Storage backend for audit log + price bars + positions

**Decision**: One SQLite database file at `data/auto_invest.db`, opened with WAL journal mode and `synchronous=NORMAL`. Audit log tables are INSERT-only (enforced by code review and a CHECK on a `frozen` boolean column for any mutable mirrors).

**Rationale**:
- Single-file SQLite gives ACID semantics, fast local reads, and a universally-available CLI (`sqlite3`) for ad-hoc forensics — directly supporting constitution IV (audit log) and SC-005 (full reconstructability from log).
- WAL mode keeps the writer fast and concurrent-readable, important during the daily report generation while the worker may still be running.
- INSERT-only conventions for audit tables map cleanly to constitution IV's append-only requirement; mutability is contained to a small `current_positions` table that is reproducible from `fills`.

**Alternatives considered**:
- **JSONL files (one log per day)** — simpler, but querying across days for the daily report or reconciliation requires either DIY indexing or `jq` gymnastics. Rejected as cost > benefit.
- **PostgreSQL** — overkill for single-operator scope; introduces a second runtime dependency the operator must run.

---

## R-4. Process / concurrency model

**Decision**: Single-process `asyncio` event loop. The CLI command `auto-invest run` boots the loop, schedules a price-feed task per active rule, a trigger-evaluation task per rule, and an APScheduler instance for end-of-session reconciliation and report jobs.

**Rationale**:
- Trading is I/O-bound (HTTP/WebSocket against KIS, SQLite writes); asyncio matches the workload without paying for a thread pool's overhead.
- A single process simplifies the audit log invariant — one writer, one append-order.
- APScheduler integrates with asyncio and removes the need to roll our own session-boundary scheduling.

**Alternatives considered**:
- **Threaded** — would force locking around audit log writes and SQLite writes; SQLite's single-writer model already serializes us, so threads add nothing.
- **Multiprocess** — would let us parallelize indicator calculation, but at v1 scale (≤ 50 symbols, ≤ 20 rules) a single core is comfortably sufficient. Reconsider if scaling >> v1.

---

## R-5. HTTP client

**Decision**: `httpx` (sync API for tests, async API for the main loop).

**Rationale**:
- Same library covers both sync (test recordings, scripts) and async (worker loop). One mental model.
- First-class support for connection pools, timeouts, and proxies — essentials for a long-running worker against an external API.
- Already a transitive dependency via `anthropic`; using it natively avoids parallel HTTP stacks.

**Alternatives considered**:
- **`requests`** — sync only, would force a second HTTP stack for the async loop.
- **`aiohttp`** — async only, would force a second HTTP stack for tests/CLI.

---

## R-6. Market calendar

**Decision**: `exchange_calendars` library for NYSE/NASDAQ session boundaries.

**Rationale**:
- Active maintenance, broad exchange coverage, returns deterministic open/close times in the venue's local timezone.
- Handles holidays, half-days, and DST transitions natively — these are exactly the edge cases listed in spec.md.

**Alternatives considered**:
- **`pandas-market-calendars`** — comparable feature set, slower release cadence; functionally interchangeable. Pick one and standardize.
- **Hand-coded holiday tables** — guaranteed to drift; rejected.

---

## R-7. Configuration format

**Decision**: TOML, parsed with stdlib `tomllib`. Schema validation by pydantic v2 models in `config/rules.py`, `config/whitelist.py`, `config/caps.py`.

**Rationale**:
- TOML is friendly to non-technical operators (closer to INI than YAML's whitespace traps).
- `tomllib` is in the standard library on 3.11 — zero dependency cost.
- Pydantic gives precise, message-rich validation errors that satisfy FR-001 and FR-011 ("refuse to start").

**Alternatives considered**:
- **YAML** — common in ops, but indentation accidents and the "Norway problem" make it riskier for safety-critical config.
- **JSON** — no comments, painful for human-edited config.
- **Python module** — most flexible, but lets arbitrary code run at config load; rejected on principle II (deny-by-default) thinking.

---

## R-8. Logging

**Decision**: Stdlib `logging` configured for line-delimited JSON, with a custom `RedactionFilter` that replaces any registered secret value (`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`, access tokens) with the literal string `***REDACTED***` before the record reaches any handler.

**Rationale**:
- Stdlib is sufficient and adds no dependency. JSON output makes downstream tooling (jq, Loki, Datadog) trivial later.
- A filter — not a formatter — runs upstream of every handler, so even tracebacks and exception args are redacted (covers FR-009 fully).
- Secret values are registered through a single function `register_secret(value)` that the secret loader calls right after reading `.env`. This keeps the redaction list authoritative.

**Alternatives considered**:
- **`structlog`** — better ergonomics, but adds a dependency for a benefit (structured kwargs) we can replicate with the stdlib `extra` dict.
- **`loguru`** — pleasant API; rejects against the "minimize dependency surface" theme.

---

## R-9. Secret loading

**Decision**: `python-dotenv` to read `.env` at process start; values are pushed through `register_secret()` (R-8) and then placed into a frozen `Secrets` dataclass that the rest of the code consumes.

**Rationale**:
- Operators run this themselves; `.env` is the lowest-friction format, and `.env` is in our `.gitignore`.
- Centralizing the loader means we have one and only one entry point for secret material — easier to audit (constitution V).
- A frozen container prevents accidental mutation of secrets after load.

**Alternatives considered**:
- **OS-only environment variables** — works, but `.env` improves the operator quickstart story.
- **Vault / cloud secret manager** — out of scope for single-operator v1; revisit when the operator runs the worker on managed infrastructure.

---

## R-10. Operator halt mechanism

**Decision**: A halt-flag file (`data/halt.flag`). Presence of the file means "no new orders." The worker checks the flag (a) at startup, (b) before every order submission, and (c) on every loop tick. An `auto-invest halt --reason "<text>"` CLI command writes the file with a JSON payload (timestamp + reason). `auto-invest resume --confirm` removes it.

**Rationale**:
- Survives worker restarts (FR-013 requires persistence across restarts).
- Filesystem-mediated, so the operator can also halt manually from a shell with `touch data/halt.flag` if the worker is unresponsive.
- Order of checks (startup, pre-order, tick) makes the worst-case latency from "halt issued" to "no further orders" bounded by the loop tick (target: < 1 s).

**Alternatives considered**:
- **POSIX signal (e.g., SIGUSR1)** — does not survive a restart and is awkward to inspect.
- **In-process flag via IPC socket** — adds a daemon-control protocol we don't need yet; revisit if/when the worker grows a control plane.

---

## R-11. Default sizing-cap and canary values

**Decision** (declared here so that the plan is self-contained; operator may override per environment in `config/caps.toml`):

| Knob | Default | Rationale |
|------|---------|-----------|
| `per_trade_pct` | 5.0 % of total capital | Each single order can lose at most ~5% of capital under worst-case slippage; this matches widely-used retail sizing heuristics. |
| `per_symbol_pct` | 20.0 % of total capital | Caps concentration risk in any single ticker without forcing over-diversification. |
| `global_exposure_pct` | 80.0 % of total capital | Leaves a 20% cash buffer for FX drift, settlement, and margin headroom. |
| `canary_capital_pct` | 5.0 % of total capital | Bounds canary-stage exposure to a "tuition" fraction; matches FR-014's expectation of a small but real-money signal. |
| `canary_min_duration_days` | 10 trading days | Long enough to expose a strategy to multiple session types (high vol, low vol, gap days) before promotion. |
| `canary_acceptance_drawdown_pct` | 3.0 % | Strategy autopauses if its canary drawdown exceeds this for the duration window. |

**Rationale**: These defaults are conservative enough to be safe for an operator who has not yet tuned them, and explicit enough that any future change shows up in a config diff (constitution VIII — change discipline).

**Alternatives considered**: Tighter caps (per_trade 2%, per_symbol 10%) would be safer but throttle the system below practical usefulness for a personal account. Looser caps (per_trade 10%) would exceed standard retail risk hygiene.

---

## R-12. Retry / rate-limit / circuit breaker

**Decision**:
- Retries: `tenacity` with exponential backoff, jitter, max 4 attempts on transient HTTP errors.
- Rate limit: in-house `AsyncTokenBucket` keyed per API host (KIS REST and WebSocket separately).
- Circuit breaker: in-house `CircuitBreaker` per call site with `closed → open → half-open` states; opens after N consecutive failures, cooldown M seconds. Defaults: N=5, M=30 s.

**Rationale**:
- `tenacity` is the de-facto Python retry library; battle-tested and well-documented.
- Rate limiter and breaker are kept in-house to stay close to the worker's asyncio loop and to avoid pulling in a heavier resilience framework. Both fit in <100 LOC each and are exhaustively unit-testable.

**Alternatives considered**:
- **`aiobreaker` / `pybreaker`** — proven libraries; the in-house implementation is small enough that the cognitive cost of a third-party dep outweighs the maintenance saving.
- **Manual retry per call site** — reject; too easy to miss one path.

---

## Summary

All Technical-Context unknowns have a recorded decision. Phase 1 (data model + contracts + quickstart) can proceed.
