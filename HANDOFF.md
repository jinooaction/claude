# auto-invest — Next-Session Handoff

This file is the entry point for **the next Claude session** working on
this repository. It summarises what's done, where to read, and the
direction that has been chosen for the next milestones.

## North star (operator-set, 2026-05-06)

> **Goal**: build and operate a **world-class, self-improving automated
> investment service**. Investment scope is **not limited to US
> equities** — every domain that can be automated by a system is in
> scope (other equity markets, FX, crypto, derivatives where legal,
> rates, commodities, etc.).
>
> Until that goal is met, "v1 ships" is not the same as "we are done".
> v1 is a safe **execution shell**, not a strategy and not a research
> platform. The next specs exist to close that gap.

This north star is also captured in `CLAUDE.md` and is binding on every
future spec.

## Status as of last commit on `main`

* **Spec 001 (automated US-equity trading MVP)** — fully implemented
  and validated end-to-end as a *rule execution shell*.
* **Test count (`main`)**: 256 passing + 1 skipped (live KIS smoke is
  gated by `KIS_LIVE_TEST=1`).
* **Live broker validation**: operator (mason) ran
  `scripts/live_smoke.py` against their real KIS account on
  2026-05-04; returned a real-time AAPL quote (`$279.4475`). The
  KIS overseas-equity adapter is verified against production.
* **Constitution v1.0.0** — all eight principles satisfied for v1.

## Status as of last commit on `claude/investment-automation-setup-8KPrZ`

Spec 002 (data infra + backtest engine) is **31/65 tasks
implemented** through Phase 3:

| Phase | Tasks | Status |
|---|---|---|
| 1 — Setup | T001-T006 | ✅ shipped |
| 2 — Foundational | T007-T021 | ✅ shipped |
| 3 — US1 backtest MVP | T022-T031 | ✅ shipped |
| 4 — US2 point-in-time + cost realism | T032-T038 | ⬜ next |
| 5 — US3 multi-source ingestion | T039-T046 | ⬜ |
| 6 — US4 walk-forward + OOS | T047-T052 | ⬜ |
| 7 — US5 promotion seal | T053-T060 | ⬜ |
| 8 — Polish | T061-T065 | ⬜ |

Test count on the branch: **293 passing + 2 skipped**
(256 spec 001 baseline + 37 spec 002 unit/integration tests).

**Working end-to-end command**:

```bash
uv run auto-invest backtest \
    --rule tests/fixtures/rules/aapl_rsi_demo.toml \
    --from 2024-01-01 --to 2025-12-31 \
    --vendor kis --capital 10000
```

This produces `data/backtests/<run_id>/{report.md, metrics.json,
audit_log.jsonl, orders.jsonl, inputs/{run.toml, rule_snapshot.toml,
data_pin.json}}`. Re-running the command is idempotent (same run_id,
byte-identical artifacts).

### ⚠️ Trustworthiness caveat (binding on the next session)

The Phase 3 backtest is **not yet trustworthy as a basis for
promotion**. `report.md` itself states this. Specifically still
missing:

- No lookahead barrier at the data-read layer (T032). A buggy
  strategy that indexes `bars[t+1]` is not caught.
- No square-root market impact term and no participation cap
  (T035). Cost is currently commission + half-spread only.
- No time-in-force semantics for limit orders (T036). The
  Phase 3 fill rule is "fill iff limit price is in `[bar.low,
  bar.high]`", which approximates `day` but does not model
  `gtc/ioc/fok`.
- No corporate-action application during replay (T037). Splits
  and dividends inside the window are not yet folded into
  position quantity / cost basis.
- No live-router-vs-backtest-router parity test (T038). The
  refactor for SC-005 already happened in T020 (single
  `risk/chain.py`); the test that pins it is in Phase 4.

**Phase 4 closes all five gaps**. Until Phase 4 lands, no rule
should reach `canary` or `full-live` stage even if a `--unsealed-
development` escape exists.

## Reading order for the next session

Read in this exact order before doing anything new:

1. `.specify/memory/constitution.md`
2. `CLAUDE.md` (north star + active spec pointer + active plan)
3. `HANDOFF.md` (this file — pay attention to "Phase 4 kickoff" below)
4. `specs/002-data-and-backtest/spec.md` (US2 specifically)
5. `specs/002-data-and-backtest/plan.md`
6. `specs/002-data-and-backtest/research.md` (R-2 cost model)
7. `specs/002-data-and-backtest/data-model.md`
8. `specs/002-data-and-backtest/contracts/`
9. `specs/002-data-and-backtest/tasks.md` (Phase 4 = T032-T038)
10. Trustworthiness caveat above

For historical context on the shipped execution shell, also see
`specs/001-automated-trading-mvp/`.

## Phase 4 kickoff (next session, start here)

Phase 4 implements **US2 — point-in-time correctness + cost
realism**. The seven tasks:

1. **T032** — Define `LookaheadError` in
   `src/auto_invest/backtest/engine.py`. Replace the engine's
   direct `iter_bars(...)` consumption with a `BarWindow` context
   object that wraps the iterator: every read the strategy makes
   goes through `BarWindow.__getitem__` / iteration, which enforces
   `bar.as_of_ts <= as_of_ts_pin` AND `bar.bar_open_ts <=
   current_decision_ts`. Any violation raises `LookaheadError` and
   the engine writes `result_status="aborted_lookahead"` to
   `backtest_runs` and returns exit code 3.
   - File: `src/auto_invest/backtest/engine.py` (extend, don't
     rewrite — the Phase 3 loop body is the right shape).
   - Be careful: spec 001's `strategy/triggers.py` evaluates the
     trigger on a `tuple[PriceBar, ...]` slice that the engine
     builds from past bars only. The current implementation slices
     `bars_window` correctly but the *contract* with the strategy
     is not enforced. T032 makes the contract enforceable.

2. **T033** — Integration test in
   `tests/integration/backtest/test_lookahead_barrier.py`. Build a
   strategy module (or a TOML rule referencing a stub indicator)
   that *intentionally* indexes one bar past the decision time.
   Assert the run aborts with `LookaheadError`, exit code 3,
   `result_status="aborted_lookahead"`.

3. **T034** — Unit test
   `tests/unit/backtest/test_revisions_pin.py`. Already mostly
   covered by `tests/unit/market_data/test_revisions.py::test_pin_returns_only_revisions_at_or_before_pin`
   — verify, expand only if needed.

4. **T035** — Extend `src/auto_invest/backtest/cost_model.py`
   with the square-root impact term:
   `impact_usd = impact_coeff × σ × sqrt(qty / bar_volume) × notional`
   where `σ = (bar.high - bar.low) / bar.close`. Apply the
   participation cap: clamp the fill quantity at
   `participation_cap_pct% × bar.volume`. Update the unit tests
   in `tests/unit/backtest/test_cost_model.py` (does not exist yet
   — create it).

5. **T036** — Implement TIF semantics in
   `src/auto_invest/execution/backtest_broker.py::simulate_fill`.
   `day` cancels at the next bar's open if unfilled; `gtc` carries
   over; `ioc` cancels immediately if not fully filled; `fok` is
   all-or-nothing. The Phase 3 implementation is "fill iff in
   range", which approximates `day` only. Tests in
   `tests/unit/execution/test_backtest_broker_tif.py`.

6. **T037** — Wire corporate-action application in
   `engine.py`: between bars, consult
   `revisions.iter_corporate_actions` for the instrument; on a
   split, scale the position quantity and divide the cost basis;
   on a cash dividend, add to cash. Synthetic 2-for-1 split
   fixture in
   `tests/integration/backtest/test_corporate_actions.py`.

7. **T038** — Parity test
   `tests/unit/backtest/test_risk_gate_parity.py`: import
   `risk/chain.py` from both `execution/order_router.py` (live)
   and `execution/backtest_broker.py` (simulated); assert they
   reference the **same module objects** (single source of
   truth — SC-005). T020 already did the refactor; this test
   pins it against future drift.

**Phase 4 entry criteria** (all currently met on the branch):
- 0002 migration applied; new tables in place.
- BacktestConfig + CostModel + WalkForwardConfig + OOSWindowConfig
  models present in `src/auto_invest/config/backtest.py`.
- `revisions.iter_bars` already enforces `as_of_ts <=
  as_of_ts_pin` at the SQL level (T017). T032 lifts this barrier
  one level higher to also catch *content-time* lookahead.

**Phase 4 exit criteria**:
- A synthetic cheating strategy raises `LookaheadError` and aborts
  the run.
- A market order fills with itemised commission / half-spread /
  impact rows in `orders.jsonl`.
- A 2-for-1 split inside a backtest window is correctly applied to
  position quantity / cost basis without operator intervention.
- All 293 existing tests still pass; new Phase 4 tests added.
- `report.md`'s trustworthiness caveat is updated to reflect that
  the report is now trustworthy enough for promotion (Phase 7 then
  layers the actual seal mechanism on top).

## How to start the next session

> Read `.specify/memory/constitution.md`, `CLAUDE.md`, `HANDOFF.md`
> (specifically the Phase 4 kickoff section), and the spec/plan/
> tasks under `specs/002-data-and-backtest/`. The roadmap is locked
> in: implement Phase 4 (T032-T038) on the existing branch
> `claude/investment-automation-setup-8KPrZ`. Commit per task or per
> coherent group; push at phase boundary.

## What NOT to do in the next session

- Do **not** modify any spec 001 file beyond what spec 002's plan
  already permits. The only spec 001 surface intentionally
  rewritten in spec 002 is `worker/schedule.py` (now a thin facade
  over `market_data/calendar.py`'s NYSE calendar — zero behaviour
  change, all 16 spec 001 schedule tests pass unchanged).
- Do **not** invent a feature without writing a spec first. SDD
  discipline is the project's working agreement.
- Do **not** push KIS credentials anywhere. They live only in the
  operator's local `.env`.
- Do **not** push to `main` without operator permission. Spec 002
  ships via PR after Phase 4 (or later) is reviewed.
- Do **not** mark a rule promoted (spec 005) before Phase 4 lands.
  The Phase 3 backtest is by design not trustworthy yet.
- Do **not** start Phase 5 (multi-source ingestion) before Phase 4.
  US3 inherits the engine's read-path; if the lookahead barrier is
  not in place, every new adapter inherits the same gap.

## Quick state summary table

| What | State |
|------|-------|
| Constitution | v1.0.0 ratified; multi-asset amendment pending (will land alongside the first non-US-equity trading spec) |
| Spec 001 | shipped to `main`, 256/256 tests, live broker verified |
| Spec 002 | drafted; Phase 1-3 (31/65 tasks) shipped on `claude/investment-automation-setup-8KPrZ`; Phase 4 next |
| Operator local env | working `uv` venv, working `gh` auth, KIS keys in `.env` (operator's machine only) |
| Active branch | `claude/investment-automation-setup-8KPrZ` |
| North star | world-class, self-improving, multi-domain automated investment service |
