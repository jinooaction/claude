# Phase 0 Research: Multi-Asset Data Infrastructure & Backtest Engine

This document records the research-and-decision step for every
unknown surfaced by `plan.md` and the open decisions (OD-1 … OD-6)
left in `spec.md`. Each entry follows the required shape:
**Decision** / **Rationale** / **Alternatives considered**.

---

## R-1. Second ingestion adapter (resolves OD-1)

**Decision**: A keyless **public-crypto-bars adapter** sourcing 1m /
1h / 1d candles from a public exchange API (Binance public klines or
Coinbase Exchange public candles, whichever is reachable from the
operator's host without auth at adapter-write time). The adapter
declares `asset_class="crypto"`, `venue=<exchange>`, supports
`kind={"ohlcv_1m","ohlcv_1h","ohlcv_1d"}`, and uses the always-open
market calendar.

**Rationale**:
- Exercises the always-open calendar path (FR-D-006) — a test the
  KIS US-equity adapter cannot give us.
- Exercises the multi-vendor key (`vendor` column) without requiring
  a paid subscription.
- Exercises the second-asset-class path of FR-D-001 / SC-001 (new
  adapter must land in < 200 LOC without modifying existing
  adapters).
- Crypto is **not** in the constitution's tradable scope; ingesting
  it does not trigger a constitution amendment because trading is
  out of scope until a future spec adds it.

**Alternatives considered**:
- **Free FX bars** (e.g., a public quote feed) — viable but most
  free FX sources have either authenticated tiers or sparse history.
  The crypto path is cleaner.
- **A second US-equity vendor** (e.g., a free EOD CSV) — would
  exercise multi-vendor disagreement (FR-D-005), but skips the
  always-open calendar. We get more coverage from crypto.
- **Sample-CSV adapter** (operator-supplied flat files) — useful
  later but does not exercise rate-limit / retry / breaker plumbing
  the way a real HTTP source does.

**Implementation note**: the adapter ships with a recorded fixtures
directory under `tests/fixtures/historical/crypto/` so CI never hits
the live exchange; live calls are gated by `CRYPTO_LIVE_TEST=1`.

---

## R-2. Slippage and market-impact model (resolves OD-2)

**Decision**: The default cost model is the sum of three configurable
components, applied per simulated fill:

1. **Commission**: `commission_bps × notional + commission_min_usd`
   (defaults: 0 bps, $0 — operators with KIS may set 0; an explicit
   value is required for spec 005's first canary).
2. **Half-spread slippage**: `half_spread_bps × notional`
   (default: 5 bps for liquid US-equity 1m bars; 10 bps for the
   crypto adapter; configurable per-symbol override).
3. **Square-root market impact**: `impact_coeff × σ × sqrt(order_qty / bar_volume) × notional`
   where `σ` is the bar's high-low range divided by close, and
   `impact_coeff` defaults to 0.1 (a conservative literature value).

A **participation cap** (default: 10% of bar volume) limits the
quantity that can fill within a single bar; remainder follows the
order's declared time-in-force.

**Rationale**:
- Three separable knobs make each cost component independently
  configurable and independently inspectable in the report
  (FR-B-004).
- Half-spread + square-root impact is the cheapest defensible model
  that can hold up under operator scrutiny: it is the form that
  matches the empirical literature (Almgren et al.) within an order
  of magnitude.
- Defaults err **expensive** so a strategy that only barely passes
  in backtest has been stress-tested for cost; a generous-cost model
  understates real friction and produces the false-confidence
  failure mode this spec exists to eliminate.

**Alternatives considered**:
- **Fixed bps slippage only** — simpler, but ignores order-size
  effects entirely. Acceptable as a fallback (and we expose it via
  `impact_coeff=0`), but not as a default for a "world-class"
  service.
- **Full L2/L3 simulation** — most accurate, but the data layer in
  v2 does not ingest order books. Reserved for a future spec.
- **Volatility-scaled spread** — alternative formulation of (2) and
  (3) merged. Rejected because the merged form makes it harder for
  the operator to attribute cost in the report.

---

## R-3. OOS reservation default (resolves OD-3)

**Decision**: The default OOS window is **`max(20% of the configured
window, last 6 calendar months)`**, snapped to the nearest session
boundary on the venue's calendar. Operators may override with an
explicit `oos_window=...` in the backtest config.

**Rationale**:
- 20% is the lower bound used widely in finance ML literature; for
  short windows (e.g., a 1-year backtest) 20% is too short to expose
  regime changes, so the 6-month floor catches that case.
- Snapping to the calendar prevents fold boundaries that fall mid-
  session, which would make corporate-action handling ambiguous.

**Alternatives considered**:
- **Fixed 6 months** — fails for very long windows where 20% is the
  better proxy.
- **Fixed 20%** — fails for short windows, see above.
- **Operator must specify** — rejected: a default is needed so a
  one-shot `auto-invest backtest` invocation produces a defensible
  report without configuration ceremony.

---

## R-4. Promotion threshold defaults (resolves OD-4)

**Decision** (operator may override per environment in
`config/promotion.toml`; values below are the conservative defaults):

| Threshold | Default | Rationale |
|---|---|---|
| `min_oos_sharpe` | 1.0 | Below 1.0 is generally indistinguishable from random noise after costs. |
| `max_oos_drawdown_pct` | 15 | Caps the canary downside at a level the operator can absorb without psychological damage. |
| `min_oos_trade_count` | 30 | Below 30 trades, Sharpe and hit rate are statistically unreliable. |
| `min_oos_window_days` | 90 | Less than ~3 months of OOS data hides regime risk. |
| `max_live_vs_backtest_drawdown_divergence_pct` | 5 | Threshold for the divergence flag (FR-P-004). |
| `divergence_alert_window_days` | 5 | Sustained divergence over this window triggers the flag. |

**Rationale**:
- These defaults are deliberately set so **no current
  hand-written rule from spec 001 trivially passes** without a real
  measurable edge. Promotion is an earned status, not a default.
- The thresholds are all OOS-only; in-sample metrics never
  influence promotion (this is the whole point of the OOS
  reservation in R-3).

**Alternatives considered**:
- **Stricter (Sharpe ≥ 2.0, DD ≤ 8%)** — would block too many
  legitimate strategies for a personal-account scope.
- **Operator-only thresholds, no defaults** — rejected: defaults
  give a useful baseline for the first promotion attempt and are
  easy to override.

---

## R-5. Storage backend for the unified data store (resolves OD-5)

**Decision**: **Extend the existing SQLite database**
(`data/auto_invest.db`) with the new tables described in
`data-model.md`. Schema is designed so that a future migration to a
columnar store (Parquet on disk, partitioned by
`(asset_class, venue, instrument, ymd)`) is mechanical: every table
has a stable primary key set, no foreign-key joins on hot read
paths, and `as_of_ts` is a first-class column rather than a side
table. We add a `bars_to_arrow()` export utility in v2 so the
downstream Parquet path is exercised by tests but is not the
primary read path.

**Rationale**:
- v2 scale (≤ 50 instruments × ≤ 5 years × 1m bars ≈ tens of
  millions of rows) fits SQLite comfortably with WAL and proper
  indices. Switching to Parquet now is premature.
- Operator already runs a single SQLite file (constitution-friendly
  audit-log discipline). Adding a second store doubles operational
  complexity for no v2 benefit.
- The forward-compat design means the migration cost is "rewrite
  the read path, keep the schema" — not "redesign the schema".

**Alternatives considered**:
- **Parquet now** — best for the 100-instrument-and-up regime;
  premature today. Reserved for spec 006 (operational hardening).
- **DuckDB on top of Parquet** — interesting hybrid; rejected for v2
  because it adds a runtime dep for a benefit that does not bind
  yet.
- **Time-series DB (TimescaleDB / InfluxDB)** — overkill for
  single-operator scope; introduces a server process the operator
  must run.

---

## R-6. Backtest CLI surface (resolves OD-6)

**Decision**: Both surfaces are first-class:

- **CLI flags** for one-off interactive runs:
  `auto-invest backtest --rule path/to/rule.toml --from 2021-01-01 --to 2025-12-31 --vendor kis`
- **TOML config** for reproducible / CI runs:
  `auto-invest backtest --config path/to/run.toml`

The TOML config file is canonical; CLI flags map onto it via a
documented surjection (a `run.toml` is auto-generated from any flag
invocation and stored under `data/backtests/<run_id>/inputs/run.toml`
so every run is reproducible from its own directory). See
`contracts/backtest-config.md` for the schema.

**Rationale**:
- CLI flags make "kick off a quick backtest" a one-liner, which is
  what the operator wants for the first 90% of runs.
- TOML config makes the run reproducible and reviewable as a single
  artifact — essential for `/speckit-tasks` CI gates and for the
  promotion seal which pins a config hash.
- The auto-generated `run.toml` inside the run directory closes the
  loop: a flag-launched run becomes a file-launched re-run with no
  operator effort.

**Alternatives considered**:
- **Flags only** — fails the reproducibility requirement.
- **Config only** — friction-heavy for one-shot runs.
- **Argparse-defined config** — rejected; we already use Pydantic v2
  + tomllib in spec 001 (R-7) and reuse buys us validation for free.

---

## Summary

All open decisions (OD-1 … OD-6) and all `NEEDS CLARIFICATION`
markers from `plan.md` Technical Context are resolved. Phase 1
(`data-model.md`, `contracts/`, `quickstart.md`) can proceed.
