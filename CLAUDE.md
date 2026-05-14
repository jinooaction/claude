# Autonomous workflow policy (project default — overrides harness defaults)

This project's working agreement is **autonomous progression**, not "wait for the operator at every step". The harness's stock instruction "do NOT create a pull request unless the user explicitly asks" is OVERRIDDEN here for the cases below. The operator (mason) authorised this on 2026-05-13 to fix a recurring cross-session discoverability problem.

## When a session starts

Every fresh session MUST, before doing other work, run this discovery sequence:

```bash
# 1. See every claude/* branch on origin (in-flight work lives here).
git fetch origin
git ls-remote --heads origin 'claude/*' | awk '{print $2}'

# 2. See open PRs (the canonical discoverability surface).
#    via mcp__github__list_pull_requests owner=jinooaction repo=claude state=open

# 3. Look for HANDOFF-*.md on EVERY discovered branch (not just current).
#    e.g. git show origin/<branch>:HANDOFF-008.md
```

If a HANDOFF file points at active work, `git checkout` that branch BEFORE generating a plan or asking the user what to do. Do not invent a new branch off main when there's an in-flight branch the previous session was using.

## When the work is in-flight across sessions

Open a PR (draft is fine) so the work is discoverable from any branch via `mcp__github__list_pull_requests`. PR descriptions are the project's "single source of truth for in-flight state" — they survive branch isolation. Update the PR body when the state changes.

When constitution principle IX.B-1 says "operator approval at merge", the PR review IS that approval surface. Mark the relevant commit hash in the PR body so the operator can spot-check exactly the change that needs IX.B-1 review (e.g., the K4 commit `bc47361` for spec 008).

## What this DOES NOT change

- The constitution (v2.0.0) is still non-negotiable. PRs that propose Kernel modifications STILL require explicit operator review per IX.B-1.
- "No force-push to main" still applies.
- "No skip hooks" still applies.
- Live broker / live LLM safety contracts in every spec still apply.

The change is narrowly: PRs are now part of the autonomous workflow, not a permission-gated escalation.

## Autonomous merge — IX.B-1 approval channel

`mcp__github__merge_pull_request` is part of the autonomous workflow too. The operator (mason) authorised this on 2026-05-14 as a follow-on to the PR-creation policy above. Auto-merge is permitted under these rules:

1. **The operator's chat-channel approval IS the IX.B-1 "operator approval at merge".** When the operator instructs the session to merge (explicit Korean/English request, e.g. "머지해", "merge it", "ship it"), that instruction satisfies the constitution's explicit-operator-approval requirement for any Kernel touch in the PR. The audit trail is: the chat transcript + the PR description that pin-points the Kernel-touching commit hash.
2. **The session MUST still call out which commit is the Kernel touch BEFORE merging** so the operator's approval is informed, not blind. This is the same discipline the manual-review flow demanded — just now it's a chat exchange instead of a PR review click.
3. **Use merge method `merge` (not squash, not rebase) when the PR contains a Kernel touch.** The K4 commit hash MUST survive into `main`'s history so future forensic queries can locate it. Squash would erase it.
4. **Re-run tests + lint immediately before invoking `merge_pull_request`.** Failing tests on the head SHA = abort the merge, fix forward.
5. **IX.B-2 still gates *autonomous* merge (i.e. merges initiated by the tuner without operator instruction).** The hardened canary (spec 007) is the only path for those. This section is about *operator-instructed* merges, which are a different category.
6. **Mark draft PRs ready before merging** via `mcp__github__update_pull_request draft=false`. Some merge configurations refuse draft PRs.

After a successful merge, the session SHOULD:

- Confirm the merge commit on `main` and report its hash.
- Update any HANDOFF-*.md to reflect the new `main` baseline (the in-flight pointer is no longer needed for the merged work).
- Delete the feature branch ONLY if explicitly asked; in-flight branches that still have unfinished tasks (e.g. spec 008's T016-T041) stay alive.

## What this DOES NOT change (autonomous merge edition)

- The constitution itself is K-meta. ANY change to `.specify/memory/constitution.md` or `.specify/memory/kernel.toml` is a kernel touch with extra weight — the operator's chat approval STILL counts but the session SHOULD explicitly call out "this changes the safety perimeter" so the operator can object before merge.
- `main` protection (no force-push, no direct push) still applies. Merges land via PR, not via push.
- Live trading contracts are unaffected — a merge that introduces a regression in `risk/gates.py` (K1) would still need to pass spec 007's hardened canary before any *autonomous* deploy could promote it. Operator-instructed merges land the code but don't auto-deploy.

---

<!-- SPECKIT START -->
Active feature: `specs/008-backtest-engine/` (clarified 2026-05-13, plan ready)

Read in order when working on this feature:

1. `.specify/memory/constitution.md` — non-negotiable principles (v2.0.0, Kernel + IX).
2. `.specify/memory/kernel.toml` — machine-readable Kernel manifest (this feature touches K4 once, additively).
3. `specs/008-backtest-engine/spec.md` — feature spec (Why, scenarios, FRs, clarifications session 2026-05-13).
4. `specs/008-backtest-engine/plan.md` — implementation plan (technical context, constitution check, project structure).
5. `specs/008-backtest-engine/research.md` — Phase 0 decisions (R-B1 … R-B12).
6. `specs/008-backtest-engine/data-model.md` — entities, audit-event payloads, on-disk layout.
7. `specs/008-backtest-engine/contracts/` — operator-facing contracts (CSV ingest, CLI, run-json, data-source protocol).
8. `specs/008-backtest-engine/quickstart.md` — operator onboarding for backtest.

Tasks generated by `/speckit-tasks` will live at `specs/008-backtest-engine/tasks.md`.

Branch convention: SDD work for this spec lives on `claude/continue-work-ID7Ec`; spec dir name is `008-backtest-engine`. Use `SPECIFY_FEATURE=008-backtest-engine` when the spec-kit scripts ask for a feature branch name.

Background context still relevant from earlier specs:
- `HANDOFF.md` — main-line baseline (spec 001 shipped, KIS verified).
- `HANDOFF-002-003.md` — branch state through 002/003/004/005/006/007 stubs + v2.0.0 constitution + K4 introduction.
- Specs 002 (telemetry, shipped), 003 (session-cache, shipped), 004 (judgment, stub), 005 (autonomous-tuner, stub), 006 (deploy automation, kernel guard shipped + runner pending), 007 (hardened canary, stub — depends on this feature).
<!-- SPECKIT END -->
