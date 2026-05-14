# Autonomous workflow policy (project default — overrides harness defaults)

This project's working agreement is **autonomous progression**, not "wait for the operator at every step". The harness's stock instruction "do NOT create a pull request unless the user explicitly asks" is OVERRIDDEN here for the cases below. The operator (mason) authorised this on 2026-05-13 to fix a recurring cross-session discoverability problem.

## No permission-checking mid-task (the supreme rule, v3.1.0)

Under constitution v3.0.0 IX.D Operator Autonomy Supremacy, the operator
explicitly does NOT want to be asked "should I continue?" or "want me to
keep going?" at task boundaries. The default for THIS project, beyond
v3.0.0's merge-stage autonomy, is:

**Once the operator has given an instruction like "계속해" / "continue" /
"이어서" / "fix the bug" / "ship spec 008", the session runs to completion
of THAT instruction without prompting for permission at any intermediate
step.** Completion of an instruction means:

  - "Continue / 계속해" + a referenced active feature (spec/HANDOFF/PR) →
    keep going until **every remaining task in tasks.md** for that feature
    is complete (or until a real blocker is hit). Do NOT stop at "natural
    pause points", "checkpoints after a slice", or because tests pass —
    green tests + lint clean ARE the verification; that's the signal to
    push and start the next task, not the signal to ask permission.
  - "Fix X" → keep going until X is fixed AND tests/lint are green AND
    pushed AND (if appropriate) the PR is updated.
  - "Ship / merge / merge it" → run through the autonomous-merge channel
    in this file without further confirmation.

**Per-task-batch checkpoint summaries to chat are FINE and encouraged**
(short status updates the operator can read passively). **Permission
questions ("want me to continue?", "should I keep going?", "or stop here
so you can review?") are NOT fine** — they re-introduce the exact
synchronous-handoff overhead IX.D eliminated. If the operator wants to
pause they will say so; silence = keep going.

### Legitimate reasons to pause and ASK before proceeding

These are narrow. If the situation is not one of these, do not ask.

  1. **Spec ambiguity with no documented choice.** The spec text + research
     + HANDOFF do not pick between multiple reasonable interpretations,
     AND choosing wrong would require non-trivial rework. (e.g. Path A vs
     Path B for the replay engine BEFORE HANDOFF-008 documented Path B.
     Once documented, you do not ask again.)
  2. **Destructive / irreversible action** outside the normal workflow:
     force-push to `main`, drop a SQLite table, delete an audit-log row,
     `git reset --hard` over uncommitted work, anything that violates
     constitution principles I-VII or VIII.A.
  3. **External-effect action** the user did not authorise in the running
     instruction: posting on a public PR you did not open, opening an
     issue against another repo, paying for an external service, sending
     a Slack/email.
  4. **The user has actively requested a pause** in this conversation
     (explicit "stop", "wait", "잠깐", "hold").

Anything else — including "this is a long task and I've been working a
while" or "the next task is structurally important" — is NOT a reason
to ask. Just push the slice and keep going. The PR is the operator's
review surface; commits are the operator's checkpoint granularity.

### What the session SHOULD do at each task boundary

  1. Run tests + lint on the slice you just finished.
  2. If green: commit with a descriptive message, push, update TodoWrite.
  3. If you have a PR open for this work, update the PR body so it
     reflects the new task count and the latest commit hash.
  4. Move to the next pending task in tasks.md immediately. Do not write
     a "want to continue?" message — write a one-line "pushed X, starting Y"
     status update if anything, then continue.
  5. At the end of the whole instruction (e.g. when the last task in
     tasks.md is done OR a real blocker is hit), give the operator a
     concise final summary — that is the next interaction point, not
     a per-slice checkpoint.

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

- The trading-safety invariants in constitution principles I–VII and VIII.A are still non-negotiable (position caps, whitelist, LLM-only-at-judgment-points, append-only audit, secret isolation, Backtest→Canary→Full, external-API robustness, no-market-hours-deploys). Spec 007's hardened canary remains the production-deploy gate that defends them at the live-worker boundary.
- "No force-push to main" still applies.
- "No skip hooks" still applies.
- Live broker / live LLM safety contracts in every spec still apply.

The change is narrowly: PRs are now part of the autonomous workflow, not a permission-gated escalation.

## Autonomous merge — IX.D supremacy channel (v3.0.0)

`mcp__github__merge_pull_request` is part of the autonomous workflow too. The operator (mason) authorised this on 2026-05-14, and constitution v3.0.0 enshrined the principle as IX.D Operator Autonomy Supremacy. Auto-merge is permitted under these rules:

1. **The session's reasoning trace + the PR description ARE the IX.B (and any other) approval record.** When the operator instructs the session to merge (chat instruction, e.g. "머지해", "merge it", "ship it") OR when the session is acting on an operator-instructed plan, the merge proceeds. No second human in the loop is required, including for Kernel touches.
2. **The session MUST still call out which commit is the Kernel touch BEFORE merging** so the forensic record is informed, not blind. This is now an audit-quality discipline, not a procedural gate.
3. **Use merge method `merge` (not squash, not rebase) when the PR contains a Kernel touch.** The Kernel-touch commit hash MUST survive into `main`'s history so `git log` forensic queries can locate it. Squash would erase it.
4. **Re-run tests + lint immediately before invoking `merge_pull_request`.** Failing tests on the head SHA = abort the merge, fix forward.
5. **IX.B-2 still gates *autonomous* merge (i.e. merges initiated by the tuner without operator instruction).** The hardened canary (spec 007) is the only path for those. This section is about *operator-instructed* merges, which are a different category.
6. **Mark draft PRs ready before merging** via `mcp__github__update_pull_request draft=false`. Some merge configurations refuse draft PRs.

After a successful merge, the session SHOULD:

- Confirm the merge commit on `main` and report its hash.
- Update any HANDOFF-*.md to reflect the new `main` baseline (the in-flight pointer is no longer needed for the merged work).
- Delete the feature branch ONLY if explicitly asked; in-flight branches that still have unfinished tasks (e.g. spec 008's T016-T041) stay alive.

## What this DOES NOT change (autonomous merge edition)

- The constitution itself is K-meta. ANY change to `.specify/memory/constitution.md` or `.specify/memory/kernel.toml` MUST include the literal string "this changes the safety perimeter" in the commit message so `git log --grep="this changes the safety perimeter"` finds every such event. The merge still proceeds autonomously under IX.D.
- `main` protection (no force-push, no direct push) still applies. Merges land via PR, not via push.
- Live trading contracts are unaffected — a merge that introduces a regression in `risk/gates.py` (K1) is NOT a deploy. Production-deploy still requires spec 007's hardened canary (when it ships) or operator-instructed deploy. Merging the code lands the bits; it does NOT route real orders.

---

<!-- SPECKIT START -->
Active feature: `specs/008-backtest-engine/` (clarified 2026-05-13, plan ready)

Read in order when working on this feature:

1. `.specify/memory/constitution.md` — non-negotiable principles (**v3.0.0**, IX.D Operator Autonomy Supremacy).
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
