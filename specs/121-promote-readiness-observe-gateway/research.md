# Research: Promote Readiness Observe Gateway

## Decision: Route promotion readiness through `observe promote-readiness`

**Rationale**: Current production evidence shows the server gateway refuses the raw command `cd /opt/auto-invest && /usr/local/bin/uv run auto-invest promote-check ...` with exit 126. Other read-only evidence paths already use fixed `observe ...` commands, so promotion readiness should join that pattern.

**Alternatives considered**:
- Allow raw shell commands again: rejected because that reverses the SSH hardening.
- Run promotion readiness locally in GitHub Actions: rejected because readiness depends on the production audit database.
- Ignore the sidecar: rejected because a stale or broken readiness surface weakens the operator's ability to understand promotion status.

## Decision: Add no variable inputs to the gateway command

**Rationale**: `promote-check` currently uses fixed production paths and fixed capital in the workflow. Keeping `observe promote-readiness` argument-free prevents a caller from changing database paths, rules paths, capital, mode, or output format over SSH.

**Alternatives considered**:
- Accept `observe promote-readiness <capital>`: rejected because capital is a safety-sensitive value and should not be user-controlled through this read path.
- Accept arbitrary CLI flags and validate them: rejected because the simpler fixed command is safer and sufficient.

## Decision: Preserve exit-code semantics

**Rationale**: `promote-check` uses exit 0 for READY and exit 1 for NOT READY. The workflow already captures nonzero exit codes and publishes the sidecar. Keeping that contract means not-ready evidence remains visible and does not look like a gateway failure.

**Alternatives considered**:
- Force helper exit 0 after writing JSON: rejected because it would blur READY and NOT READY.
- Treat exit 1 as infrastructure failure: rejected because not-ready is a valid promotion-gate result.

## Decision: Test the boundary with static workflow and helper assertions

**Rationale**: The highest-risk failure is accidentally reopening raw SSH command execution or allowing live-order behavior through the helper. Static tests can prove the workflow uses only the fixed command and that the helper/gateway do not include unsafe primitives.

**Alternatives considered**:
- Only wait for the next scheduled sidecar: rejected because it would detect the issue late and would not prove the boundary.
- Add a live server smoke in unit tests: rejected because local tests must not depend on secrets or the production host.

## Decision: Refresh root-owned gateway/helpers from `origin/main` during deploy

**Rationale**: Post-merge verification showed the repository fix was deployed, but the server still refused `observe promote-readiness`. The installed gateway and observation helper are root-owned files created by the SSH boundary repair script, while the normal deploy state machine runs unprivileged. A root-only deploy pre-step can install the latest fixed-command gateway/helpers from `origin/main` before the normal deploy starts, closing this drift without reintroducing raw remote shell access.

**Alternatives considered**:
- Manually repair the server through the provider console: rejected as the primary path because the same drift would recur after future allowlist changes.
- Add raw SSH fallback to the workflow: rejected because it would bypass the forced-command gateway.
- Move all deploy work to root: rejected because the current unprivileged deploy state machine is the safer default and should remain the main path.
- Refresh from the working tree after deploy: rejected because the gateway must be current before the workflow relies on it, and the clean-tree deploy state machine should not be responsible for root-owned helper installation.
