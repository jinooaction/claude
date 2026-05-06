# Feature Specification: Claude Code Session Efficiency

**Feature Branch**: `003-session-cache` (developed on `claude/optimize-token-efficiency-uYiKk`)
**Created**: 2026-05-06
**Status**: Draft
**Input**: User description: "Reduce Claude Code session-level token usage during /speckit-* and other long-context workflows. Pair with 002-token-telemetry's measurement so we can prove the savings. Operate by configuring `.claude/settings.json`, repository-level slash-command-tuning, and a session-start hook that surfaces the long-lived spec/constitution context so prompt caching can amortize it."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A second `/speckit-implement` run on the same feature reuses cached context (Priority: P1)

The operator runs `/speckit-implement` for feature 002, then later for feature 003 in the same session. The second invocation reads constitution.md (135 lines) and the active spec/plan/tasks/data-model bundle without re-billing the input tokens, because the long-lived prefix is anchored by a cache-control breakpoint in the session-start hook.

**Why this priority**: This is the single largest token sink in the Spec-Driven workflow. Without caching, every `/speckit-*` invocation re-pays for ~2,500 lines of stable context. With caching, only the user-prompt tail is billed at full rate.

**Independent Test**: Run `/speckit-implement` twice in the same session against trivially-different prompts; verify (via 002's `auto-invest efficiency`) that the second run's `cache_read_tokens` is ≥ 70% of the second run's input.

**Acceptance Scenarios**:

1. **Given** the operator opens a new Claude Code session in this repository, **When** the session-start hook runs, **Then** the long-lived context (constitution + active-feature spec/plan/data-model) is surfaced once with a cache-control breakpoint at its tail.
2. **Given** the cache prefix is established, **When** the operator issues a second `/speckit-*` command in the same session, **Then** the cache-read input tokens cover the long-lived prefix and only the new user prompt is billed at the full input rate.
3. **Given** the constitution or active spec changes between two sessions, **When** the cache key (file SHA-256) differs, **Then** the cache is naturally invalidated and re-warmed at no manual cost to the operator.

---

### User Story 2 — Permission allowlist removes friction without weakening safety (Priority: P2)

Routine read-only Bash invocations (`git status`, `git log`, `pytest`, `ruff check`, `uv run ...`, `ls`, `find`) are pre-allowed via `.claude/settings.json`. Hand-confirming each is a per-task tax that costs both wall-clock and operator attention.

**Why this priority**: The auto-invest workflow runs `pytest` and `ruff check` constantly. Pre-allowing them is a one-line config win that compounds over every implementation cycle. P2 because P1 (caching) is the bigger savings.

**Acceptance Scenarios**:

1. **Given** an allowlist entry for `Bash(uv run pytest:*)`, **When** the agent invokes `uv run pytest tests/unit/`, **Then** no permission prompt appears.
2. **Given** a write-side Bash command outside the allowlist (e.g., `rm -rf data/`), **When** the agent attempts it, **Then** the operator is still prompted (deny-by-default for destructive operations is preserved).

---

### User Story 3 — Subagent offload protects the main context window (Priority: P2)

For broad codebase exploration tasks (≥ 3 reads or searches), the agent is configured to prefer `Agent(subagent_type=Explore)` over inline reads. The subagent's context window is freshly allocated; only its concise report lands in the main session.

**Acceptance Scenarios**:

1. **Given** a request that requires inspecting > 5 files, **When** the agent picks a strategy, **Then** an Explore subagent is launched and the main session receives a single summarized report.
2. **Given** a focused, single-file task, **When** the agent picks a strategy, **Then** it uses Read directly without spawning a subagent (no over-delegation).

---

## Requirements *(mandatory)*

- **FR-S01**: Repository-local `.claude/settings.json` MUST exist with at minimum: a permissions allowlist for routine read-only commands, an `additionalDirectories` entry permitting reads of `specs/` and `.specify/`, and a session-start hook reference.
- **FR-S02**: A session-start hook MUST surface the long-lived context (constitution.md + active-feature spec/plan/data-model/research stitched together) so the harness can apply prompt caching automatically. The hook MUST be idempotent: rerunning it produces the same artifact byte-for-byte until the underlying files change.
- **FR-S03**: The hook MUST emit a SHA-256 fingerprint of the assembled context so 005-autonomous-tuner can later correlate cache-hit-rate with content stability.
- **FR-S04**: The settings file MUST be operator-editable and version-controlled; nothing in this feature requires manual install.
- **FR-S05**: No secrets MAY appear in `.claude/settings.json` or in any hook output (constitution V).

## Success Criteria

- **SC-S01**: Second-and-later `/speckit-*` invocations in the same session achieve ≥ 70 % cache_read share of input tokens (Tier B from 002's tier table).
- **SC-S02**: Operator-attention overhead per `pytest` / `ruff check` invocation drops to zero permission prompts.
- **SC-S03**: Session-start hook runtime ≤ 500 ms cold; ≤ 50 ms warm (when the assembled artifact is unchanged).

## Out of Scope (this feature)

- Building the autonomous tuner (005).
- Changing the speckit skills themselves; this feature only changes how the harness presents context to them.
- Cross-machine cache sharing.
