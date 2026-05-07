# Branch Handoff — `claude/optimize-token-efficiency-uYiKk`

**Read this first if you're resuming work on this branch.** The
repo-root `HANDOFF.md` describes the `main` baseline. This file
captures everything this branch added on top of `main` and what the
next session should do.

> **File-name note**: still called `HANDOFF-002-003.md` for git-history
> continuity, but the branch now spans 002, 003, 004 (stub), 005
> (stub, v2.0.0-aligned), 006 (kernel guard shipped, runner pending),
> 007 (stub), plus a constitutional MAJOR bump to v2.0.0.

---

## TL;DR for the next session

1. Read `.specify/memory/constitution.md` (v2.0.0 — Kernel + principle IX).
2. Read `.specify/memory/kernel.toml` (machine-readable safety perimeter).
3. Read this file.
4. Start with **Backtest engine (option D)** — it is the hard
   prerequisite for spec 007 → spec 006 deploy runner → spec 005
   autonomous tuner. Without it, autonomous merge stays disabled
   (constitution IX.B-2).

The first message to send to the next session is at the bottom of
this file. Copy-paste ready.

---

## Branch state at last commit

```
881b91b feat(006): kernel-touch guard (constitution IX.B-1, FR-D13)
c88f9ec docs(005,006,007): align with constitution v2.0.0 — Kernel boundary
99c2f7b constitution: introduce Kernel + principle IX (v1.1.0 -> v2.0.0)
3c19845 docs(006): PR draft, migration 0002 runbook, spec 006 (spec + plan)
2700543 constitution: amend principle VIII for deploy automation (v1.0.0 -> v1.1.0)
e86011c feat(002): T503 wire PRICE_TABLE_LOADED audit emission   [other session]
edfc97b docs(002,003): branch handoff + README pointers
df68e69 feat(002,003): token telemetry + session-cache settings; stub 004/005
```

Everything is pushed to `origin/claude/optimize-token-efficiency-uYiKk`.
`main` is unchanged at `dd81fa0`. **Do not push to `main`** — the
operator opens the PR and merges per the original `HANDOFF.md` rule.

| Spec / artifact | Status |
|------|--------|
| 002 — token telemetry & KPIs | **shipped** (T503 closed by parallel session) |
| 003 — Claude Code session cache | **shipped** (operator-side validation pending — see below) |
| 004 — LLM judgment points | **STUB** |
| 005 — autonomous tuner | **STUB**, v2.0.0-aligned (L1/L2/L3/L4 tiered authority) |
| 006 — deploy automation | spec + plan + kernel-touch guard (FR-D13) shipped; runner pending |
| 007 — hardened canary | **STUB**, defines the gate referenced by IX.B-2 |
| Constitution | **v2.0.0** (Kernel + principle IX added) |
| Kernel manifest | `.specify/memory/kernel.toml` (7 groups: K1–K6 + K-meta) |
| Tests | **319 passing, 1 skipped** (live KIS gated). +17 new this push |
| Lint | clean |

---

## Constitution v2.0.0 — what changed

- **Principle IX added** (Self-Modification Boundary, NON-NEGOTIABLE).
  Defines a Kernel that the autonomous tuner cannot modify. Outside
  the Kernel, autonomous merge is permitted via spec 007's hardened
  canary (when 007 ships).
- **Principle VIII.B-3** health window 30 s → 90 s minimum. Operator
  may configure longer; never shorter.
- **Principle VIII.B-5** rewritten to defer to IX (was
  "operator-triggered, not autonomous"; now "tiered autonomy — see
  IX"). Backward-incompatible → MAJOR bump.
- Kernel manifest at `.specify/memory/kernel.toml` is the single
  source of truth for "what counts as Kernel". Deploy code consults
  it; never hard-codes paths.

The Kernel comprises 7 groups, each tied to one safety invariant:

| Group | Invariant | Files (excerpt) |
|-------|-----------|-----------------|
| K1 | Position sizing (I) | `src/auto_invest/risk/gates.py`, `config/caps.py` |
| K2 | Whitelist (II) | `src/auto_invest/config/whitelist.py` |
| K3 | LLM-only-at-judgment (III) | `src/auto_invest/telemetry/meter.py`, `store.py` |
| K4 | Append-only audit (IV) | `persistence/audit.py`, both migration SQL files |
| K5 | Secret isolation (V) | `logging_config.py`, `config/loader.py` |
| K6 | Market-hours guard (VIII.A) | `src/auto_invest/worker/schedule.py` |
| K-meta | The manifest itself + the constitution | `kernel.toml`, `constitution.md` |

Predicted Kernel-touch frequency: 0–2 events per year. Everything
else is autonomous-merge-eligible after spec 007 ships.

---

## What still needs doing — recommended order

The four steps below are the path to true autonomous execution per
the operator's stated goal. Each one is best done in its own session
for token efficiency and SDD discipline.

### Step 1 (next session): Backtest engine — spec 008

**Why first**: spec 007's hardened canary requires the ability to
replay historical OHLCV against the new code. That capability is the
backtest engine. Without it, IX.B-2 stays unsatisfied and autonomous
merge stays disabled.

**Scope sketch** (the next session writes the spec; this is just an
orientation):
- Historical OHLCV ingest: at minimum the symbols on the operator's
  whitelist; vendor TBD (yfinance / IEX / KIS historical / vendor
  CSV).
- Replay engine that drives `Worker.tick` against historical quotes
  instead of live KIS.
- Synthetic-shock dataset prepared for 007: 2020-03-12, 2020-04-20,
  2024-08-05, plus the most recent quarterly OPEX day.
- Backtest report (returns, Sharpe, drawdown, per-rule).
- Promotion gate: a passing backtest report becomes input to the
  existing canary stage.

**Constitutional notes for the next session**:
- This is not a Kernel change (no file under `kernel.toml` should
  appear in the diff). Verify with `kernel_diff_check` after coding.
- Adds new rows to `audit_log` (`BACKTEST_STARTED`, `BACKTEST_COMPLETED`)
  — append-only, principle IV.
- Touches `worker/schedule.py`? **No.** Replay should NOT modify
  `schedule.py` (that's K6). It should pass a different "now" function
  into the existing scheduling code.

**Entry command for the next session** (after reading the constitution
and this file):
```
/speckit-specify Backtest engine for auto-invest. Hard prerequisite for
spec 007 (hardened canary, constitution IX.B-2). Replays historical
OHLCV against the existing Worker.tick / risk-gate stack to produce
a deterministic returns/drawdown/Sharpe report. NOT a Kernel change.
NOT a strategy change. Vendor for OHLCV: TBD during /speckit-clarify.
```

### Step 2: Spec 007 implementation — hardened canary

Depends on step 1. Spec is already drafted at
`specs/007-canary-hardening/spec.md`.

Implements: 5-metric all-or-nothing acceptance, ≥30 trading-day
window for L2 / ≥45 for L3, synthetic-shock replay, ≥10 000 property
fuzz iterations.

### Step 3: Spec 006 deploy runner

Depends on the kernel guard (already shipped, see
`src/auto_invest/deploy/kernel_guard.py`). Implements FR-D01..D14 in
full: pull / sync / migrate / dry-run / stop / start / health-check
(90 s) / rollback. Plugs the kernel guard in at the critical path.
Adds systemd unit + timer templates.

### Step 4: Spec 005 autonomous tuner

Depends on 1–3. Implements the L1/L2/L3 detection rules and the
hand-off to the deploy runner. L4 changes auto-open a PR (operator
merges).

After step 4, the system is genuinely autonomous outside the Kernel.
Operator's per-day workload: 0. Operator's per-year workload: 0–2
Kernel merges.

---

## Operator-side, still pending (not blockers for the above)

These are unchanged from before. Listed here so the next session
doesn't re-prompt them.

1. **Validate 003 SessionStart hook in a fresh session.**
   ```bash
   .claude/hooks/session_context.py < /dev/null \
     | python -m json.tool | head -5
   ```
   Expected: a `systemMessage` line with
   `session-context fingerprint: <12-hex>`.

2. **Decide which 004 candidate ships first.** Recommend
   `daily_summary` (off-hours, no real-time latency budget). Run
   `/speckit-clarify specs/004-llm-judgment-points/` to narrow.

3. **Accumulate ≥30 days of telemetry data** before promoting 004.
   Today there is none.

4. **First canary trade** (option B from main HANDOFF) is still open.

5. **PR-merge to `main`** for this branch is still pending operator
   review. PR body draft at
   `.github/PULL_REQUEST_TEMPLATE/optimize-token-efficiency.md`.

---

## Reading order for the next session (resuming on this branch)

1. `.specify/memory/constitution.md` — **v2.0.0**, principles I–IX.
2. `.specify/memory/kernel.toml` — Kernel manifest.
3. `HANDOFF.md` (repo root) — main-line state.
4. `HANDOFF-002-003.md` (this file).
5. The spec for whatever step you're on (008 backtest → 007 → 006 → 005).

---

## Quickstart commands for the next session

```bash
# verify branch state
git fetch origin
git checkout claude/optimize-token-efficiency-uYiKk
git pull --ff-only
git log -1 --oneline                # should be 881b91b

# verify clean test + lint
uv run ruff check src tests
uv run pytest                       # expect 319 passed, 1 skipped

# verify SessionStart hook still produces a stable fingerprint
.claude/hooks/session_context.py < /dev/null | python -m json.tool | head -5

# verify the kernel guard is wired
uv run python -c \
  "from auto_invest.deploy import load_kernel_manifest; \
   print(sorted(load_kernel_manifest().groups.keys()))"
# Expected: ['K1_position_sizing', 'K2_whitelist', 'K3_judgment_points',
#            'K4_append_only_audit', 'K5_secret_isolation',
#            'K6_market_hours_guard', 'K_meta']
```

---

## What NOT to do

- Do **not** modify any file in the Kernel without explicit operator
  approval. The kernel guard will block an autonomous deploy that
  touches `kernel.toml` paths; respect it manually too.
- Do **not** skip `/speckit-specify` for the backtest engine. It is
  a new feature and SDD discipline applies.
- Do **not** implement spec 007 before the backtest engine — 007's
  property fuzz and synthetic-shock replay both depend on it.
- Do **not** push to `main`. PR opens by operator review.
- Do **not** instrument LLM calls outside `TokenMeter` (FR-T01).
- Do **not** put prompt or response text into `token_usage` or any
  audit row (FR-T11 / constitution V).

---

## State summary table

| Item | State |
|------|-------|
| Branch | `claude/optimize-token-efficiency-uYiKk` pushed to origin |
| Last commit | `881b91b feat(006): kernel-touch guard ...` |
| Constitution | v2.0.0 (Kernel + IX) |
| Kernel manifest | shipped, 7 groups |
| Tests | 319 passing, 1 skipped |
| Lint | clean |
| Telemetry table | created (migration 0002), zero rows in production |
| Session hook | wired, operator-side validation pending |
| Kernel-touch guard | shipped (`auto_invest.deploy.kernel_guard`) |
| Deploy runner | not yet shipped (step 3 above) |
| Hardened canary (007) | spec only; impl blocked on backtest engine |
| Backtest engine | not yet specced (step 1, next session) |
| Autonomous merge in production | DISABLED until 007 ships (constitution IX.B-2) |

---

## First message to send to the next session (copy-paste ready)

```
Read .specify/memory/constitution.md (v2.0.0), .specify/memory/kernel.toml,
HANDOFF.md, and HANDOFF-002-003.md in that order. Then start the SDD
cycle for the backtest engine: /speckit-specify Backtest engine for
auto-invest. Hard prerequisite for spec 007 (hardened canary,
constitution IX.B-2). Replays historical OHLCV against the existing
Worker.tick / risk-gate stack to produce a deterministic
returns/drawdown/Sharpe report. NOT a Kernel change. Vendor for OHLCV
TBD during /speckit-clarify.

After /speckit-specify, run /speckit-plan, then /speckit-tasks, then
/speckit-implement. Branch is already
claude/optimize-token-efficiency-uYiKk; stay on it until merge or open
a child branch off of it. Do not push to main without operator approval.
```
