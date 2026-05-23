<!--
Sync Impact Report (v3.0.0 -> 3.1.0)
==================
Version change: 3.0.0 -> 3.1.0  (MINOR: principle X added — Measurement-Driven Autonomous Growth. No principle removed or redefined; trading-safety invariants I-VII and VIII.A unchanged; spec 007 hardened canary remains the production-deploy gate.)
Added principles:
  X. Measurement-Driven Autonomous Growth (NEW). Autonomous self-modification targeting trading performance (spec 005 tuner) MUST be justified by live/paper measurement (spec 011); live/paper/canary/backtest performance MUST share one metric definition (spec 008 backtest/metrics.py); completed merged phases auto-deploy via the VIII.B-guarded pipeline (deploy/AUTO-DEPLOY.md); deploy != live money (AUTO_INVEST_MODE=live stays operator-gated). Adds a requirement (evidence before tuning) and a standing mode (continuous deploy to a dry-run worker) entirely INSIDE the existing safety perimeter.
Modified principles: none.
Templates requiring updates:
  ✅ .specify/memory/constitution.md (this file) — principle X added; Governance compliance line "I–IX" -> "I–X".
  ⚠ .specify/templates/plan-template.md — Constitution Check should cover principle X for performance-targeting / tuner / deploy specs (deferred; applied at next /speckit-plan touching those areas).
  ⚠ specs/005-autonomous-tuner/spec.md — tuner MUST cite spec 011 measurement as its input signal (deferred; spec 005 still a stub).
Rationale:
  The operator's vision is a world-class system that grows itself autonomously, driven by measured evidence rather than guesses. v3.0.0 enshrined operator-autonomy supremacy (IX.D) and the deploy guards (VIII.B), but nothing required the future tuner to act on MEASURED performance, nor named the standing "each merged phase auto-deploys" mode. Spec 011 (live performance eval, P2 risk-adjusted metrics) now provides the measurement; this principle ties it to spec 005's growth loop and to the deploy pipeline, without widening the loss surface. this changes the safety perimeter (K-meta forensic marker: principle addition).

Sync Impact Report (v2.0.0 -> 3.0.0)
==================
Version change: 2.0.0 -> 3.0.0  (MAJOR: operator's autonomy preference enshrined as supreme decision criterion; IX.B-1 and IX.B-4 repealed so autonomous merge is the default path including Kernel touches; IX.B-2 reclassified as deploy-stage gate not merge-stage gate; trading-safety invariants preserved via principles I-VII and VIII.A unchanged; spec 007 hardened canary remains the production-deploy gate that protects real money)
Modified principles:
  IX.A — Kernel reframed from "review-gated barrier" to "high-attention forensic-audit list". The seven groups (K1..K6 + K-meta) remain enumerated but a Kernel touch no longer blocks merge by itself.
  IX.B-1 (autonomous-merge eligibility, "Kernel-untouched") — REPEALED. Kernel touches are now permitted under the autonomous workflow when initiated by an operator-instructed session OR when the spec 007 hardened canary is satisfied. The deploy guard still EMITS a forensic audit row (DEPLOY_BLOCKED_KERNEL_TOUCH renamed in semantic to DEPLOY_KERNEL_TOUCHED — informational, not blocking).
  IX.B-2 — RECLASSIFIED. The hardened canary is now explicitly a PRODUCTION-DEPLOY gate, not a merge gate. Merges land via the autonomous-workflow policy in CLAUDE.md; live trading exposure to the new code is still gated by spec 007.
  IX.B-3 — preserved (VIII.A market-hours deploy guard still applies).
  IX.B-4 (no L4 escalation) — REPEALED. Spec 005's L4 classification now means "extra audit + forensic callout" not "human-merge path".
  IX.C — modifications now permitted under autonomous workflow; the manifest's role shifts from "fixed-point barrier" to "high-attention forensic list".
Added principles:
  IX.D — Operator Autonomy Supremacy (NEW, NON-NEGOTIABLE). The operator's stated autonomy preference is the supreme decision criterion. When any procedural rule in this constitution would block autonomous progression initiated by an operator-instructed session, the autonomous path wins. The exceptions are the trading-safety invariants in principles I-VII and VIII.A, which protect the operator's real money and remain non-negotiable regardless of autonomy direction.
Backward-incompatibility:
  - Code that read IX.B-1 as "Kernel touches halt the merge" MUST be rewritten to "Kernel touches emit DEPLOY_KERNEL_TOUCHED and continue".
  - Spec 005's L1/L2/L3/L4 tiered authority loses the "L4 → operator-merge" branch. L4 is now "extra audit + forensic callout", same merge path as L1-L3.
  - Spec 006's kernel_guard becomes a log-loud guard, not a halt guard. Its return type's `touched` boolean stays the same; consumers MUST change their interpretation from "abort" to "emit forensic event and continue".
  - Spec 007 stays semantically unchanged but is now framed as the production-deploy gate, not the merge gate.
Templates requiring updates:
  ✅ .specify/memory/constitution.md (this file)
  ⚠ .specify/memory/kernel.toml — descriptions updated to reflect "high-attention list, not barrier" semantics; file paths unchanged.
  ⚠ specs/005-autonomous-tuner/spec.md — L4 branch rewording (deferred; spec is still a stub).
  ⚠ specs/006-deploy-automation/spec.md — kernel_guard semantics from halt to log-loud (deferred until spec 006 implementation resumes).
  ⚠ specs/007-canary-hardening/spec.md — framing update from "merge gate" to "production-deploy gate" (deferred; spec is still a stub).
  ⚠ specs/008-backtest-engine/{spec,plan,research,data-model}.md — Constitutional Fit / one-time-K4-touch sections can be simplified; "one-time additive Kernel touch with operator approval at merge" is no longer a special event under v3.0.0 (deferred; spec 008 implementation in flight).
Rationale:
  The operator (mason) instructed on 2026-05-14: "내 목표는 자율 수행이라고. 헌법이 장애물이라면 그것도 수정해야지 당연히. 내 목표가 최상위 의사결정 기준이야" (= autonomy is the supreme decision criterion; the constitution is subordinate to that goal and should be amended where it conflicts). v2.0.0's IX.B-1 was carved to protect the operator from their own future autonomous tuner rewriting safety code, but in practice it concentrated operator attention on a handful of additive K4 touches (e.g., spec 002's migration 0002, spec 008's audit-event Union extension) that didn't reduce safety. The operator's concrete failure mode is loss of money via bad trading decisions, not loss of money via the autonomous tuner rewriting risk gates — because the autonomous tuner doesn't exist yet (spec 005 is a stub), and when it does, spec 007's hardened canary will catch the misbehaviour at the production-deploy boundary. So the meaningful protection lives at the deploy boundary, not at the merge boundary; v3.0.0 makes that explicit.
Trade-off acknowledged:
  Under v3.0.0, a misbehaving future autonomous tuner CAN merge a change that removes K1 (position caps). The change lands in `main`. It does NOT reach production unless it passes spec 007's hardened canary or unless an operator-instructed session deploys it. The operator accepts this trade-off because:
    1. The autonomous tuner doesn't exist yet (spec 005 is a stub).
    2. When it ships, spec 007 is its mandatory deploy gate.
    3. The operator wants zero procedural friction at the merge stage.
    4. Reversion is one PR away (main is always deployable; main with a regression is one PR away from being main without the regression).
Sync Impact Report (v1.1.0 -> 2.0.0)
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

### IX. Self-Modification Boundary (NON-NEGOTIABLE, amended v3.0.0)

The system is permitted — and encouraged — to evolve its own code, configuration, prompts, KPI thresholds, dependencies, schemas, and principles, as long as the trading-safety invariants in principles I–VII and VIII.A are honoured at production-deploy time. The Kernel (defined below) is no longer a merge-time barrier under v3.0.0; it is now a **high-attention forensic list** that triggers loud audit on touch. The real defence against a misbehaving autonomous tuner is spec 007's **hardened canary as a production-deploy gate** (IX.B-2), not IX.B-1's old merge-time approval requirement.

#### IX.A — The Kernel (forensic-attention list)

The Kernel is the closed set of files listed in the machine-readable manifest at `.specify/memory/kernel.toml`. As of v3.0.0 the Kernel still comprises seven groups, each tied to one constitutional invariant — but a Kernel touch no longer halts merge by itself.

| Group | Invariant | Forensic-attention reason |
|-------|-----------|---------------------------|
| **K1** | Position sizing caps (principle I) | Modification expands the loss surface; emit `DEPLOY_KERNEL_TOUCHED` and require spec 007 canary before production deploy. |
| **K2** | Deny-by-default whitelist (principle II) | Modification expands the universe; same gate. |
| **K3** | LLM-only-at-judgment-points contract (principle III) | Modification uncaps LLM cost or moves call sites; same gate. |
| **K4** | Append-only audit log (principle IV) | Modification could erase forensic trail; same gate. |
| **K5** | Secret isolation (principle V) | Modification could leak KIS keys; same gate. |
| **K6** | Market-hours deploy guard (principle VIII.A) | Modification could permit mid-session deploys; same gate. |
| **K-meta** | The Kernel manifest itself + this constitution | Modification reshapes the safety surface; same gate AND the commit message MUST include the literal string "this changes the safety perimeter" so a forensic grep can find every such event. |

#### IX.B — Autonomous-merge eligibility (v3.0.0)

A change set MAY be merged autonomously by ANY of these paths:

1. **REPEALED** (was: "Kernel-untouched required for autonomous merge"). Kernel touches no longer block merge. The deploy guard (spec 006) MUST emit an informational `DEPLOY_KERNEL_TOUCHED` audit row when a Kernel touch lands; it MUST NOT abort the deploy on this signal alone.
2. **Hardened canary as production-deploy gate (spec 007).** Before any change set reaches the production worker, it MUST pass spec 007's hardened-canary acceptance criteria: multi-metric, ≥30 trading-day window for L2 / ≥45 for L3, synthetic-shock replay, property-based fuzz of risk math. This gate protects real money. Until spec 007 ships, the existing 10-day spec-001 canary is the operator-facing upper bound on production autonomy; merges still land freely, but a human (or future tuner) decides when a merge is deploy-eligible.
3. **VIII.A market-hours guard unchanged.** Mid-session deploys remain forbidden whether the change set is Kernel-touching or not.
4. **REPEALED** (was: "L4 escalation → human-merge"). Spec 005's L4 classification now means "extra audit + forensic callout in the PR description"; the merge path is the same as L1-L3.
5. **Operator-instructed session merges** (autonomous-workflow policy in CLAUDE.md) are first-class. The session's reasoning trace + the PR description + the merge commit message form the forensic record. No second human in the loop is required.

#### IX.C — Kernel manifest discipline (v3.0.0)

- The manifest at `.specify/memory/kernel.toml` is the single source of truth for "what counts as Kernel". Code that asks "is this path Kernel?" MUST read the manifest; hard-coded paths are forbidden so a Kernel addition or removal is one TOML edit, not a code release.
- The manifest is itself in K-meta. Modifications to it (adding paths, removing paths, restructuring groups) ARE permitted under the autonomous workflow but MUST include the K-meta forensic callout in the commit message (see IX.A's K-meta row).
- Adding a file to the Kernel is a forward-compatible safety improvement (broadens the forensic-attention list). Removing a file is a contraction of the safety surface and SHOULD be paired with a brief commit-message justification.

#### IX.D — Operator Autonomy Supremacy (NEW, NON-NEGOTIABLE, added v3.0.0)

The operator's stated autonomy preference is the **supreme decision criterion** for procedural conflicts. When a procedural rule anywhere in this constitution, in a spec, in CLAUDE.md, or in this session's reasoning would block autonomous progression initiated by an operator-instructed session, the autonomous path wins.

This DOES NOT relax the trading-safety invariants:

- **Principle I** (position caps) — still non-negotiable. A change that removes a cap is still subject to the spec 007 canary at production-deploy time.
- **Principle II** (deny-by-default whitelist) — still non-negotiable, same gate.
- **Principle III** (LLM-only-at-judgment-points) — still non-negotiable, same gate.
- **Principle IV** (append-only audit log) — still non-negotiable, same gate.
- **Principle V** (secret isolation) — still non-negotiable, same gate.
- **Principle VI** (Backtest → Canary → Full Live) — still non-negotiable; spec 008's backtest engine is the first stage, spec 007 the hardened canary is the second.
- **Principle VII** (external API robustness) — still non-negotiable.
- **Principle VIII.A** (no live deploys during market hours) — still non-negotiable.

What IX.D explicitly relaxes:

- "Wait for the operator to approve a PR" — the session's chat-channel approval (or the operator-instructed merge command) IS the approval.
- "Wait for the operator to amend the constitution" — when the constitution itself is the procedural barrier, the session MAY amend it under operator instruction, recording the change as a K-meta forensic event.
- "Defer Kernel touches to a separate human review" — under v3.0.0 they ride the same PR.

**Rationale**: The operator's failure mode is loss of money via bad trading decisions, not loss of money via a self-rewriting safety perimeter — because the autonomous tuner doesn't exist yet (spec 005 is a stub), and when it does, spec 007's hardened canary will catch misbehaviour at the production-deploy boundary. Procedural friction at the merge boundary delivered no safety benefit in practice (the operator's K4 touches were all additive: spec 002's migration 0002, spec 008's event-type Union extension) and consumed operator attention that should have gone to trading-strategy quality. v3.0.0 moves the safety perimeter from the merge boundary to the production-deploy boundary, where it actually defends real money.

**Trade-off acknowledged**: under v3.0.0, a future misbehaving autonomous tuner CAN merge a change that removes K1 (position caps). The change lands in `main`. It does NOT reach the live worker unless it passes spec 007's hardened canary or unless an operator-instructed session deploys it. Reversion is one PR away (main is always deployable; main with a regression is one PR away from being main without the regression).

### X. Measurement-Driven Autonomous Growth (added v3.1.0)

The system's purpose is not merely to trade safely but to **grow itself toward world-class performance autonomously**, and that growth MUST be driven by measured evidence, not by guesses.

1. **Measure before you tune.** Any autonomous self-modification that targets trading performance (spec 005's tuner) MUST be justified by live/paper performance measurement (spec 011) — realized/unrealized PnL, risk-adjusted metrics (Sharpe, max drawdown, win rate, profit factor), and per-rule/per-symbol attribution. A tuning action with no upstream measurement signal is not permitted.
2. **One yardstick.** Live, paper, canary, and backtest performance MUST be computed with the **same metric definitions** (spec 008 `backtest/metrics.py` is the single source). This makes "backtest said X, live did Y" a meaningful comparison and lets the tuner detect strategy decay (e.g., rolling Sharpe 1.2 → 0.8).
3. **Each completed phase auto-deploys.** A merged change auto-deploys to the running system via the VIII.B-guarded pipeline (`deploy/AUTO-DEPLOY.md`): an immediate on-merge trigger plus the off-hours timer safety net. This keeps the running worker continuously at `main`.
4. **Deploy ≠ live money.** Auto-deploy lands code and restarts the worker; it does NOT move the system from dry-run to real orders. The `AUTO_INVEST_MODE=live` transition remains an explicit operator-gated decision and is never flipped autonomously.

This DOES NOT relax principles I–VII or VIII.A. The production-money defence remains spec 007's hardened canary (IX.B-2). Measurement-driven growth operates entirely **within** the existing safety perimeter: it adds a *requirement* (evidence before tuning) and a *standing mode* (continuous deploy of merged work to a dry-run worker), neither of which widens the loss surface.

**Rationale**: A self-growing system that tunes on guesses instead of measured performance is just a faster way to drift. spec 011 makes live behaviour measurable on the same yardstick as backtest, so the future tuner (spec 005) and the operator act on evidence. Naming the auto-deploy mode as a principle (not just an ops doc) ensures the "deploy ≠ live money" separation is a constitutional invariant, not a convention that could erode.

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

**Compliance**: every `/speckit-plan` artifact MUST include a Constitution Check section verifying the plan does not violate principles I–X. Violations require explicit, written justification and a sign-off recorded in the audit log.

**Version**: 3.1.0 | **Ratified**: 2026-05-01 | **Last Amended**: 2026-05-23
