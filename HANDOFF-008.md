# Branch Handoff — spec 008 (backtest engine), Increment 2 entry point

**Branch**: `claude/review-docs-sdd-cycle-SbbBy` (per `.specify/active-work.json` — the canonical source)
**Last commit**: see `git log -1 --oneline` after `git fetch origin && git checkout <branch> && git pull --ff-only`
**Status**: working tree should be clean; if not, investigate before any code work.
**Constitution**: v2.0.0 (Kernel + principle IX). Spec 008 added Kernel group `[K7_named_datasets]` to `kernel.toml` in Increment 1.

> **Read this first if you are the next session resuming this branch.**
> `HANDOFF.md` and `HANDOFF-002-003.md` describe the main-line baseline.
> This file is the spec-008-specific resume point.

---

## TL;DR for the next session — the "이어가" workflow

The operator's standard first message in a fresh workspace is one word: **`이어가`** (or `resume`).
The SessionStart hook does most of the orientation for you. When that one-word
message arrives, do this exact sequence:

1. **Read the SessionStart `systemMessage`** that the harness has already emitted.
   It carries:
   - `session-context fingerprint: <12 hex>` — the prompt-cache anchor.
   - `branch=<current> OK (matches active-work)` *OR* `ACTION REQUIRED -- branch MISMATCH …`
   - `next: T019,T020,T021,T022` (or whatever `next_tasks` says).
2. **Read `.specify/active-work.json`** to confirm `active_branch`, `next_tasks`, and `tip_commit_short`.
3. **If the hook said MISMATCH**, immediately run:
   ```bash
   git fetch origin --prune
   git checkout <active_branch>      # from active-work.json
   git pull --ff-only
   ```
   Do **not** create a new branch even if your auto-generated session prompt says
   `Develop on branch claude/<title>-<hash>`. `active-work.json` is the source of truth.
4. **Read `.specify/memory/constitution.md` (v2.0.0)** and `.specify/memory/kernel.toml` (K1–K7 + K-meta).
5. **Read `specs/008-backtest-engine/tasks.md`** at the `next_tasks` cursor.
6. **Run the four sanity checks** before any code work:
   ```bash
   uv sync
   uv run ruff check src tests           # expected: All checks passed!
   uv run ruff format --check src tests  # expected: N files already formatted
   uv run pytest -q                       # expected: <baseline> passed, 1 skipped
   ```
7. Resume implementation at `next_tasks[0]`.

---

## The session-handoff contract

Two files are the **single source of truth** between sessions:

| File | What it tracks | Updated by |
|------|----------------|------------|
| `.specify/active-work.json` | `active_branch`, `active_feature_dir`, `next_tasks`, `tip_commit_short`, `kernel_status` | the **outgoing** session, at the very end of its work, in the same commit as code (or a separate `docs: bump active-work` commit) |
| `HANDOFF-008.md` (this file) | narrative — what landed, what's open, gotchas | the outgoing session when it materially changes the picture |
| `tasks.md` | per-task `[x]` checkboxes | the outgoing session when tasks become **green** (test+code both committed) |

**End-of-session checklist** (every session MUST perform this before stopping):

1. Are commits clean and pushed? `git status` should show "up to date".
2. Update `.specify/active-work.json`:
   - `tip_commit_short` ← new HEAD sha (`git rev-parse --short HEAD`)
   - `next_tasks` ← the task IDs the next session should pick up
   - `phase_focus` ← one-line summary of where you stopped
   - `last_session_end_utc` ← current UTC timestamp
3. If the picture changed materially (PR plan shift, blocker, new contract decision), append a one-line entry to "Where the last session stopped" below.
4. Commit + push the `active-work.json` update (combine with the working commit when possible).

## How the SessionStart hook helps you

The hook at `.claude/hooks/session_context.py` does the following before your
first message is even processed:

- `git fetch origin --prune` (silent, idempotent).
- Reads `.specify/active-work.json` to resolve the active feature dir.
- Loads the constitution, kernel manifest, **active feature's spec/plan/data-model/research** as `additionalContext` so the long-lived context tracks the current feature (no more "fresh session sees spec 001 only").
- Emits `systemMessage` with the branch-match diagnosis. If the diagnosis says `ACTION REQUIRED -- branch MISMATCH`, you must `git checkout <active>` before any other work.

If the hook can't run (no `.specify/active-work.json` yet, network down for fetch, etc.), it falls back gracefully and never blocks the session.

---

## What landed in this branch already

Nine commits, in order:

```text
48c9801 docs(008): /speckit-specify        backtest engine spec drafted
cccf7ab docs(008): /speckit-clarify Q1     OHLCV vendor (yfinance + KIS historical)
2630f97 docs(008): /speckit-clarify Q2-Q5  fill model, migration policy, thresholds, OPEX freeze
2abeb4b docs(008): /speckit-plan           plan + research (R-1..R-12) + data-model + 5 contracts + quickstart
b30c2d9 docs(008): /speckit-tasks          67 tasks across 7 phases (US1-US4)
30b8f79 docs(008): /speckit-analyze        C1 (HIGH) + M1/M2/M3 (MEDIUM) remediation; now 70 tasks
aa5b1de chore:    ruff format pass         pure-whitespace reflow on telemetry/deploy/test files
3828f5d feat(008): Increment 1             Phase 1+2 — the one-time K-meta human-merge change set
6220277 docs(008): branch handoff          first cut of HANDOFF-008.md
dc2cb95 test(008): T016/T017/T018          Phase 3 US1 red tests (non-Kernel)
```

(Plus the commit that introduces the session-handoff system — `active-work.json`, the hook upgrade, this file.)

Spec docs are complete and the engine's **foundation** is on disk:

| Spec artifact | Status |
|---------------|--------|
| `specs/008-backtest-engine/spec.md` | clarified (5 answers integrated) |
| `specs/008-backtest-engine/plan.md` | Constitution Check I–IX pass; K-meta one-time event documented |
| `specs/008-backtest-engine/research.md` | R-1..R-12 decisions frozen |
| `specs/008-backtest-engine/data-model.md` | in-memory + on-disk + SQLite schemas |
| `specs/008-backtest-engine/contracts/` | cli, ohlcv-adapter, named-dataset, run-artifact, audit-events |
| `specs/008-backtest-engine/quickstart.md` | 5-step operator path |
| `specs/008-backtest-engine/tasks.md` | 70 tasks; **T001–T015 are `[x]`**, T016–T018 red tests landed (not yet `[x]` — they only flip when green) |
| `specs/008-backtest-engine/checklists/requirements.md` | all ✓ |
| `.specify/active-work.json` | NEW — single source of truth for next session |

Code already on this branch (Increment 1 + red tests):

| File | Status |
|------|--------|
| `src/auto_invest/persistence/audit.py` | `EventType` += BACKTEST_STARTED/COMPLETED/FAILED + three payload classes. K4 file (touched once). |
| `src/auto_invest/persistence/migrations/0003_backtest_events.sql` | new partial index for SC-B06; no column changes. Added to K4 in kernel.toml. |
| `.specify/memory/kernel.toml` | K4 += 0003 path; new group `[K7_named_datasets]`. |
| `src/auto_invest/worker/loop.py` | two optional kwargs on `Worker.__init__` — `quote_provider`, `clock`. Both default `None`; live behaviour byte-identical (verified). |
| `src/auto_invest/backtest/` | subpackage: `errors.py`, `clock.py`, `verdict.py`, `config.py`, `hashing.py`, `ohlcv/canonical.py`. All non-Kernel. |
| `tests/backtest/test_foundational.py` | 10 tests (T015), all passing. |
| `tests/backtest/test_named_dataset.py` | T016 red test — waits for T019. |
| `tests/backtest/test_kernel_safety.py` | T017 red test — waits for T021. |
| `tests/backtest/test_synthetic_shock_mode.py` | T018 red test — waits for T022 + T020 + T041. |
| `pyproject.toml` + `uv.lock` | yfinance>=0.2, hypothesis>=6.0; `nightly` pytest marker. |
| `.gitignore` | negation rules for `data/ohlcv/datasets/`. |

---

## What is left — three increments mapped to PRs

**Increment 2 — Phases 3+4+5+6 = T019..T059 (the remainder of US1 + US2 + US3 + US4). NON-Kernel except for T020.**

| Phase | Tasks | Story | What ships |
|-------|-------|-------|------------|
| Phase 3 (in flight) | T019–T023 (5 left) | US1 | green T016/T017/T018: named-dataset loader, K7 fixture, engine.kernel_touch_check, synthetic-shock replay mode |
| Phase 4 | T024–T045 (22) | US2 | OHLCV adapters (yfinance + KIS historical), canonical cache, hybrid fill model, portfolio ledger, BacktestBroker, engine main loop, report, verdict, manifest, CLI |
| Phase 5 | T046–T052 (7) | US3 | `_emit_started/_completed/_failed` wired; FR-B16 invariant tests |
| Phase 6 | T053–T059 (7) | US4 | on-disk artifact dir (5 files) atomic write + byte-identity tests |

**T020 is a one-off Kernel touch** — it creates `data/ohlcv/datasets/synthetic_shock_v1.json` which is registered under `[K7_named_datasets]`. The deploy guard will flag this. That is expected (constitution IX.C — "adding a file to the Kernel is always a forward-compatible safety improvement"). Operator should explicitly approve T020's commit; subsequent commits must NOT modify the file.

**Increment 3 — Phase 7 = T060..T067 + the three analyze-boost tasks T068, T069, T070 (11 tasks). NON-Kernel. One PR.**

Naive task count is 70 in `tasks.md`; with 15 `[x]` + 3 red tests landed, **52 tasks remain** to fully green.

---

## How to resume — exact first commands (auto-triggered by `이어가`)

```bash
# 1. Land on the right branch.
git fetch origin --prune
git checkout claude/review-docs-sdd-cycle-SbbBy
git pull --ff-only

# 2. Verify the foundation is intact.
git log -1 --oneline   # should match active-work.json tip_commit_short
uv sync
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q       # expect baseline pass count (see active-work.json.test_baseline.passing)

# 3. Verify the K7 group is in place.
uv run python -c "
import tomllib
m = tomllib.loads(open('.specify/memory/kernel.toml').read())
assert 'K7_named_datasets' in m
print('K7 OK')"
```

Once those checks succeed, start at `active-work.json.next_tasks[0]`.

---

## Implementation discipline for Increment 2 (cannot be repeated enough)

The Phase 2 K-meta touch is already done. From here on:

1. **NO file under `.specify/memory/kernel.toml` may appear in any commit's diff EXCEPT T020.**
   - K1: `src/auto_invest/risk/gates.py`, `risk/__init__.py`, `config/caps.py`
   - K2: `src/auto_invest/config/whitelist.py`
   - K3: `src/auto_invest/telemetry/meter.py`, `telemetry/store.py`
   - K4: `src/auto_invest/persistence/audit.py`, `migrations/0001_initial.sql`, `migrations/0002_token_usage.sql`, `migrations/0003_backtest_events.sql`
   - K5: `src/auto_invest/logging_config.py`, `config/loader.py`
   - K6: `src/auto_invest/worker/schedule.py`
   - K7: `data/ohlcv/datasets/synthetic_shock_v1.json` ← will be created in T020 and is the only spec-008 file you create directly into the Kernel boundary. After T020, do not touch this file again in non-K change sets.
   - K-meta: `.specify/memory/constitution.md`, `kernel.toml`

   Easy spot-check before any commit:
   ```bash
   git diff --staged --name-only | grep -E '\.specify/memory/(kernel\.toml|constitution\.md)|src/auto_invest/(risk/gates|risk/__init__|config/(caps|whitelist|loader)|telemetry/(meter|store)|persistence/(audit|migrations/000[1-3])|logging_config|worker/schedule)\.(py|sql)|data/ohlcv/datasets/synthetic_shock_v1\.json' \
     ; echo "(must be empty unless this is the T020 commit)"
   ```

2. **Tests written first.** T016/T017/T018 already exist as red; T019/T020/T021/T022 must make them green without modifying the tests.

3. **Live behaviour stays byte-identical.** The two `Worker.__init__` kwargs default to `None`. Any spec-008 work must NOT change live default behaviour. The foundational test (`test_worker_kwargs_default_to_none_preserve_live_behaviour`) is the canary.

4. **Determinism is a hard contract (FR-B12).** Anything you add that ingests time, randomness, dict-ordering, or float arithmetic must surface through the six-hash determinism floor in `auto_invest.backtest.hashing` (research R-5).

5. **Market-hours discipline.** Engine *code* changes are still subject to constitution VIII.A — do code changes off-hours (outside 09:30–16:00 ET). *Running* a backtest does not affect the live worker; that part is safe at any hour.

6. **Append-only audit.** The engine never UPDATEs or DELETEs `audit_log`. The 0001 trigger enforces this, but spec 008 also adds an explicit unit test in Phase 5 (T048).

---

## Risks / gotchas the next session should know about

- **Worker.tick + indicator priming.** Live `Worker._evaluate_and_route` calls `store_synthetic_bar` and `get_bars` to feed indicators. The synthetic-shock replay (T022) must prime indicator state silently for `warmup_bars` bars *before* the shock day. The current `_evaluate_and_route` happily does this if you simply call `tick(now=...)` for each warmup bar — but you'll need to suppress order routing in the warmup window. Cleanest path: the BacktestBroker (T040) is constructed but ignores all `submit_order` calls during warmup; flip on at first non-warmup tick.
- **CLI is `typer`, not `click`.** Plan + contracts say "click" in one or two places. The repo's existing CLI uses typer; T045 must use typer for consistency.
- **yfinance is flaky against Yahoo.** Adapter must implement tenacity retry + a circuit breaker (T035). Tests must use `respx` to mock; never hit live Yahoo in CI.
- **KIS historical adapter and credentials.** T036 reuses `auto_invest.broker.auth`. CI tests mock the endpoint with `respx`; never use real KIS keys in tests. Constitution V binds.
- **partial index naming.** `idx_audit_log_backtest_events` is the index that 0003 creates; T049's `EXPLAIN QUERY PLAN` test must accept either that name OR the existing `idx_audit_log_event_ts`.
- **`schema_version: 1`** on every on-disk artifact JSON. Bumping is a breaking change for spec 007's harness. Don't bump in Increment 2.
- **The `Decimal` type.** Prices are `Decimal`, not `float`. Avoid float-Decimal mixing.

---

## CASE A / CASE B diagnostic (kept for emergencies)

If the SessionStart hook is absent, broken, or the auto-generated session prompt
overrides everything and you can't trust `active-work.json`, fall back to:

**CASE A** — `remotes/origin/claude/review-docs-sdd-cycle-SbbBy` exists at `git fetch origin --prune`:
```bash
git checkout claude/review-docs-sdd-cycle-SbbBy
git pull --ff-only
git log -1 --oneline
cat HANDOFF-008.md
```

**CASE B** — that branch is NOT visible at origin:
This workspace is mounted on the wrong repo. Stop, report `git remote -v` and `git branch -a` to the operator, and do not write code.

---

## What NOT to do

- Do **not** push to `main`. PR review by the operator.
- Do **not** modify any Kernel file (see list above) outside of intentional K-meta PRs.
- Do **not** touch `worker/schedule.py` (K6) — pass a synthetic `now` instead.
- Do **not** introduce a parallel audit log; new `BACKTEST_*` rows go through `auto_invest.persistence.audit.append`.
- Do **not** add live-network calls inside the replay loop (FR-B09). Cache-first ingest before `BACKTEST_STARTED`.
- Do **not** modify `synthetic_shock_v1.json` once created in T020. Adding/removing a date is L4 (operator-only).
- Do **not** push during US regular hours (constitution VIII.A applies to deploys; the operator's working agreement here is "outside market hours" for safety).
- Do **not** forget to update `.specify/active-work.json` before ending your session.

---

## Where the last session stopped

| End of session | tip commit | Status | Next |
|----------------|------------|--------|------|
| 2026-05-07 (Increment 1 / Phase 1+2) | `3828f5d` | foundation landed; 329 pass, 1 skipped | T016 (US1 first red test) |
| 2026-05-07 (HANDOFF first cut) | `6220277` | handoff doc created | T016 |
| 2026-05-13 (Phase 3 US1 red tests) | `dc2cb95` | T016/T017/T018 red tests landed (ImportError red because T019/T021/T022 absent) | T019, T020, T021, T022 |
| 2026-05-13 (handoff system) | this commit | active-work.json + SessionStart hook upgrade + this rewrite | T019 unchanged |

When you finish a session, append a row here.

---

## First message to send to the next session (copy-paste ready)

```text
이어가
```

That's it. The SessionStart hook + active-work.json carry the rest of the
state. If the hook is missing or misroutes, fall back to the longer prompt
preserved below.

### Fallback prompt (use only if `이어가` doesn't trigger correct branch resume)

```text
Read .specify/memory/constitution.md (v2.0.0), .specify/memory/kernel.toml
(K1-K7 + K-meta), .specify/active-work.json (single source of truth),
HANDOFF-008.md, and specs/008-backtest-engine/tasks.md in that order.

Then resume at the task ID listed in .specify/active-work.json.next_tasks[0].
Branch is .specify/active-work.json.active_branch; check it out, pull, run
the four sanity checks at the top of HANDOFF-008.md to verify the foundation
is intact, then start work.

Increment 2 is non-Kernel except for T020 — your commits must not touch any
path under kernel.toml (K1-K7 + K-meta) outside T020. Do code changes outside
US market hours (09:30-16:00 ET). Do not push to main.
```

