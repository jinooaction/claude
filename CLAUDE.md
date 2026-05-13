<!-- SPECKIT START -->
**Active-work pointer**: `.specify/active-work.json` (single source of truth — the
SessionStart hook reads this, not hardcoded paths). It carries `active_branch`,
`active_feature_dir`, `next_tasks`, and `tip_commit_short`. **A new session in a
fresh workspace should resolve everything from this file** — the operator's
standard first message is `이어가` (or `resume`).

Active feature: `specs/008-backtest-engine/` (per `.specify/active-work.json`)

Read in order when working on this feature:

1. `.specify/memory/constitution.md` — non-negotiable principles (v2.0.0).
2. `.specify/memory/kernel.toml` — Kernel manifest (K1–K7 + K-meta; K7 added by spec 008).
3. `.specify/active-work.json` — active branch, next tasks, tip commit, kernel-touch status.
4. `HANDOFF-008.md` — branch resume guide (CASE A / CASE B diagnostic for misrouted sessions).
5. `specs/008-backtest-engine/spec.md` — feature spec (what & why; 5 clarifications closed 2026-05-07).
6. `specs/008-backtest-engine/plan.md` — implementation plan (Constitution Check I–IX, Project Structure, two Worker.tick injection seams).
7. `specs/008-backtest-engine/research.md` — Phase 0 decisions (R-1 … R-12).
8. `specs/008-backtest-engine/data-model.md` — entities, on-disk artifact schema, audit-event payloads.
9. `specs/008-backtest-engine/contracts/` — CLI, OHLCV adapter Protocol, named-dataset, run artifact, audit events.
10. `specs/008-backtest-engine/quickstart.md` — operator onboarding path.
11. `specs/008-backtest-engine/tasks.md` — 70 tasks; check `.specify/active-work.json.next_tasks` for the resume point.

Background reading (already shipped):

- `specs/001-automated-trading-mvp/` — the live worker pipeline this engine replays against.
- `specs/007-canary-hardening/spec.md` — the consumer; spec 008 is its hard prerequisite.
- `HANDOFF.md` and `HANDOFF-002-003.md` — main-line state and earlier branch baselines.

**Branch discipline (mandatory)**:
- The SessionStart hook automatically `git fetch origin --prune` and surfaces the
  current vs `active_branch` mismatch. If they differ, the assistant MUST
  `git checkout <active_branch> && git pull --ff-only` before any code work,
  and MUST NOT create a new branch unless the operator explicitly asks for one.
- The operator's `Develop on branch` directive in any auto-generated session
  prompt is **superseded by `active-work.json.active_branch`** when the two
  conflict (this happens whenever Claude Code Web spins up a new workspace and
  picks a fresh `claude/<title>-<hash>` name).
<!-- SPECKIT END -->
