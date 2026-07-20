# Research: Security Trust Boundary Hardening

## Decisions

- Use workflow-level guard scripts instead of duplicating shell snippets. This makes the fail-closed behavior testable and reusable.
- Pin known third-party Actions to resolved commit SHAs: `actions/checkout@11d5960a326750d5838078e36cf38b85af677262`, `astral-sh/setup-uv@caf0cab7a618c569241d31dcd442f54681755d39` for v3, and `astral-sh/setup-uv@d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86` for v5.
- Refuse root SSH in GitHub workflows as an immediate repository-side stopgap. Full `gh-deploy` forced-command deployment remains an operator/server migration.
- Require explicit code and ruleset hashes on canary pass evidence. Legacy rows remain readable but cannot approve a deployment.
- Use `fcntl.flock` for deploy locking because it is process-lifetime tied and avoids PID-file creation races.
- Preserve public sidecar proof but redact high-risk operational details before commit.

## Alternatives Rejected

- Secret rotation from the repository session: rejected because real root SSH keys and server `authorized_keys` are outside the repo and require operator-controlled credential actions.
- Accepting broker recovery matches with only symbol/side/quantity: rejected because same-day manual or parallel orders can collide.
- Blanket allowing all sells under halt: rejected because it can permit oversell and create unintended short exposure.
