<!--
Sync Impact Report
==================
Version change: 1.0.0 -> 1.1.0  (MINOR: principle VIII materially expanded for deploy automation)
Modified principles:
  VIII. Change Discipline — split into 8.A (no market-hours deploys, unchanged in spirit) and 8.B (automated-deploy requirements: market-hours guard, audit events, health-check gate, rollback obligation). Spirit preserved; guidance materially expanded.
Added sections: none (expansion is inside principle VIII).
Removed sections: n/a
Templates requiring updates:
  ✅ .specify/memory/constitution.md  (this file)
  ✅ specs/006-deploy-automation/spec.md  (new feature; consumes the 8.B clauses)
  ⚠ specs/001-automated-trading-mvp/plan.md  — Constitution Check table still references VIII as a single block; left as-is because v1 was authored under v1.0.0 and is shipped. New plans MUST cite VIII.A / VIII.B explicitly.
Follow-up TODOs:
  - Reconsider adding an explicit daily/cumulative loss-limit principle (deliberately omitted; carried over from v1.0.0).
  - At /speckit-specify for 004 (LLM judgment points), declare per-judgment-point cost + latency budgets and confirm VIII.B audit events still cover an LLM-bearing deploy.

Sync Impact Report (v1.0.0 -> 1.0.0)
==================
Version change: (none) -> 1.0.0  (initial ratification)
Modified principles: n/a (initial draft)
Added sections:
  - Core Principles (8 principles)
  - Investment Domain Constraints
  - Development Workflow
  - Governance
Removed sections: n/a
Templates requiring updates:
  ✅ .specify/memory/constitution.md  (this file)
  ⚠ .specify/templates/plan-template.md   — needs a "Constitution Check" section that maps to principles I-VIII (to be added at first /speckit-plan run)
  ⚠ .specify/templates/spec-template.md   — needs investment-domain fields (asset universe, risk caps, judgment points) (to be added at first /speckit-specify run)
  ⚠ .specify/templates/tasks-template.md  — needs task categories: risk-check, reconciliation, judgment-contract, audit-log (to be added at first /speckit-tasks run)
Follow-up TODOs:
  - Reconsider adding an explicit daily/cumulative loss-limit principle (deliberately omitted in v1.0.0 at user request; non-standard for professional trading systems).
  - At /speckit-specify, declare concrete numeric values for: per-trade size cap, per-symbol exposure cap, global exposure cap, canary capital share.
-->

# auto-invest Constitution

## Core Principles

### I. Position Sizing & Exposure Limits (NON-NEGOTIABLE)

Every order MUST pass position-sizing checks before submission:

- **Per-trade cap**: a single order MUST NOT exceed a configured percentage of total capital.
- **Per-symbol cap**: total exposure to one symbol MUST NOT exceed a configured percentage of total capital.
- **Global exposure cap**: total deployed capital MUST NOT exceed a configured percentage, preserving a cash buffer.

Concrete values are declared in the spec, but the existence of all three caps is non-negotiable. Any code path that places an order without enforcing these caps is a bug.

**Rationale**: Disciplined position sizing is the single most important factor in long-term survival of any trading system. It bounds the worst-case impact of bugs, bad data, or wrong judgment calls before any other safeguard fires.

### II. Deny-by-Default (Whitelist)

The system MUST reject all trading operations unless they appear on an explicit allowlist:

- Tradeable symbols are maintained as a versioned whitelist; unknown tickers are auto-rejected.
- Order types (limit, market, stop, etc.) MUST be opt-in per environment.
- Trading sessions (regular hours, extended hours) MUST be opt-in.
- Account IDs MUST be opt-in; orders against any other account are rejected.

**Rationale**: Typos, runaway loops, and malformed LLM output are common failure modes. Whitelisting turns a class of catastrophic accidents into harmless rejections.

### III. Claude Is Invoked Only at Defined Judgment Points

LLM calls are restricted to pre-declared decision points described in the spec:

- Per-tick, per-quote, or per-bar LLM calls are forbidden.
- Each judgment point MUST declare: trigger condition, input contract, output schema, latency budget, cost budget.
- Every call MUST log: timestamp, inputs, prompt, response, decision taken, downstream effect.

**Rationale**: Without these constraints, LLM cost spirals and decision lineage becomes unauditable. Treating the LLM as a bounded oracle (rather than an always-on reasoner) keeps the system deterministic where it can be.

### IV. Append-Only Audit Log + Daily Reconciliation

- Every order, fill, cancellation, error, and judgment call MUST be persisted to an append-only log. Mutating prior records is forbidden.
- At least once per trading day, internal positions and cash MUST be reconciled against the broker's reported state.
- Any unresolved mismatch MUST automatically halt new order submission until manually cleared with a logged justification.

**Rationale**: Append-only history enables post-mortem analysis. Daily reconciliation catches data corruption, orphan orders, and partial-fill misaccounting — all routine failure modes of live trading systems.

### V. Secret Isolation

- API keys, account numbers, refresh tokens, and access tokens MUST NEVER be committed to the repository.
- Secrets are loaded from environment variables or a secret manager at runtime only.
- Logs, error traces, and outbound telemetry MUST mask sensitive values.

**Rationale**: A leaked KIS app key allows unauthorized trading on the user's real account. Treat secrets as tier-0 assets.

### VI. Staged Rollout: Backtest → Canary (Live, Small) → Full Live

New strategies and material changes (parameter shifts, model swaps, prompt edits) MUST progress through:

1. **Backtest**: passes predefined acceptance metrics on out-of-sample data.
2. **Canary**: live trading with capital capped at a configured small share (declared in spec) and run for a configured minimum duration.
3. **Full live**: promotion only after canary meets predeclared acceptance metrics.

Each promotion is an explicit decision recorded in the audit log. Material change to a previously-promoted strategy resets it to step 1.

**Rationale**: Backtests systematically overstate performance because they cannot model API failures, slippage, or partial fills. A bounded canary captures these without risking full capital.

### VII. External API Robustness

All calls to external services (KIS, market data vendors, Anthropic) MUST implement:

- Rate limiting that respects documented vendor limits.
- Retry with exponential backoff on transient errors, with a bounded retry count.
- Circuit breaker that disables the call site after sustained failures and re-enables only after a cooldown.
- Automated token refresh where applicable (e.g., KIS access tokens).

**Rationale**: External APIs fail. Without these protections a vendor outage cascades into invalid system state, missed cancels, and unbounded retries.

### VIII. Change Discipline

#### VIII.A — No Live Deploys During Market Hours

- Code changes affecting trading logic MUST NOT be deployed during US regular trading hours (NYSE/NASDAQ regular session). Declared emergency hotfixes are the only exception and MUST be logged.
- All changes go through Git with descriptive commit messages.
- Changes to this constitution MUST be a dedicated amendment commit with a version bump.

**Rationale**: Mid-session deploys are the single most reliable way to introduce undefined behavior into a running strategy.

#### VIII.B — Deploy Automation Requirements (added v1.1.0)

Operator-triggered automated deploys are explicitly permitted (and preferred over hand-typed deploys) when ALL of the following hold:

1. **Market-hours guard.** The automation MUST check the US market state via `exchange_calendars` (or equivalent) and refuse to proceed during regular hours. The guard MUST be in code, not in operator memory.
2. **Append-only audit events.** Every deploy attempt MUST emit:
   - `DEPLOY_STARTED` before any code, dependency, or schema change.
   - `DEPLOY_COMPLETED` on success after the post-deploy health check passes.
   - `DEPLOY_FAILED` on any abort, with `phase` and `reason` populated.
   These are first-class entries in the existing `audit_log` (principle IV); no parallel deploy log is permitted.
3. **Health-check gate.** After restarting the worker, the automation MUST poll for evidence of liveness for at least 30 s before declaring success: a fresh `WORKER_STARTED` audit row whose `ts_utc` is after `DEPLOY_STARTED.ts_utc`, no `ERROR` rows in the same window, and no `DATA_QUALITY_ISSUE` rows referencing telemetry mismatches.
4. **Rollback obligation.** On any health-check failure or migration failure, the automation MUST emit `DEPLOY_FAILED` and either (a) restore the previous worker version and confirm it boots, or (b) leave the system halted with a clear surfaced reason. The automation MUST NOT silently leave the worker stopped.
5. **Operator-triggered, not autonomous.** A scheduler that fires the deploy script at a fixed off-hours time IS still operator-triggered (the operator configured the schedule). Code that decides to deploy itself based on observed system state is NOT — that crosses into spec 005 (autonomous tuner) territory and is constrained by VIII.B clause 5 to PR-only proposals (L3 in 005).
6. **Secrets isolation preserved.** Deploy automation MUST NOT log, persist, or transmit any secret material; it inherits principle V.

**Rationale**: Manual deploys are the single most reliable way for principle VIII.A to be violated by accident. Automation that *enforces* the rule is therefore safer than the absence of automation. Treating deploys as audited operations puts them on the same forensic surface as orders and judgment calls (principle IV), so an unexpected change in worker behavior can be traced to a specific deploy event.

**Boundary with spec 005**: 005's autonomous tuner can *propose* changes (open a PR for L3 changes; auto-apply L1 changes outside market hours), but applying any L1 change still goes through the VIII.B deploy automation — there is exactly one path to a running worker.

## Investment Domain Constraints

- **Initial scope**: US listed equities (NYSE / NASDAQ / AMEX) traded via Korea Investment & Securities (KIS) OpenAPI.
- **Currency**: orders priced in USD; KRW↔USD conversion is tracked as a separate, observable risk.
- **Default order type**: limit orders only. Market orders require an explicit per-symbol opt-in with a documented liquidity justification recorded in the spec.
- **Out of scope (v1.0.0)**: derivatives, leverage, short selling, options, futures, crypto, domestic Korean equities.

## Development Workflow

- **Spec-Driven Development is mandatory.** Every feature flows through `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`. Code that has no upstream spec MUST NOT be merged.
- **Test gates.** Modules touching risk checks, order validation, reconciliation, or judgment-call contracts MUST have automated tests passing before merge.
- **Tooling.** `ruff check` and `pytest` MUST pass on every commit reaching `main`.
- **Branching.** Work happens on dedicated branches; `main` is always deployable.
- **Reviews.** Changes to risk-related modules require an explicit self-review against this constitution before merge, recorded in the commit message or PR description.

## Governance

This constitution supersedes all other practices, conventions, and ad-hoc decisions. When a principle conflicts with convenience or velocity, the principle wins.

**Amendments**: require (a) a dedicated commit modifying this file, (b) a version bump per the policy below, and (c) propagation to dependent templates (`plan-template.md`, `spec-template.md`, `tasks-template.md`).

**Versioning** (SemVer):
- **MAJOR**: principle removal or backward-incompatible redefinition.
- **MINOR**: principle addition or material expansion of guidance.
- **PATCH**: clarifications, wording, typo fixes.

**Compliance**: every `/speckit-plan` artifact MUST include a Constitution Check section verifying the plan does not violate principles I–VIII. Violations require explicit, written justification and a sign-off recorded in the audit log.

**Version**: 1.1.0 | **Ratified**: 2026-05-01 | **Last Amended**: 2026-05-06
