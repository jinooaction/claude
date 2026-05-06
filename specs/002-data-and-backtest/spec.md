# Feature Specification: Multi-Asset Data Infrastructure & Backtest Engine

**Feature Branch**: `002-data-and-backtest`
**Created**: 2026-05-06
**Status**: Draft
**Input**: Operator description: "Spec 001 shipped a safe execution
shell but no measurement layer. The north star (CLAUDE.md) is a
world-class, self-improving, multi-asset automated investment service.
Before any new strategy reaches live capital, it must pass a measured
backtest. Build the data infrastructure and backtest engine that makes
constitution principle VI (`backtest → canary → full-live`)
operational, and design both layers asset-class agnostic from the
start."

## Why this spec exists (read first)

Spec 001 deliberately listed "backtest engine" as out of scope and
assumed backtest results would be supplied by a sibling concern. That
sibling is this spec.

Without 002, the system cannot:

- Distinguish a profitable rule from a lucky rule.
- Honour constitution principle VI's `backtest → canary → full-live`
  staged rollout — there is no `backtest` stage today.
- Support any asset class beyond US equities, because all of v1's data
  plumbing is wired to KIS overseas-stock OHLCV only.
- Generate evidence (live-vs-backtest divergence, regime fit,
  parameter drift) that feeds the self-improving loop in the north
  star.

This spec is therefore the foundation of every future strategy and
asset-class extension. It is **not** a strategy. Strategy R&D
(hypotheses, factors, portfolio construction) is sibling spec 003 and
consumes 002's outputs.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Operator can backtest a candidate rule before risking capital (Priority: P1)

The operator has a candidate trading rule (the same TOML-declared rule
shape as in spec 001, or a programmatic strategy that produces orders
from quotes/bars). The operator points the backtest engine at a
historical window, presses one CLI command, and receives a written
report covering returns, drawdown, hit rate, exposure, turnover, and
estimated transaction cost. The report is reproducible bit-for-bit on
the same machine and is auditable end-to-end.

**Why this priority**: This is the smallest end-to-end slice that
delivers the spec's purpose. Without it, the system cannot honour
constitution principle VI. Every other story in this spec exists to
make this story trustworthy, not to replace it.

**Independent Test**: Take a sample rule and a 12-month historical
window for one US-listed symbol; run `auto-invest backtest --rule
<file> --from <date> --to <date>`; verify the report exists, contains
the required metric set, runs in under one minute on operator
hardware, and produces byte-identical output on a re-run.

**Acceptance Scenarios**:

1. **Given** a TOML rule referencing a whitelisted symbol and a
   historical window for which sufficient data is locally cached,
   **When** the operator runs the backtest CLI, **Then** the engine
   replays the rule against the historical bars in chronological
   order, applies the same risk gates that the live router applies,
   produces orders / fills, and emits a report file plus a JSON
   results file inside `data/backtests/<run_id>/`.
2. **Given** the same inputs, **When** the operator re-runs the
   backtest, **Then** the run_id changes but the metrics, the order
   sequence, and the fills are byte-identical (deterministic).
3. **Given** a rule whose required history window is longer than the
   data locally cached, **When** the operator runs the backtest,
   **Then** the engine refuses to run with an explicit "insufficient
   warm-up data" message naming the missing range, and exits non-zero.
4. **Given** a rule that, during the backtest window, would have
   submitted an order that violates a sizing cap, **When** the
   backtest evaluates that bar, **Then** the engine rejects the order
   in the simulated audit log with the same gate name and reason that
   the live router would have used (no divergence between live and
   backtest gating).
5. **Given** a corporate action (split / dividend) inside the backtest
   window, **When** the engine replays bars across that date, **Then**
   the engine adjusts position quantity / cost basis correctly and
   the report reflects the adjusted P&L without operator
   intervention.

---

### User Story 2 — Replay is point-in-time correct and uses realistic execution costs (Priority: P1)

A backtest that suffers from look-ahead bias, ignores transaction
costs, or assumes ideal fills is worse than no backtest because it
gives the operator false confidence. This story raises P1 with story 1
because the *trustworthiness* of the report is what makes the report
worth reading.

**Why this priority**: Equally critical with story 1. A working but
biased backtest is a footgun, not a feature.

**Independent Test**: Construct a known-bad strategy that "buys at
yesterday's low, sells at tomorrow's high" using only bar data
available at decision time; verify the backtest reports a realistic
(not infinite) return.

**Acceptance Scenarios**:

1. **Given** a strategy whose decision at time `t` consults bar
   `[t-1]`, **When** the engine evaluates time `t`, **Then** the
   strategy MUST NOT be able to read any data with a timestamp `> t`
   from the data store; any attempt MUST raise a `LookaheadError` and
   abort the backtest.
2. **Given** a market order in the simulated session, **When** the
   engine fills it, **Then** the fill price MUST include a configured
   slippage component (default: half-spread + impact model) and a
   commission; both costs MUST appear as line items in the report.
3. **Given** a limit order whose price is on the wrong side of the
   bar's range during its time-in-force window, **When** the engine
   evaluates fills, **Then** the order MUST NOT be filled and MUST be
   recorded as expired/cancelled in the simulated audit log.
4. **Given** a bar whose volume is too small to absorb the requested
   order size at the modelled impact, **When** the engine evaluates
   the fill, **Then** the fill is partial in proportion to a
   configured participation cap, and the unfilled remainder follows
   the rule's declared time-in-force behaviour.
5. **Given** the operator declares an explicit cost model
   (commission_bps, slippage_bps, market_impact_curve), **When** the
   backtest runs, **Then** every order's modelled cost is computed
   from those parameters and recorded so the report's "transaction
   cost" line is reconstructable from the audit log alone.

---

### User Story 3 — Data store ingests multi-source, multi-asset history without rewrites (Priority: P2)

A "world-class" automated investment service consumes more than
OHLCV. The data layer must accept additional sources (news,
fundamentals, alt-data, macro indicators, options chains, on-chain
data) over time, and must work for asset classes beyond US equities
without schema rewrites. This story makes the data layer extensible
from day one.

**Why this priority**: Less urgent than P1 because story 1 and 2 can
ship with an OHLCV-only ingestion. But the *schema* and the *adapter
interface* must be set in 002 so adding a vendor or an asset class in
a future spec is a config change, not a migration. Locking the schema
later is far more expensive than designing it open now.

**Independent Test**: Implement two ingestion adapters (e.g., KIS for
US equities, one publicly-accessible vendor for FX or crypto bars),
load a small slice of each into the unified store, and run
`auto-invest data describe` to confirm both appear under a common
schema with `asset_class` and `venue` fields populated correctly.

**Acceptance Scenarios**:

1. **Given** the data layer's adapter interface, **When** a new
   ingestion adapter is added for a new asset class (e.g., crypto),
   **Then** no existing adapter, no existing rule, and no existing
   backtest result needs to change to keep working.
2. **Given** two adapters writing to the data store, **When** they
   write the same logical instrument (e.g., AAPL on NASDAQ from two
   different vendors), **Then** the store records both sources with a
   `vendor` qualifier and the backtest engine can be told which vendor
   to read from per backtest run, without losing the other.
3. **Given** a non-OHLCV time series (e.g., a fundamentals release, a
   news event, a sentiment score), **When** the adapter writes it,
   **Then** the store accepts it via a generic `event_series` schema
   keyed by `(instrument, ts, kind, payload)` without requiring a new
   table per kind.
4. **Given** a corporate action (split, dividend, ticker change),
   **When** an adapter publishes it, **Then** the store records the
   action with effective date and the backtest engine consumes it
   without operator intervention.
5. **Given** any historical bar in the store, **When** read by the
   backtest engine, **Then** the bar carries an explicit `as_of_ts`
   distinct from `bar_close_ts` so revisions (e.g., late-arriving
   adjusted closes) are observable and never silently overwrite
   earlier point-in-time values.

---

### User Story 4 — Walk-forward and out-of-sample evaluation guard against overfitting (Priority: P2)

A single in-sample backtest is the cheapest way to fool oneself. The
engine must natively support walk-forward windows and held-out
out-of-sample evaluation so a strategy whose parameters were tuned on
window A is *forced* to also report performance on a never-seen
window B before promotion.

**Why this priority**: Less urgent than P1 (a single backtest unblocks
the very first promotion-gate use case), but mandatory before strategy
research (sibling spec 003) can be trusted. Without this story, every
"good backtest" is suspect.

**Independent Test**: Run the same strategy with the same parameters
in three modes — single-window in-sample, walk-forward (rolling 12-month
train, 3-month test, step 3 months), and held-out OOS (last 6 months
reserved). Verify the report shows all three sections side by side with
clearly-labelled in-sample vs out-of-sample metrics.

**Acceptance Scenarios**:

1. **Given** a backtest configuration with an OOS reservation
   declared, **When** the engine runs, **Then** the strategy MUST NOT
   be able to read any data from the OOS window during the in-sample
   phase; this is enforced by the same point-in-time barrier as story
   2.
2. **Given** a walk-forward configuration, **When** the engine runs,
   **Then** each fold reports its own metrics, and the final report
   aggregates them with stability indicators (e.g., per-fold Sharpe
   variance, worst-fold drawdown).
3. **Given** an in-sample report and an OOS report, **When** the
   strategy is later submitted to the canary promotion gate (spec
   001's FR-014 / FR-012), **Then** the gate consumes the OOS metrics
   (not the in-sample metrics) when comparing against acceptance
   thresholds.

---

### User Story 5 — Backtest results are first-class inputs to the canary promotion gate (Priority: P3)

The promotion path defined by constitution principle VI is currently a
manual statement in the spec. This story turns it into machinery: a
backtest result file is the artifact a strategy must possess before
the live worker accepts it as a canary candidate.

**Why this priority**: Useful but not the smallest viable slice — it
becomes essential at the moment the operator first wants to promote
strategy 001 to canary live (spec 005). Until then it can be wired in
last.

**Independent Test**: Submit a rule to the live worker without an
attached backtest result and verify it is rejected at startup with a
"missing backtest" error. Submit the same rule with a
backtest result whose OOS metrics fall below the configured
acceptance threshold and verify the same rejection.

**Acceptance Scenarios**:

1. **Given** the live worker's startup, **When** loading a rule that
   has not been previously promoted, **Then** the worker MUST find an
   accompanying backtest result file (referenced by the rule) whose
   `oos_metrics` clear the configured promotion thresholds; otherwise
   the rule is rejected with a clear reason in the audit log.
2. **Given** a rule was already promoted previously, **When** its
   parameters or its underlying code change in any non-trivial way,
   **Then** the promotion seal is invalidated and a fresh backtest +
   canary cycle is required (this matches constitution VI's "material
   change resets to step 1").
3. **Given** a backtest result file, **When** the live audit log
   later records fills against that strategy, **Then** the daily
   reporter can compute live-vs-backtest divergence as a first-class
   metric and surface it on the daily report (input to the
   self-improving loop in CLAUDE.md's north star).

---

### Edge Cases

- The historical data store is missing bars across a holiday or a
  data outage — the engine MUST detect the gap, refuse to run any rule
  whose indicator window straddles the gap, and report the missing
  range explicitly.
- Two vendors disagree about a bar's value beyond a configurable
  tolerance — the engine MUST record the disagreement, refuse to use
  the bar in a backtest, and surface the discrepancy on
  `auto-invest data describe`.
- A corporate action arrives retroactively (announced after the
  effective date) — the store MUST record the action with its real
  `as_of_ts` and the affected backtests MUST be flagged as needing
  re-run, never silently re-emitted.
- A strategy raises `LookaheadError` during a walk-forward fold —
  the engine MUST abort the entire walk-forward run, not just the
  fold; a strategy that cheats once cannot be trusted across folds.
- The operator runs a backtest with an extremely large window — the
  engine MUST stream rather than load all bars into memory, and MUST
  honour a `--max-runtime` flag that aborts cleanly past the budget.
- The data adapter for a new asset class (e.g., crypto) reports
  24/7 sessions while the existing market-calendar plumbing assumes
  closed sessions — the calendar layer MUST accept "always open"
  venues without per-asset-class branching in higher layers.
- A backtest writes to `data/backtests/<run_id>/`, the run is
  cancelled mid-write — the engine MUST treat the partial directory
  as failed and exclude it from result lookups; failed runs are kept
  for forensics for a configurable retention window.
- A strategy in walk-forward depends on rolling parameter
  recalibration that itself uses a search procedure — the engine MUST
  enforce that the recalibration only sees data inside that fold's
  in-sample window (no global cheating).

## Requirements *(mandatory)*

### Functional Requirements

#### Data layer (FR-D-*)

- **FR-D-001**: System MUST persist historical price bars and
  non-price events in a unified store using a schema keyed by
  `(asset_class, venue, instrument, ts, kind, source)`. The schema
  MUST accommodate at minimum: OHLCV bars, tick prints, corporate
  actions, fundamentals releases, news/event series, macro indicators.
- **FR-D-002**: System MUST track each record's `as_of_ts` (when this
  value was first observed) separately from its content timestamp; a
  later revision of the same `(instrument, ts, kind)` MUST be stored
  alongside the original, never overwriting it. Backtests pin a single
  `as_of_ts` per run for point-in-time correctness.
- **FR-D-003**: System MUST expose a pluggable `IngestionAdapter`
  interface so adding a new vendor or new asset class is one new file
  + one config entry; existing adapters and rules MUST NOT need
  changes.
- **FR-D-004**: System MUST track corporate actions (splits,
  dividends, ticker changes, mergers) with effective dates and apply
  them consistently in every backtest read path; raw bars MUST be
  retrievable both in unadjusted and adjusted forms.
- **FR-D-005**: System MUST detect missing bars across a session and
  surface gaps as a first-class data-quality event; affected backtests
  MUST refuse to run silently across the gap.
- **FR-D-006**: System MUST support a market-calendar abstraction
  that covers (a) discrete-session venues (e.g., NYSE, KRX, LSE), and
  (b) always-open venues (e.g., crypto). The abstraction MUST NOT
  require asset-class branching in higher layers.
- **FR-D-007**: System MUST provide a `data describe` CLI command
  that reports, per `(asset_class, venue, instrument, kind, vendor)`:
  earliest and latest record, gap count, last revision time, and
  vendor count for that key.

#### Backtest engine (FR-B-*)

- **FR-B-001**: System MUST replay strategies (TOML rule files from
  spec 001 *and* programmatic strategy modules) deterministically over
  a chosen historical window. Two runs of the same backtest with the
  same configuration MUST produce byte-identical metrics, order
  sequences, and fills.
- **FR-B-002**: System MUST enforce point-in-time correctness:
  during evaluation at time `t`, no read of any record with content
  timestamp `> t` or with `as_of_ts > t` is permitted. Any such read
  MUST raise `LookaheadError` and abort the run.
- **FR-B-003**: System MUST apply the same risk gates as the live
  router (whitelist, halt flag is irrelevant in backtest, per-trade /
  per-symbol / global caps from `config/caps.toml`). Divergence
  between live and backtest gating is a P0 bug.
- **FR-B-004**: System MUST simulate execution with explicit cost
  components: commission, slippage, market impact, and partial-fill
  participation cap. Each component MUST be configurable per backtest
  run and MUST appear as an itemised line in the report.
- **FR-B-005**: System MUST support time-in-force semantics for
  limit orders (`day`, `gtc`, `ioc`, `fok`) and reflect their cancel /
  expire / fill outcomes in the simulated audit log identically to
  live behaviour.
- **FR-B-006**: System MUST support walk-forward configuration
  (rolling train/test windows with declared step size) and held-out
  out-of-sample windows. The OOS window MUST be unreadable by the
  strategy during in-sample evaluation; this is enforced by the
  point-in-time barrier (FR-B-002).
- **FR-B-007**: System MUST record every backtest run as a directory
  under `data/backtests/<run_id>/` containing: the input rule /
  strategy snapshot, the resolved data slice (vendor + as_of_ts
  pin), the simulated audit log, the cost-itemised order log, the
  computed metrics, and the human-readable report. Run directories
  are append-only (a re-run produces a new run_id; never mutates an
  existing directory).
- **FR-B-008**: System MUST compute, at minimum: total return, CAGR,
  volatility, Sharpe ratio, Sortino, max drawdown, hit rate, average
  win/loss ratio, exposure (% of time invested), turnover (annualised
  notional turnover / capital), gross transaction cost, and per-trade
  P&L distribution.
- **FR-B-009**: System MUST stream historical data so backtests over
  large windows do not require loading the entire window into memory;
  worst-case memory use for a single-instrument multi-year run MUST
  fit on operator hardware (≤ 1 GB resident).

#### Promotion gate (FR-P-*)

- **FR-P-001**: System MUST provide a "promotion seal" — a small
  signed-by-content (e.g., hash-pinned) record stating: rule snapshot
  hash, backtest run_id, OOS metrics, and the threshold set the
  metrics cleared. Promotion seals live under
  `data/promotions/<seal_id>.toml`.
- **FR-P-002**: The live worker (spec 001's `auto-invest run`) MUST
  refuse to load a rule that lacks an attached promotion seal whose
  rule-snapshot hash matches the live rule's content hash; this gate
  applies to both `canary` and `full-live` stages and is bypassable
  only by an explicit `--unsealed-development` flag that is itself
  refused outside dry-run.
- **FR-P-003**: System MUST support a "promotion check" CLI
  (`auto-invest promote --rule <file> --backtest <run_id>`) that
  evaluates the run's OOS metrics against configured thresholds and
  either writes a promotion seal or refuses with a per-threshold
  diff.
- **FR-P-004**: System MUST compute live-vs-backtest divergence
  during operation: for each promoted rule, the daily reporter
  compares the live-session realised P&L distribution against the
  backtest's distribution and surfaces a divergence flag if the live
  shape falls outside a configurable tolerance for a configurable
  duration. This is the first primitive of the self-improving loop.

### Key Entities

- **HistoricalRecord**: a single row in the unified data store, keyed
  by `(asset_class, venue, instrument, ts, kind, source, as_of_ts)`.
  Carries a typed payload — OHLCV, tick, corporate action, fundamentals
  release, news event, macro indicator.
- **IngestionAdapter**: a pluggable component that pulls records from
  a vendor and writes them as `HistoricalRecord`s. Each adapter
  declares: vendor name, supported asset classes, supported kinds,
  rate-limit profile.
- **MarketCalendar**: per-venue session abstraction. Discrete-session
  venues expose open/close timestamps; always-open venues expose
  perpetual sessions. Higher layers consume a uniform interface.
- **CorporateAction**: dated event affecting an instrument's quantity
  / cost basis / identifier. Backtest read paths apply or skip these
  based on the run's adjustment mode.
- **BacktestRun**: an immutable directory under
  `data/backtests/<run_id>/` containing inputs, simulated audit log,
  cost-itemised orders, metrics, report.
- **PromotionSeal**: an immutable record under
  `data/promotions/<seal_id>.toml` linking a rule-snapshot hash to a
  backtest run_id and the OOS thresholds it cleared.
- **DivergenceMetric**: a daily statistic comparing the live realised
  P&L distribution of a promoted rule against the backtest's
  distribution; consumed by the daily report and (later) by the
  self-improving loop.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new ingestion adapter for a new asset class (e.g.,
  crypto bars from a public vendor) can be added in **under 200 LOC**
  and **without modifying** any existing adapter, the data store, or
  the backtest engine.
- **SC-002**: Two consecutive runs of the same backtest with
  identical configuration produce **byte-identical** metrics, order
  log, and audit log files (deterministic replay).
- **SC-003**: Across a 5-year historical window for a single
  US-listed symbol, a backtest run completes in **under 60 seconds**
  on operator hardware and uses **< 1 GB** resident memory.
- **SC-004**: Any strategy that attempts to read post-decision data
  triggers `LookaheadError` and aborts the run with a clear stack
  pointing to the offending read; **zero** look-ahead leaks are
  observed across a synthetic test suite of known-cheating strategies.
- **SC-005**: The risk-gate code path used in the live router and the
  one used in the backtest engine are the **same** code path (single
  source of truth); a CI test confirms the imports.
- **SC-006**: For every promoted rule, the daily report includes a
  live-vs-backtest divergence flag with a configurable threshold;
  the flag fires within **one trading day** of a sustained shape
  divergence.
- **SC-007**: Across any rolling 90-day operating window after this
  spec ships, **zero** rules reach `canary` or `full-live` stage
  without a matching, threshold-clearing promotion seal.
- **SC-008**: An unrecoverable data-quality event (gap, vendor
  disagreement beyond tolerance, retroactive corporate action) blocks
  the affected backtest **before** any metrics are computed; no
  silent skips.
- **SC-009**: Walk-forward and held-out OOS modes are exercised by
  CI with at least one strategy each; per-fold metrics and OOS
  metrics are part of the standard report.

## Assumptions

- The operator continues to be the sole user, owner, and on-call
  responder; no multi-tenant or multi-user concerns enter v2.
- The data store remains local first (SQLite-or-equivalent file under
  `data/`) for v2; cloud-hosted data warehousing is a sibling concern
  for ops hardening (former option C, now spec 006).
- The live router's risk gate code (from spec 001's
  `src/auto_invest/risk/`) is import-compatible with the backtest
  engine; if not, the gate code is refactored under 002 to make this
  true (single source of truth for risk gating is non-negotiable —
  see SC-005).
- Spec 001's TOML rules format is supported as an input to the
  backtest engine without modification. Programmatic strategy modules
  (a sibling concern for spec 003) are also accepted but are not the
  P1 surface for this spec.
- Backtest data licensing: the operator is responsible for ensuring
  vendor-supplied data is licensed for backtest use. The system MUST
  surface vendor + license metadata per record but does not enforce
  licensing.
- Constitution v1.0.0 governs this spec. The "Out of scope (v1.0.0)"
  list (derivatives, leverage, short, options, futures, crypto,
  domestic Korean equities) is a constraint on **trading**, not on
  **data ingestion or backtest**. The data layer and backtest engine
  MUST be designed asset-class agnostic; actual *trading* of those
  asset classes is a future spec, gated by a constitution amendment.
- Any apparent conflict between this spec and the constitution
  resolves in the constitution's favour.

## Out of Scope (v2)

The following are deferred to keep v2 focused:

- **Strategy research framework** — alpha hypotheses, factor models,
  portfolio construction, parameter search procedures. Sibling spec
  003.
- **LLM-assisted judgment** — judgment points, prompts, latency /
  cost budgets. Sibling spec 004.
- **First canary live trade** — actually pushing a sealed strategy
  through the live worker into a small real-money run. Sibling spec
  005.
- **Operational hardening** — cloud deploy, alerting, dashboards,
  SQLite backup. Sibling spec 006.
- **Order-book / L2-L3 microstructure** — v2 supports OHLCV +
  optional tick prints; full L2/L3 simulation is a future extension.
- **Distributed / parallel backtest farm** — v2 runs single-process;
  parameter-grid sweeps may be added later if research demand
  outgrows single-machine throughput.
- **GUI** — backtest reports remain Markdown + JSON; visualisation
  notebooks are operator-side.

## Open Decisions

The following are flagged for resolution at `/speckit-plan` (Phase 0
research):

- **OD-1 — Vendor for the second ingestion adapter (proof of
  multi-asset / multi-vendor design)**: candidates include a public
  crypto-bar API (no auth, easy to wire) or a free FX bar source.
  Decision deferred to research; default if undecided is a public
  crypto-bar API because it also exercises the always-open calendar
  path.
- **OD-2 — Slippage / market-impact default model**: simplest
  defensible default is half-spread + a square-root impact term keyed
  on (order size / bar volume). Decision deferred to research; an
  alternative is a fixed-bps model for v2 with the impact curve added
  in a later iteration.
- **OD-3 — OOS reservation default size**: candidate defaults are
  20% of the window or "last 6 months", whichever is larger.
  Decision deferred to research.
- **OD-4 — Promotion threshold defaults**: e.g., minimum OOS Sharpe,
  maximum OOS drawdown, minimum trade count. Decision deferred to
  research; conservative defaults will be set such that no current
  hand-written rule from spec 001 trivially passes — promotion must
  be earned.
- **OD-5 — Storage backend for the unified data store**: extend the
  existing SQLite database (`data/auto_invest.db`) with new tables, or
  create a separate Parquet-on-disk store optimised for time-series
  scans? Decision deferred to research; default is "extend SQLite for
  v2, design tables to migrate to Parquet later without schema
  rewrite."
- **OD-6 — Backtest CLI surface**: how much of the configuration
  lives in CLI flags vs a backtest TOML config file? Decision
  deferred to research; default is "CLI flag for one-off runs, TOML
  config for reproducible / CI runs".

These will be resolved in `research.md` during `/speckit-plan` and
folded into the FRs above before tasks are generated.
