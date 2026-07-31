# Implementation Plan: Promote Readiness Observe Gateway

**Branch**: `codex/promote-readiness-observe-gateway` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/121-promote-readiness-observe-gateway/spec.md`

## Summary

The latest `promote-readiness` sidecar initially failed with `ssh_exit=126` because the workflow sent a raw remote `promote-check` shell command, while the production server correctly accepts only fixed forced-command gateway verbs. The first repair routed the report through `observe promote-readiness`, but post-merge verification showed the installed root-owned gateway/helpers on the server were still stale. This feature now also refreshes those fixed-command files from `origin/main` during deploy, while proving that no live order, arming, capital, whitelist/caps, secret, audit-log, or promotion action is opened.

## Technical Context

**Language/Version**: Bash for GitHub workflow and server helper; Python 3.11 for existing CLI and tests
**Primary Dependencies**: Existing GitHub Actions workflow pattern, SSH forced-command gateway, existing `auto-invest promote-check` CLI
**Storage**: Git-published sidecar Markdown only; no database migration
**Testing**: pytest, ruff, shell syntax checks, SDD/handoff probes
**Target Platform**: GitHub Actions and the production host `gh-deploy` forced-command gateway
**Project Type**: Trading automation repository with server-side deployment helpers
**Performance Goals**: Promotion readiness sidecar should publish within the existing 10-minute workflow timeout
**Constraints**: No broker order submission, no live arming, no capital allocation, no whitelist/caps changes, no secret reads or writes, no arbitrary shell through SSH
**Scale/Scope**: One workflow, one forced-command gateway allowlist entry, one observation helper command, one deploy pre-step for helper refresh, focused tests, and handoff update

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|-----------|-------|--------|
| I. Position sizing & exposure limits | No sizing rule or order path is changed. | PASS |
| II. Deny-by-default whitelist | No symbol, account, order-type, or session allowlist is changed. | PASS |
| III. Defined judgment points | No LLM judgment point or always-on model call is added. | PASS |
| IV. Append-only audit + reconciliation | `promote-check` reads existing evidence; this feature must not mutate audit rows. | PASS |
| V. Secret isolation | No secret value is read, printed, or written; workflow uses existing secret references only. | PASS |
| VI. Backtest -> Canary -> Full Live | This reports readiness only and does not promote to full live. | PASS |
| VII. External API robustness | No new external API call is added. | PASS |
| VIII.A No market-hours deploys | Repository merge may trigger guarded deploy; the feature itself is read-only and does not bypass deploy policy. | PASS |
| IX. Self-modification boundary | No constitution or kernel manifest path is changed. | PASS |
| X. Measurement-driven autonomous growth | The repair restores measurement visibility while keeping deploy distinct from live money. | PASS |

Risk grade: **3**. The change touches the server SSH command boundary, but only by adding one fixed read-only observation verb. It does not widen the money path.

## Project Structure

### Documentation (this feature)

```text
specs/121-promote-readiness-observe-gateway/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── promote-readiness-observe-gateway.md
└── tasks.md
```

### Source Code (repository root)

```text
.github/workflows/
└── promote-readiness.yml

deploy/
├── auto-invest-deploy.service
├── repair-ssh-boundary.sh
├── refresh-ssh-boundary-helpers.sh
└── observe-on-instance.sh

tests/unit/
├── test_observation_gateway_workflows.py
├── test_ssh_boundary_repair.py
├── test_sync_units.py
└── test_spec_026_readiness.py
```

**Structure Decision**: Keep the repair inside the existing workflow, deploy unit, and forced-command helper files. Do not introduce a second SSH path or a privileged workflow.

## Complexity Tracking

No constitution violation is required. The added complexity is one fixed observation command plus a deploy-time refresh of root-owned helper files; it is justified because the existing raw SSH command and then stale installed gateway were both correctly refused by the hardened server boundary.
