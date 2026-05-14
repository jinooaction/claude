# Spec 008 Backtest Engine — Merged to Main

**Read this if you're touching the backtest engine.** Spec 008 is now part of `main`; this file is the historical record of how it shipped.

> **2026-05-14 — PR #4 MERGED to `main` as `7f8fb99`** via the IX.D
> autonomous-merge channel. Spec 008 is complete and live on main:
> 41/41 tasks, **494 passed / 1 skipped, lint clean**. Pre-merge tests
> + lint re-run on head `38c77ce` immediately before invoking
> `mcp__github__merge_pull_request` (IX.D rule 4). Merge method was
> `merge` so every implementation commit hash (962ae77 → 38c77ce)
> survives in `git log` for forensic queries; no Kernel-touch commit
> was in this PR's diff (the only K4 touch, `bc47361`, was already on
> main via PR #1).
>
> Spec 007 (hardened canary) is now structurally unblocked — it has
> a deterministic backtest artefact (`backtest-run.json` + `metrics.csv`
> + `per-rule/*.json` + `summary.md`, FR-B15 byte-identical) to diff
> baseline vs candidate against.
>
> Quickstart smoke (T041, AAPL fixture, 30 sessions, single
> `buy_aapl_dip` rule with per_symbol_cap=10%):
> `run_id = 3482fad709f34a7fb60826f8d117d175`. Artefact tree matched
> `data-model.md § On-disk per-run layout` verbatim. 6 orders, 2 fills,
> 4 per_symbol_cap_gate rejections, aggregate sharpe 0.500286.

> **2026-05-14 earlier — PR #1 + PR #2 both merged.**
> - **PR #1** (`5b9d001`): spec 008 mid-flight (15/41 tasks) + autonomous-workflow + autonomous-merge policy → `main`.
> - **PR #2** (`f849fab`): constitution **v2.0.0 → v3.0.0** — IX.B-1/B-4 repealed, IX.B-2 reclassified as production-deploy gate, IX.D Operator Autonomy Supremacy added. K-meta touch — `git log --grep="this changes the safety perimeter"` will find it.
> - Net effect for future sessions: **no merge-stage gate**; the production-deploy gate (spec 007 hardened canary, when shipped) is the only structural safety boundary between merged code and live trading. Trading-safety invariants (I-VII, VIII.A) preserved.

## Session-start discovery recipe (NEW — mandated by CLAUDE.md)

Every fresh session MUST run this BEFORE deciding what to do:

```bash
# 1. See every claude/* branch on origin.
git fetch origin
git ls-remote --heads origin 'claude/*' | awk '{print $2}'

# 2. List open PRs (the true source of truth for in-flight work).
#    Use mcp__github__list_pull_requests owner=jinooaction repo=claude state=open

# 3. Checkout the in-flight branch if one exists; do NOT create a new branch off main.
git checkout claude/continue-work-ID7Ec
git pull --ff-only
```

## TL;DR

- Spec 008 (Backtest Engine) is **15 / 41 tasks done** and pushed.
- **Phase 1 (Setup), Phase 2 (Foundational + K4 commit), and the first 4 of 17 US1 tasks** are complete.
- All shipped tests pass: **363 passed, 1 skipped** (was 319+1 on `main`; +44 new tests).
- Lint clean.
- The K4 commit (`bc47361`) was a Kernel touch — already merged to `main` via PR #1 on 2026-05-14. Under constitution v3.0.0 (live as of `f849fab`), Kernel touches no longer block merge; they're logged for forensic attention. `git log --grep="K4"` finds the commit.

## What's done

| Task | Status | Commit |
|------|--------|--------|
| T001 backtest/ skeleton | ✓ | `13004df` |
| T002 deps verify (no new deps) | ✓ | `13004df` |
| T003 config/synthetic_shocks.toml placeholder | ✓ | `13004df` |
| **T004+T005 K4 — audit.py event-type Union extension** | ✓ | **`bc47361` (operator review)** |
| T006 backtest/data_model.py | ✓ | `454a624` |
| T007 backtest/clock.py (ReplayClock + WallClockGuard) | ✓ | `454a624` |
| T008 test_backtest_clock_guard.py (8 tests) | ✓ | `454a624` |
| T009 test_backtest_data_model.py (9 tests) | ✓ | `454a624` |
| T010 backtest/kernel_pre_flight.py | ✓ | `454a624` |
| T011 test_backtest_kernel_guard.py (6 tests) | ✓ | `454a624` |
| T012 backtest/data_source.py (Protocol + CSVDataSource) | ✓ | `e4c3eee` |
| T013 backtest/ingest.py (CSV → SQLite) | ✓ | `e4c3eee` |
| T014 test_backtest_csv_ingest.py (13 tests) | ✓ | `e4c3eee` |
| T015 test_backtest_data_source.py (8 tests) | ✓ | `e4c3eee` |

## What's left — 26 tasks across Phases 3-6

The dependency-ordered plan is in `specs/008-backtest-engine/tasks.md`. Pick up at **T016**.

### Phase 3 US1 — execution layer (T016-T020)

- **T016** `backtest/broker_mock.py` — `BacktestBroker(adapter_id="backtest-mock-v1")` with `submit_order` / `cancel_order` / `list_open_orders`. Pessimistic zero-slippage fill per R-B3: BUY fills at `min(limit, bar.open)` iff `bar.low ≤ limit AND bar.volume ≥ order.qty`; SELL symmetric. No partial fills. `DAY` + `GTC` time-in-force.
- **T017** `test_backtest_fill_model.py` — exhaustive R-B3 coverage (BUY/SELL × touched/untouched × volume-ok/short).
- **T018** `test_backtest_broker_mock.py` — `adapter_id` invariant; live-broker detection.
- **T019** `backtest/judgment_stub.py` — `JudgmentStub.decide(decision_class, inputs)` emits `LLM_CALL_STUBBED` (input hashed via canonical-JSON SHA-256). Raises `BacktestJudgmentLeakError` when `BACKTEST_MODE=1` AND an `AnthropicClient` is constructed.
- **T020** `test_backtest_judgment_stub.py` — stub emits one `LLM_CALL_STUBBED` per call; leak detection.

### Phase 3 US1 — engine (T021-T025)

- **T021** `backtest/metrics.py` — `total_return_pct`, `max_drawdown_pct`, `sharpe_ratio` (annualised √252, RFR 0). numpy/pandas only. Returns canonicalised `Decimal`.
- **T022** `test_backtest_metrics.py` — known series → expected values.
- **T023** `backtest/replay.py` — **DESIGN DECISION REQUIRED**. The spec's FR-B01 says "reuses `Worker.tick` unmodified". Two viable paths:
  - **Path A (faithful)**: Construct a fake `ResilientClient` and full `Worker` and call `Worker.tick(now=clock.now())` per bar. Requires shimming `market_data/feed.py` quote source to return the next bar's data; requires the broker mock to satisfy the `ResilientClient` interface. Heavier wiring.
  - **Path B (slim)**: Directly invoke `risk/gates.py` + `strategy/triggers.py` + `OrderRouter` in a thin per-bar loop, BYPASSING the async `Worker.tick` shell. Reuses the same safety code (gates, whitelist, audit) but not the async lifecycle. Simpler.
  Recommend **Path B**: the safety surface is identical (same gate code, same audit code, same whitelist); the async lifecycle is irrelevant for offline replay. Document the choice in plan.md or research.md as R-B13.
- **T024** `backtest/report.py` — write `backtest-run.json`, `metrics.csv`, `per-rule/<rule_id>/{orders,fills,gate-rejections}.json`. Stable sort by ts ASC then insertion order. chmod-readonly on POSIX at completion.
- **T025** `backtest/run.py` — orchestration: kernel_pre_flight → wall_clock_guard → BACKTEST_STARTED → replay → report → BACKTEST_COMPLETED. All error branches set correct exit codes (77/78/79/80/81) and still attempt to write `backtest-run.json` for forensics.

### Phase 3 US1 — CLI (T026-T028)

- **T026** Wire `auto-invest backtest` + `auto-invest ingest-history` in `src/auto_invest/cli.py`. Stdout first+last line = `backtest run_id: <hex>`. Exit codes per `contracts/backtest-cli.md`.
- **T027** Filter `BACKTEST_*` + `LLM_CALL_STUBBED` from live observability — one-line WHERE clause add in `reports/daily.py` and `cli.py` status path.
- **T028** `tests/integration/test_backtest_end_to_end.py` — fixture: one rule × one symbol × 30 days; run end-to-end; assert artefact tree + no live-broker leak.

### Phase 4 US2 — synthetic-shock (T029-T034)

- **T029** `backtest/synthetic_shocks.py` — load `config/synthetic_shocks.toml`; resolve `most_recent_quarterly_opex` using XNYS calendar (third Friday of Mar/Jun/Sep/Dec on or before today).
- **T030** Populate `config/synthetic_shocks.toml` (already mostly populated by T003; just confirm the DYNAMIC entry resolves correctly).
- **T031** `test_backtest_synthetic_shocks.py` — date resolution + config loader.
- **T032** `--synthetic-shock` CLI mode — per-day artefacts under `per-rule/<rule_id>/by-date/<date>/`.
- **T033** `test_backtest_synthetic_shock_2020_03_12.py` — SC-B04 gate-trip sanity (≥1 `ORDER_REJECTED_BY_GATE` with loose ruleset).
- **T034** `test_backtest_determinism.py` — FR-B15 byte-identical re-run.

### Phase 5 US3 — summary.md (T035-T036)

- **T035** Extend `report.py` to render `summary.md` (operator one-page block); identical content to stdout.
- **T036** `test_backtest_summary_render.py`.

### Phase 6 Polish (T037-T041)

- **T037** README.md paragraph + link to `specs/008-backtest-engine/quickstart.md`.
- **T038** `uv run ruff check src tests`.
- **T039** `uv run pytest` — confirm 363+new == expected total.
- **T040** Import smoke: `python -c "from auto_invest.backtest import ..."`.
- **T041** Run `quickstart.md` end-to-end on a tiny fixture; record `run_id` in this file.

## Quickstart to resume

```bash
# verify state matches
git fetch origin
git checkout claude/continue-work-ID7Ec
git pull --ff-only
git log -1 --oneline   # expect e4c3eee feat(008): T012-T015 ...

# verify tests + lint
uv run pytest -q                            # expect 363 passed, 1 skipped
uv run ruff check src tests                  # expect All checks passed!

# active feature pointer
cat .specify/feature.json                    # expect specs/008-backtest-engine

# what's left
grep "^- \[ \]" specs/008-backtest-engine/tasks.md | wc -l   # expect 26
```

## Constitutional / safety reminders for the next session

- **K4 is closed.** Do NOT modify `src/auto_invest/persistence/audit.py` again. All new event types are already in `bc47361`. Reasoning: adding a NEW event type would be a SECOND K4 touch with no operator review.
- **No other Kernel touch is permitted.** Every remaining task ships inside `src/auto_invest/backtest/` or under `tests/` or as a one-line filter in `reports/daily.py` and `cli.py`. The `reports/daily.py` change is NOT a Kernel file (K4 only covers `audit.py`, `migrations/0001_initial.sql`, `migrations/0002_token_usage.sql`).
- **No real broker / no real LLM.** T016-T020 enforce these as hard fails. Defense-in-depth runs end-to-end through to T028's integration test.
- **Determinism is non-negotiable.** T034 is the gatekeeper; if it fails, the offending non-determinism MUST be fixed before declaring US2 complete.
- **Path A vs Path B for T023:** the spec says "reuses Worker.tick"; if you go with Path B (recommended), document the deviation as a new research entry R-B13 in `specs/008-backtest-engine/research.md` so the spec author's intent is preserved in the trail.

## Quick state summary table

| Item | State |
|------|-------|
| Branch | `claude/continue-work-ID7Ec` pushed to origin |
| Last commit | `e4c3eee feat(008): T012-T015 US1 data layer` |
| K4 commit (operator review point) | `bc47361 feat(008): K4 — append BACKTEST_* + LLM_CALL_STUBBED ...` |
| Constitution | v2.0.0 |
| Tests | 363 passing, 1 skipped |
| Lint | clean |
| Active feature pointer | `specs/008-backtest-engine` |
| Tasks done | 15 / 41 (Phases 1, 2 fully; 4 / 17 US1) |
| Tasks remaining | 26 (13 US1 + 6 US2 + 2 US3 + 5 Polish) |
| K4 touch budget remaining | **0** — do not modify any kernel.toml path |
| Estimated session count to finish | 1-2 more sessions if /speckit-implement is resumed |

## First message to send to the next session (copy-paste ready)

```
Run the session-start discovery sequence in CLAUDE.md (git ls-remote +
mcp__github__list_pull_requests). You will find PR #1 with
head=claude/continue-work-ID7Ec. git checkout that branch, git pull,
then read HANDOFF-008.md and specs/008-backtest-engine/{spec,plan,
research,data-model,tasks}.md.

Resume /speckit-implement at T016. Pick Path B for T023 (slim replay
loop using gates+triggers+OrderRouter directly, not the full async
Worker.tick) and document this as R-B13 in research.md before writing
replay.py. Use SPECIFY_FEATURE=008-backtest-engine for spec-kit scripts.
Do NOT modify any path in .specify/memory/kernel.toml — K4 is closed;
the audit.py extension already shipped in bc47361.

Verify state first: git log -1 should be the latest commit on
claude/continue-work-ID7Ec; pytest should show 363 passed, 1 skipped.
```
