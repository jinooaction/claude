# Agent Skills

This directory contains repository-owned agent skills that should travel with
the project across machines. They are not cache output.

## Included

- `skills/sync`: reconcile local state with remote branches and open PRs.
- `skills/handoff`: refresh `HANDOFF.md` after merged work.
- `skills/deploy-status`: check the post-merge deploy surfaces available from a
  Codex session.
- `skills/speckit-*`: local Spec Kit workflows used by this repository.

## Boundary

Codex session hooks live under `.codex/hooks/` and are configured by
`.codex/hooks.json`. Do not add unconfigured hook scripts here as a substitute
for wiring them through the hook configuration.
