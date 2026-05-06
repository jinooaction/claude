# Branch Handoff — `claude/optimize-token-efficiency-uYiKk`

**Read this first if you're resuming work on this branch.**
The repo-root `HANDOFF.md` describes the `main` baseline. This file
captures only what changed on this branch and what the next session
needs to do.

## What this branch added (commit `df68e69`)

| Spec | Status | Artefacts |
|------|--------|-----------|
| 002 — token telemetry & KPIs | **shipped** | `specs/002-token-telemetry/`, `src/auto_invest/telemetry/`, migration `0002_token_usage.sql`, `audit.LLM_CALL`/`PRICE_TABLE_LOADED`, `auto-invest efficiency` CLI, daily-report Token Efficiency section |
| 003 — Claude Code session cache | **shipped (validation pending)** | `specs/003-session-cache/spec.md`, `.claude/settings.json`, `.claude/hooks/session_context.py` |
| 004 — LLM judgment points | **STUB** | `specs/004-llm-judgment-points/spec.md` |
| 005 — autonomous tuner | **STUB** | `specs/005-autonomous-tuner/spec.md` |

**Tests**: 301 passing, 1 skipped (live KIS). `ruff check` clean.

## What still needs doing

### Operator-side, cannot be automated

These are the gating items for promoting 004/005. They all require
either real time, real LLM traffic, or an operator decision.

1. **Validate 003 SessionStart hook in a fresh session.** Open a new
   Claude Code session in this repo. The hook should fire once and
   the system should surface a `session-context fingerprint:` line.
   Confirm by checking the session transcript or running:
   ```bash
   .claude/hooks/session_context.py < /dev/null | jq '.systemMessage'
   ```
   Expected: `"session-context fingerprint: <12-hex> (~59k chars from 5 sources)"`.

2. **Decide which 004 candidate ships first.** The 004 stub lists
   three candidates: `volatility_assessment`, `news_screen`,
   `daily_summary`. The next session should run
   `/speckit-clarify specs/004-llm-judgment-points/` to narrow to one.
   Recommendation: start with `daily_summary` — it runs once per day,
   has no real-time latency budget, and produces immediate operator
   value.

3. **Accumulate ≥30 days of telemetry data.** 002's promotion bar for
   004/005 is 30 days of `token_usage` data. v1 generates none today.
   Two ways to get there:
   - Ship a tiny 004 judgment point (e.g., `daily_summary`) and let
     the worker run for 30 sessions.
   - Or, instrument the `/speckit-*` workflow itself via the meter so
     SDD usage populates `token_usage` for 003 measurement only. This
     would require a small auxiliary script that wraps Anthropic SDK
     calls made outside the trading loop.

4. **First canary trade** (option B from the original `HANDOFF.md`) is
   still open and orthogonal to this branch. The new telemetry does
   not block it; running B in parallel produces audit log activity
   that exercises the 002 daily-report counters end-to-end.

### Code-side, ready for the next session

5. **Wire `PRICE_TABLE_LOADED` audit emission.** The contract
   (`specs/002-token-telemetry/contracts/price-table.md`) calls for
   the price-table loader to record a `PRICE_TABLE_LOADED` audit row
   on every load. The payload class exists
   (`PriceTableLoadedPayload`), but no call site emits it yet.
   Implementation hint: emit it from inside `cli.efficiency` and
   inside `cli.run`'s startup flow, once per process. Test belongs
   in `tests/integration/test_efficiency_cli.py` (assert one
   `PRICE_TABLE_LOADED` row in `audit_log` after the command runs).

6. **PR-merge to `main`.** Branch is currently local + pushed to
   `origin/claude/optimize-token-efficiency-uYiKk`. The operator must
   open a PR and merge to `main` after their own review. Per the
   original `HANDOFF.md`, **do not push to `main` without operator
   permission**.

## Reading order for the next session

If resuming on this branch:

1. `.specify/memory/constitution.md` — the eight non-negotiable principles.
2. `HANDOFF.md` (repo root) — main-line state.
3. `HANDOFF-002-003.md` (this file).
4. `specs/002-token-telemetry/spec.md` → `plan.md` → `tasks.md`.
5. `specs/003-session-cache/spec.md`.
6. `specs/004-llm-judgment-points/spec.md` (stub) +
   `specs/005-autonomous-tuner/spec.md` (stub).

## Quickstart commands for the next session

```bash
# verify branch state
git status
git log -1 --oneline                # should be df68e69

# verify clean test + lint
uv run ruff check src tests
uv run pytest                       # expect 301 passed, 1 skipped

# verify SessionStart hook still produces a stable fingerprint
.claude/hooks/session_context.py < /dev/null | python -m json.tool | head -5

# verify the new CLI surface
uv run auto-invest efficiency --help
uv run auto-invest efficiency --window 7d --as-of 2026-05-06   # empty-state JSON
```

## What NOT to do

- Do **not** implement 004 or 005 without first running
  `/speckit-clarify` on the relevant stub. Both are explicitly gated.
- Do **not** instrument any LLM call outside a `TokenMeter` context
  manager — FR-T01 forbids it; integration tests will catch it.
- Do **not** put prompt or response text into `token_usage` or any
  audit row — FR-T11 / constitution V forbid it.
- Do **not** modify constitution v1.0.0 to relax principle III. If
  judgment-point semantics need adjustment, amend via principle VIII's
  amendment process (dedicated commit, version bump, template
  propagation), not as a side-effect of feature work.

## State summary table

| Item | State |
|------|-------|
| Branch | `claude/optimize-token-efficiency-uYiKk` pushed to origin |
| Last commit | `df68e69 feat(002,003): token telemetry + session-cache settings; stub 004/005` |
| Tests | 301 passing, 1 skipped |
| Lint | clean |
| Telemetry table | created (migration 0002), zero rows in production |
| Session hook | wired, operator-side validation pending |
| 004/005 promotion | blocked on 30 days of data + operator clarify |
