<!--
Sync Impact Report
==================
Version change: 1.1.0 -> 2.0.0  (MAJOR: kernel concept introduced; principle IX added; VIII.B-3 health window relaxed; VIII.B-5 redefined to permit autonomous merge outside the kernel)
Modified principles:
  VIII.B-3 — health-check minimum window 30 s -> 90 s. Material relaxation toward more conservative.
  VIII.B-5 — was "Operator-triggered, not autonomous". Replaced by reference to new principle IX. Backward-incompatible: code that read VIII.B-5 as forbidding autonomous deploys must now read it as deferring to IX's tiered model.
Added principles:
  IX. Self-Modification Boundary (NEW). Defines a Kernel (K1-K6 + K-meta) that cannot be modified by autonomous deploys; permits autonomous merge for everything outside the kernel subject to a hardened canary (spec 007). Rationale: closes the gap between operator's "autonomous execution & autonomous improvement" goal and the safety reality that a system able to rewrite its own safety rules has no safety guarantees.
Added sections:
  - Kernel manifest reference: `.specify/memory/kernel.toml` (machine-readable list of files protected by principle IX). Modifying this file is itself a kernel touch.
Templates requiring updates:
  ✅ .specify/memory/constitution.md (this file)
  ✅ .specify/memory/kernel.toml (new; machine-readable kernel manifest)
  ✅ specs/005-autonomous-tuner/spec.md (tiered authority extended with L4 = kernel)
  ✅ specs/006-deploy-automation/spec.md (deploy guard MUST consult kernel manifest)
  ✅ specs/007-canary-hardening/spec.md (new; defines the hardened-canary that gates autonomous merges)
Follow-up TODOs:
  - 007 implementation depends on a backtest engine (option D from main HANDOFF.md). Until 007 ships, autonomous merge stays disabled in production; the kernel guard still applies and the existing 10-day canary is the upper bound on autonomy.
  - Spec 001's plan.md Constitution Check still references VIII as a single block; left as-is (shipped under v1.0.0). New plans MUST cite VIII.A / VIII.B / IX explicitly.
  - Reconsider adding an explicit daily/cumulative loss-limit principle (carried over from v1.0.0).

Sync Impact Report (v1.0.0 -> 1.1.0)
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
3. **Health-check gate.** After restarting the worker, the automation MUST poll for evidence of liveness for at least 90 s (default; operator may configure a longer window per environment, never shorter) before declaring success: a fresh `WORKER_STARTED` audit row whose `ts_utc` is after `DEPLOY_STARTED.ts_utc`, no `ERROR` rows in the same window, and no `DATA_QUALITY_ISSUE` rows referencing telemetry mismatches. Rationale for 90 s: covers KIS auth refresh retry (~10 s), broker first-quote latency under load (~5 s), and at least two full asyncio loop ticks against a live market-data feed.
4. **Rollback obligation.** On any health-check failure or migration failure, the automation MUST emit `DEPLOY_FAILED` and either (a) restore the previous worker version and confirm it boots, or (b) leave the system halted with a clear surfaced reason. The automation MUST NOT silently leave the worker stopped.
5. **Tiered autonomy — see principle IX.** Whether a given deploy may be initiated autonomously (by spec 005's tuner) versus requires explicit human merge depends on whether the change touches the Kernel defined in principle IX. The market-hours guard, audit events, health-check gate, and rollback obligation (clauses 1–4) apply to ALL deploys, autonomous or human-initiated, equally.
6. **Secrets isolation preserved.** Deploy automation MUST NOT log, persist, or transmit any secret material; it inherits principle V.

**Rationale**: Manual deploys are the single most reliable way for principle VIII.A to be violated by accident. Automation that *enforces* the rule is therefore safer than the absence of automation. Treating deploys as audited operations puts them on the same forensic surface as orders and judgment calls (principle IV), so an unexpected change in worker behavior can be traced to a specific deploy event.

### IX. Self-Modification Boundary (NON-NEGOTIABLE, added v2.0.0)

The system is permitted — and encouraged — to evolve its own code, configuration, prompts, KPI thresholds, dependencies, schemas, and even its own non-kernel principles, as long as the modifications stay outside a small, explicitly enumerated **Kernel**. The Kernel is the safety perimeter that even the autonomous tuner (spec 005) MUST NOT cross without an explicit human merge.

#### IX.A — The Kernel

The Kernel is the closed set of files listed in the machine-readable manifest at `.specify/memory/kernel.toml`. As of v2.0.0 the Kernel comprises seven groups, each tied to one constitutional invariant:

| Group | Invariant | Why it must stay in the Kernel |
|-------|-----------|--------------------------------|
| **K1** | Position sizing caps (principle I) | Without K1, the system can autonomously raise its own leverage to ruinous levels. |
| **K2** | Deny-by-default whitelist (principle II) | Without K2, "auto-expand the whitelist" defeats the protection. |
| **K3** | LLM-only-at-judgment-points contract (principle III) | Without K3, autonomous deploys can re-define what "judgment point" means and uncap LLM cost. |
| **K4** | Append-only audit log (principle IV) | Without K4, all post-mortem and reconciliation evidence becomes forgeable. |
| **K5** | Secret isolation (principle V) | Without K5, a leaked KIS key is one autonomous deploy away. |
| **K6** | Market-hours deploy guard (principle VIII.A) | Without K6, the autonomous tuner can deploy mid-session by mistake or by adversarial action. |
| **K-meta** | The Kernel manifest itself + this constitution | Without K-meta, K1–K6 are revocable by the system; the safety perimeter must be its own fixed-point. |

#### IX.B — Autonomous-merge eligibility

A change set MAY be merged and deployed autonomously by the spec 005 tuner IFF ALL of the following hold:

1. **Kernel-untouched.** No file listed under any group in `kernel.toml` appears in the change set's diff. The deploy guard (spec 006) MUST verify this before any other deploy phase and MUST emit `DEPLOY_BLOCKED_KERNEL_TOUCH` and abort if violated.
2. **Hardened canary passed (spec 007).** The change set has progressed through the spec 007 hardened-canary acceptance criteria (multi-metric, ≥30 trading-day window, synthetic-shock replay, property-based fuzz of risk math). Until 007 is shipped, autonomous merge is DISABLED in production and the existing 10-day spec-001 canary is the upper bound.
3. **Constitution VIII.A and VIII.B unchanged in spirit.** Market-hours guard, audit events, health-check gate, and rollback obligation all still apply.
4. **No L4 escalation.** A change set that adds new files to `kernel.toml`, OR removes files from it, OR redefines the L1/L2/L3/L4 classification in spec 005, is treated as L4 and follows the human-merge path.

A change set that fails any of (1)–(4) follows the **human-merge path**: the tuner opens a pull request and waits. The operator's review attention is therefore concentrated exclusively on Kernel changes — predicted frequency is 0–2 events per year.

#### IX.C — Kernel manifest discipline

- The manifest at `.specify/memory/kernel.toml` is the single source of truth. Code that decides "is this file kernel?" MUST read it; hard-coded paths in deploy code are forbidden so that a Kernel addition is one TOML edit, not a code release.
- The manifest is itself in the K-meta group; modifying it autonomously is forbidden by IX.B-1.
- Adding a file to the Kernel is always a forward-compatible safety improvement and never requires an amendment of this constitution. Removing a file from the Kernel is a constitutional concern and SHOULD be paired with a constitution amendment (PATCH or MINOR depending on whether a principle is also relaxed).

**Rationale**: The operator's stated goal is autonomous execution and autonomous improvement. A naive reading of that goal — "the system can change anything" — gives a system with no safety guarantees, because any safety property is one self-modification away from being revocable. Naming the smallest possible Kernel and freezing it under autonomous control is the maximum-autonomy point that still admits a coherent safety argument. Outside the Kernel, the system is genuinely free to evolve.

**Trade-off acknowledgement**: this still places the operator in the loop on Kernel changes. The expected frequency of those changes is low (new asset class, new principle, new schema migration that touches audit-log structure). When they happen, they merit the operator's full attention, which is the entire point of carving them out.

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

**Compliance**: every `/speckit-plan` artifact MUST include a Constitution Check section verifying the plan does not violate principles I–IX. Violations require explicit, written justification and a sign-off recorded in the audit log.

**Version**: 2.0.0 | **Ratified**: 2026-05-01 | **Last Amended**: 2026-05-06
