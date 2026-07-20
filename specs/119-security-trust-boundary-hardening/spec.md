# Feature Specification: Security Trust Boundary Hardening

**Feature Branch**: `codex/security-trust-boundary-hardening`
**Created**: 2026-07-21
**Input**: External vulnerability review of GitHub Actions, deployment, broker auth, order routing, and public sidecar paths.

## User Scenarios & Testing

### Story 1 - Fail Closed Remote Operations (Priority: P0)

As the operator, I need GitHub-triggered remote operations to refuse unsafe SSH, shell input, market state, or root escalation so repository or Actions compromise does not become server-wide or live-trading compromise.

**Acceptance**:
- Workflows pin third-party Actions by full commit SHA.
- SSH workflows require a pre-provisioned host key and do not accept a new host key silently.
- Workflows reject root SSH users at runtime.
- Workflow dispatch numeric values used in remote commands are validated before use.
- go-live only proceeds when market state is explicitly closed and the target revision matches.

### Story 2 - Preserve Order and Risk Safety While Degraded (Priority: P0)

As the operator, I need uncertain orders and missing market data to stop new risk while still allowing verified exposure-reducing sells.

**Acceptance**:
- Stale BUY intents or submitting orders block new BUY decisions until reconciled.
- Uncertain broker-order recovery requires stronger matching than symbol, side, and quantity alone.
- Halt and per-trade caps can allow verified reduce-only sells but reject oversells.
- Missing marks for open positions put the system into a degraded mode that blocks new BUY exposure.

### Story 3 - Keep Evidence Public-Safe (Priority: P1)

As the operator, I need public sidecar branches to keep proof of operation without publishing account-scale, order, token, or host-sensitive details.

**Acceptance**:
- Public sidecar writers redact sensitive account, token, NAV, capital, order, and host patterns before publishing.
- Tests prove representative public logs are redacted.

### Story 4 - Make Local Secret and Deploy State Atomic (Priority: P1)

As the operator, I need local token cache and deploy locks to be written atomically so a crash, symlink, or concurrent process cannot create ambiguous state.

**Acceptance**:
- Token cache parent directories are private, cache files are `0600`, symlinks are refused, and writes use same-directory atomic replace.
- Deploy locks are acquired with a kernel-level lock and released by closing the held lock.

## Requirements

- **FR-001**: Remote workflow SSH must require fixed known-host material and fail if `VULTR_SSH_USER` is `root`.
- **FR-002**: `capital` and similar remote numeric inputs must match a narrow decimal schema before any remote command interpolation.
- **FR-003**: go-live must fail closed for `OPEN`, `UNKNOWN`, empty, or mismatched revision states and must restore the full environment backup on failure.
- **FR-004**: Canary promotion must require both candidate code SHA and ruleset SHA on the matched `CANARY_PASSED` row.
- **FR-005**: Deploy lock acquisition must be atomic across competing processes.
- **FR-006**: Public sidecar logs must pass a repository allowlist redaction step before commit.
- **FR-007**: Broker token cache writes must be private, symlink-safe, and atomic.
- **FR-008**: Stale BUY `INTENT`/`SUBMITTING` states must block new BUY orders until reconciled.
- **FR-009**: Broker unknown-submission recovery must compare order type, price when known, and submit-time proximity when broker data supports it.
- **FR-010**: Halt and per-trade caps must distinguish exposure-increasing orders from verified reduce-only orders.
- **FR-011**: Missing current marks for open positions must block new BUY risk.

## Non-Goals

- Do not place real orders or change live capital allocation.
- Do not rotate production secrets from this repository-only session.
- Do not delete public history already published before this feature.
- Do not change the constitution or kernel manifest.

## Risk Classification

Grade 3 safety-boundary change. This touches K1 risk gates and K4 audit payloads, plus deployment and workflow controls. It does not execute real orders, does not move capital, and does not change `.specify/memory/constitution.md` or `.specify/memory/kernel.toml`.

## Success Criteria

- Focused unit and integration tests cover each mitigated vulnerability.
- Full `uv run pytest`, `uv run ruff check src tests`, strict harness, and HANDOFF fact checks pass before merge.
- PR body records risk grade, removed/reduced behavior, replacement controls, validation, and rollback path.
