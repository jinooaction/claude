# Branch Handoff — spec 008 (backtest engine), Increment 2 entry point

**Branch**: `claude/review-docs-sdd-cycle-SbbBy`
**Last commit**: `3828f5d feat(008): Increment 1 — Phase 1+2 (one-time K-meta human-merge change set)`
**Status**: clean working tree, pushed to origin.
**Constitution**: v2.0.0 (Kernel + principle IX). Spec 008 added a new Kernel group `[K7_named_datasets]` to `kernel.toml` in Increment 1.

> **Read this first if you are the next session resuming this branch.**
> `HANDOFF.md` and `HANDOFF-002-003.md` describe the main-line baseline.
> This file is the spec-008-specific resume point.

---

## TL;DR for the next session

1. Read `.specify/memory/constitution.md` (v2.0.0).
2. Read `.specify/memory/kernel.toml` (now contains **K1–K7 + K-meta**; K7 is new this branch).
3. Read this file.
4. Read `specs/008-backtest-engine/tasks.md` — T001–T015 are `[x]`, T016 onwards is what's left.
5. Continue at **T016** (Phase 3, first US1 test) and proceed through Phase 7.

The first message to send to the next session is at the bottom of this file. Copy-paste ready.

---

## What landed in this branch already

Eight commits, in order:

```text
48c9801 docs(008): /speckit-specify        backtest engine spec drafted
cccf7ab docs(008): /speckit-clarify Q1     OHLCV vendor (yfinance + KIS historical)
2630f97 docs(008): /speckit-clarify Q2-Q5  fill model, migration policy, thresholds, OPEX freeze
2abeb4b docs(008): /speckit-plan           plan + research (R-1..R-12) + data-model + 5 contracts + quickstart
b30c2d9 docs(008): /speckit-tasks          67 tasks across 7 phases (US1-US4)
30b8f79 docs(008): /speckit-analyze        C1 (HIGH) + M1/M2/M3 (MEDIUM) remediation; now 70 tasks
aa5b1de chore:    ruff format pass         pure-whitespace reflow on telemetry/deploy/test files
3828f5d feat(008): Increment 1             Phase 1+2 — the one-time K-meta human-merge change set
```

Spec docs are complete and the engine's **foundation** is on disk:

| Spec artifact | Status |
|---------------|--------|
| `specs/008-backtest-engine/spec.md` | clarified (5 answers integrated) |
| `specs/008-backtest-engine/plan.md` | Constitution Check I–IX pass; K-meta one-time event documented |
| `specs/008-backtest-engine/research.md` | R-1..R-12 decisions frozen |
| `specs/008-backtest-engine/data-model.md` | in-memory + on-disk + SQLite schemas |
| `specs/008-backtest-engine/contracts/` | cli, ohlcv-adapter, named-dataset, run-artifact, audit-events |
| `specs/008-backtest-engine/quickstart.md` | 5-step operator path |
| `specs/008-backtest-engine/tasks.md` | 70 tasks; **T001–T015 are `[x]`** |
| `specs/008-backtest-engine/checklists/requirements.md` | all ✓ |

Code already on this branch (all spec-008 Increment 1):

| File | Status |
|------|--------|
| `src/auto_invest/persistence/audit.py` | `EventType` += BACKTEST_STARTED/COMPLETED/FAILED + three payload classes. K4 file (touched once). |
| `src/auto_invest/persistence/migrations/0003_backtest_events.sql` | new partial index for SC-B06; **no column changes**. Added to K4 in kernel.toml. |
| `.specify/memory/kernel.toml` | K4 += 0003 path; **new group `[K7_named_datasets]`** containing `data/ohlcv/datasets/synthetic_shock_v1.json`. |
| `src/auto_invest/worker/loop.py` | two optional kwargs added to `Worker.__init__` — `quote_provider` and `clock`. Both default `None`; live behaviour byte-identical (verified). NOT a Kernel file. |
| `src/auto_invest/backtest/` | new subpackage: `errors.py`, `clock.py`, `verdict.py`, `config.py`, `hashing.py`, `ohlcv/canonical.py`. All non-Kernel. |
| `tests/backtest/test_foundational.py` | 10 tests, all passing. |
| `pyproject.toml` + `uv.lock` | yfinance>=0.2, hypothesis>=6.0; `nightly` pytest marker. |
| `.gitignore` | negation rules for `data/ohlcv/datasets/` (so the K7 JSON is versioned). |

Tests: **329 passing, 1 skipped (live KIS).** Baseline before spec 008 was 319 passing; +10 new from `test_foundational.py`; zero regressions.

---

## What is left — three increments mapped to PRs

**Increment 2 — Phases 3+4+5+6 = T016..T059 (44 tasks). NON-Kernel. ONE PR, optionally split by user story.**

| Phase | Tasks | Story | What ships |
|-------|-------|-------|------------|
| Phase 3 | T016–T023 (8) | US1 | synthetic-shock replay mode + engine kernel-touch self-check + `synthetic_shock_v1.json` frozen file. Hard prerequisite for spec 007. |
| Phase 4 | T024–T045 (22) | US2 | OHLCV adapters (yfinance + KIS historical) + canonical cache + hybrid fill model + portfolio ledger + BacktestBroker + engine main loop + report + verdict + manifest + CLI. The bulk of the engine. |
| Phase 5 | T046–T052 (7) | US3 | `_emit_started/_completed/_failed` wired; FR-B16 invariant tests (every started run has exactly one matching `COMPLETED` or `FAILED`). |
| Phase 6 | T053–T059 (7) | US4 | on-disk artifact dir (5 files) atomic write + byte-identity tests + stale tmp cleanup. |

**Increment 3 — Phase 7 = T060..T067 + the three analyze-boost tasks T068, T069, T070 (11 tasks). NON-Kernel. One PR.**

- T060: hypothesis property fuzz (≥10 000 nightly examples)
- T061: public API surface (`run_backtest` exported)
- T062: quickstart end-to-end verification
- T063: README "Backtest engine (spec 008)" section
- T064: HANDOFF amendments
- T065: ruff clean
- T066: full pytest pass
- T067: kernel-touch spot check (`git diff main..HEAD -- kernel.toml` must be empty in this increment)
- T068: SC-B05 30 s wall-clock assertion (folded into T018)
- T069: cross-cutting no-network-during-replay test
- T070: SC-B04 fault matrix (6 injected faults)

Naive task count is 70 in `tasks.md`; with 15 done, **55 tasks remain**.

---

## How to resume — exact first commands

```bash
# Land on the right branch.
git fetch origin
git checkout claude/review-docs-sdd-cycle-SbbBy
git pull --ff-only

# Verify the foundation is intact.
git log -1 --oneline   # expect: 3828f5d feat(008): Increment 1 ...
uv sync
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q       # expect: 329 passed, 1 skipped

# Verify the Kernel manifest contains the new K7 group + 0003 migration.
uv run python -c "
import tomllib
m = tomllib.loads(open('.specify/memory/kernel.toml').read())
assert 'src/auto_invest/persistence/migrations/0003_backtest_events.sql' \
    in m['K4_append_only_audit']['files']
assert 'K7_named_datasets' in m
assert 'data/ohlcv/datasets/synthetic_shock_v1.json' \
    in m['K7_named_datasets']['files']
print('K4+K7 manifest OK')"
```

Once those four checks succeed, start at **T016**.

---

## Implementation discipline for Increment 2 (cannot be repeated enough)

The Phase 2 K-meta touch is **already done**. From here on:

1. **NO file under `.specify/memory/kernel.toml` may appear in any commit's diff.**
   - K1: `src/auto_invest/risk/gates.py`, `risk/__init__.py`, `config/caps.py`
   - K2: `src/auto_invest/config/whitelist.py`
   - K3: `src/auto_invest/telemetry/meter.py`, `telemetry/store.py`
   - K4: `src/auto_invest/persistence/audit.py`, `migrations/0001_initial.sql`, `migrations/0002_token_usage.sql`, `migrations/0003_backtest_events.sql`
   - K5: `src/auto_invest/logging_config.py`, `config/loader.py`
   - K6: `src/auto_invest/worker/schedule.py`
   - K7: `data/ohlcv/datasets/synthetic_shock_v1.json` ← will be **created** in T020 and is the only spec-008 file you create directly into the Kernel boundary. After T020, do not touch this file again in non-K change sets.
   - K-meta: `.specify/memory/constitution.md`, `kernel.toml`

   Easy spot-check before any commit:
   ```bash
   git diff --staged --name-only | grep -E '\.specify/memory/kernel\.toml|src/auto_invest/(risk/gates|risk/__init__|config/(caps|whitelist|loader)|telemetry/(meter|store)|persistence/(audit|migrations/000[1-3])|logging_config|worker/schedule)\.(py|sql)|data/ohlcv/datasets/synthetic_shock_v1\.json|\.specify/memory/constitution\.md' \
     ; echo "(must be empty unless this is a K-meta-style PR)"
   ```

2. **Tests written first.** Each phase's `### Tests for ...` section in `tasks.md` is the first batch in that phase. Verify red, then go green.

3. **Live behaviour stays byte-identical.** The two `Worker.__init__` kwargs default to `None`. Any spec-008 work must NOT change live default behaviour. The foundational test (`test_worker_kwargs_default_to_none_preserve_live_behaviour`) is the canary.

4. **Determinism is a hard contract (FR-B12).** Anything you add that ingests time, randomness, dict-ordering, or float arithmetic must surface through the six-hash determinism floor in `auto_invest.backtest.hashing` (research R-5).

5. **Market-hours discipline.** Engine *code* changes are still subject to constitution VIII.A — do code changes off-hours. *Running* a backtest does not affect the live worker; that part is safe at any hour.

6. **Append-only audit.** The engine never UPDATEs or DELETEs `audit_log`. The 0001 trigger enforces this, but spec 008 also adds an explicit unit test in Phase 5 (T048).

---

## Risks / gotchas the next session should know about

- **Worker.tick + indicator priming.** Live `Worker._evaluate_and_route` calls `store_synthetic_bar` and `get_bars` to feed indicators. The synthetic-shock replay (T022) must prime indicator state silently for `warmup_bars` bars *before* the shock day. The current `_evaluate_and_route` happily does this if you simply call `tick(now=...)` for each warmup bar — but you'll need to suppress order routing in the warmup window. Cleanest path: the BacktestBroker (T040) is constructed but ignores all `submit_order` calls during warmup; flip on at first non-warmup tick.
- **CLI is `typer`, not `click`.** Plan + contracts say "click" in one or two places. The repo's existing CLI uses typer; T045 must use typer for consistency. Treat the plan-text as historical drift; do not introduce a second CLI library.
- **yfinance is flaky against Yahoo.** Adapter must implement tenacity retry + a circuit breaker (T035). Tests must use `respx` to mock; never hit live Yahoo in CI.
- **KIS historical adapter and credentials.** T036 reuses `auto_invest.broker.auth`. CI tests mock the endpoint with `respx`; never use real KIS keys in tests. Constitution V binds.
- **partial index naming.** `idx_audit_log_backtest_events` is the index that 0003 creates; T049's `EXPLAIN QUERY PLAN` test must accept either that name OR the existing `idx_audit_log_event_ts` (the pre-existing index on `(event_type, ts_utc)`). The foundational test already takes the OR branch — keep it that way.
- **schema_version: 1** on every on-disk artifact JSON. Bumping is a breaking change for spec 007's harness. Don't bump in Increment 2.
- **The `Decimal` type.** Prices are `Decimal`, not `float`. The canonical row, fills, and report use Decimal throughout. Avoid float-Decimal mixing; mixed arithmetic raises `TypeError` in CPython under strict contexts.

---

## What NOT to do

- Do **not** push to `main`. PR review by the operator.
- Do **not** modify any Kernel file (see list above) outside of intentional K-meta PRs.
- Do **not** touch `worker/schedule.py` (K6) to "make the session check skip during replay" — pass a synthetic `now` instead.
- Do **not** introduce a parallel audit log; new `BACKTEST_*` rows go through `auto_invest.persistence.audit.append`.
- Do **not** add live-network calls inside the replay loop (FR-B09). Cache-first ingest before `BACKTEST_STARTED`.
- Do **not** modify `synthetic_shock_v1.json` once created in T020. Adding/removing a date is L4 (operator-only).
- Do **not** push during US regular hours (constitution VIII.A applies to deploys; code commits to a feature branch are technically OK, but the operator's working agreement here is "outside market hours" for safety).

---

## State summary table

| Item | State |
|------|-------|
| Branch | `claude/review-docs-sdd-cycle-SbbBy`, pushed to origin |
| Constitution | v2.0.0 (Kernel + IX) |
| Kernel manifest | **K1–K7 + K-meta** (K7 added by Increment 1) |
| Spec 008 docs (spec/plan/research/data-model/contracts/quickstart/tasks) | complete |
| tasks.md progress | 15/70 complete (T001–T015) |
| Tests | 329 passing, 1 skipped |
| Lint | clean (ruff check + ruff format) |
| Migration 0003 | shipped (partial index only) |
| Audit events | BACKTEST_STARTED/COMPLETED/FAILED defined |
| Worker DI seam | shipped (`quote_provider`, `clock` kwargs; default None) |
| Backtest helpers | shipped (errors, canonical, clock, verdict, config, hashing) |
| Engine main loop | **NOT YET** — T041 in Phase 4 |
| OHLCV adapters | **NOT YET** — T035 (yfinance), T036 (KIS) in Phase 4 |
| Named-dataset JSON | **NOT YET** — T020 in Phase 3 |
| CLI | **NOT YET** — T045 in Phase 4 |
| Artifact writer | **NOT YET** — T056 in Phase 6 |
| Property fuzz | **NOT YET** — T060 in Phase 7 |
| Autonomous merge in production | DISABLED until spec 007 ships (constitution IX.B-2) |

---

## First message to send to the next session (copy-paste ready)

```text
Read .specify/memory/constitution.md (v2.0.0), .specify/memory/kernel.toml
(K1-K7 + K-meta), HANDOFF-008.md, and specs/008-backtest-engine/tasks.md
in that order.

Then resume /speckit-implement at T016 (Phase 3, User Story 1 first
test). Branch is already claude/review-docs-sdd-cycle-SbbBy; check it
out, pull, run the four sanity checks at the bottom of HANDOFF-008.md
to verify the foundation is intact, then start writing tests for US1.

Increment 2 is non-Kernel — your commits must not touch any path under
kernel.toml (K1-K7 + K-meta).  Do code changes outside US market hours
(09:30-16:00 ET).  Do not push to main.
```

---

## Where to stop within Increment 2 if you can't finish

Increment 2 spans 44 tasks. Acceptable stopping points (each is a checkpoint and an MVP slice):

- **End of Phase 3 (T023)**: synthetic-shock mode reachable; spec 007 harness has a Python entry point even if the engine isn't fully featured. Stoppable PR: "spec 008 — Phase 3 synthetic-shock replay scaffold".
- **End of Phase 4 (T045)**: full engine + CLI; operator can run ad-hoc backtests. Stoppable PR: "spec 008 — US1 + US2 (engine v1)".
- **End of Phase 6 (T059)**: audit + artifact wired. Spec 007 can consume `data/backtests/<run_id>/`. This is the natural end of Increment 2.

Whichever stop you pick, mark the completed tasks `[x]` in `tasks.md`, update this file's "State summary table", and write a one-paragraph "Where the next session resumes" note at the top of this file.
