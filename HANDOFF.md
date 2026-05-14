# auto-invest — Next-Session Handoff (main baseline)

This file is the entry point for **any Claude session landing on `main`** for this repository. It tells you the canonical "what is going on right now" so you don't waste tokens re-discovering it.

## How to start a session in this repo (mandatory)

Per `CLAUDE.md`'s "Autonomous workflow policy", every fresh session MUST run this discovery sequence BEFORE inventing a plan or asking the operator what to do:

```bash
# 1. See every claude/* branch on origin.
git fetch origin
git ls-remote --heads origin 'claude/*' | awk '{print $2}'

# 2. List open PRs — the canonical source of truth for in-flight work.
#    Use: mcp__github__list_pull_requests owner=jinooaction repo=claude state=open

# 3. If there's an open PR pointing at an in-flight branch, check that branch out
#    rather than creating a new one off main.
git checkout <branch from step 2>
git pull --ff-only

# 4. Read the HANDOFF-*.md on that branch (e.g. HANDOFF-008.md) for task-level state.
```

## Status as of last commit on `main`

* **Constitution `v3.0.0`** (live since 2026-05-14, merge commit `f849fab`). Principle IX.D (NEW): Operator Autonomy Supremacy. PRs and merges are part of the autonomous workflow. Kernel touches no longer block merge — the safety perimeter is now spec 007's hardened canary at the **production-deploy** boundary, not at the merge boundary.
* **Spec 001 (automated US-equity trading MVP)** — shipped (since 2026-05-04). Live broker verified.
* **Spec 002 (token telemetry)** — shipped.
* **Spec 003 (session cache)** — shipped.
* **Spec 004 (LLM judgment points)** — stub. Implementation deferred.
* **Spec 005 (autonomous tuner)** — stub. Blocked on spec 007.
* **Spec 006 (deploy automation)** — kernel-touch guard shipped; runner pending.
* **Spec 007 (hardened canary)** — stub. Blocked on spec 008.
* **Spec 008 (backtest engine)** — **IN FLIGHT on `claude/continue-work-ID7Ec`**. 15/41 tasks done; 26 remaining (T016-T041). See `HANDOFF-008.md` for task-level detail.
* **Tests on main**: 363 passing, 1 skipped (live KIS smoke is gated by `KIS_LIVE_TEST=1`).
* **Lint**: clean (`uv run ruff check src tests`).
* **Live broker validation**: operator (mason) ran `scripts/live_smoke.py` against their real KIS account on 2026-05-04; verified.

## Active feature

`specs/008-backtest-engine/` — backtest engine. Hard prerequisite for spec 007 hardened canary.

In-flight branch: `claude/continue-work-ID7Ec`. The branch is fast-forward-mergeable into main (all earlier work merged via PR #1). When the next session lands on main, it should check that branch out and resume implementation.

Read in this order before doing anything new:

1. `.specify/memory/constitution.md` — v3.0.0; IX.D Operator Autonomy Supremacy.
2. `.specify/memory/kernel.toml` — high-attention forensic list (no longer a barrier under v3.0.0).
3. `HANDOFF-008.md` — task-level state for spec 008 (committed to main via PR #1).
4. `specs/008-backtest-engine/spec.md` → `plan.md` → `research.md` → `data-model.md` → `contracts/` → `tasks.md`.
5. `CLAUDE.md` — autonomous-workflow + autonomous-merge policy. **Read this before opening or merging a PR.**

## What is NOT pending operator review

Under constitution v3.0.0, none of this requires a human "approve" click:

- PR creation — part of the autonomous workflow.
- PR merge — operator instruction in chat counts as approval.
- Kernel touches — they emit a forensic audit row and continue. No merge block.

Trading-safety invariants (principles I-VII and VIII.A — position caps, whitelist, LLM-only-at-judgment-points, append-only audit, secret isolation, Backtest→Canary→Full, API robustness, no-market-hours-deploys) are still non-negotiable. They're enforced at the **production-deploy** boundary by spec 007's hardened canary (when shipped).

## Historical handoff files (informational only)

- `HANDOFF-002-003.md` — branch state through specs 002/003/004/005/006/007 + v2.0.0 constitution bump. Predates v3.0.0; do NOT use its "operator merges manually" guidance.
- `HANDOFF-008.md` — current spec 008 in-flight state. Authoritative for that work.

## What NOT to do in the next session

- Do **not** create a new branch off main when an in-flight branch already exists (the discovery recipe above prevents this).
- Do **not** ask the operator "어떤 작업을 원하세요?" when an open PR + `HANDOFF-008.md` already tell you what's next.
- Do **not** modify spec 001 / 002 / 003 files unless the operator explicitly asks for an amendment. They are shipped.
- Do **not** push KIS credentials anywhere. `.env` is gitignored; live tests are gated by `KIS_LIVE_TEST=1`.
- Do **not** push to `main` (no direct push; merges land via PR per the autonomous-workflow policy).

## Quick state summary

| Item | State |
|------|-------|
| Constitution | v3.0.0 (IX.D supremacy) |
| Last main commit | `f849fab Merge PR #2: constitution v3.0.0` (plus this HANDOFF refresh) |
| Active in-flight feature | spec 008 backtest engine |
| Active in-flight branch | `claude/continue-work-ID7Ec` |
| Spec 008 progress | 15/41 tasks (Phases 1-2 done; US1 4/17 done) |
| Spec 008 next action | T016 broker_mock.py; see `HANDOFF-008.md` for full sequence |
| Open PRs | check via `mcp__github__list_pull_requests` |
| Tests on main | 363 passing, 1 skipped |
| Lint on main | clean |
| Operator local env | `uv` venv, `gh` auth, KIS keys in `.env` (operator's machine only) |
