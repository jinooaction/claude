# Feature Specification: Automated US-Equity Trading MVP

**Feature Branch**: `001-automated-trading-mvp`
**Created**: 2026-05-02
**Status**: Draft
**Input**: User description: "MVP automated trading worker for US listed equities via KIS OpenAPI, Python-driven and rule-based. All risk principles from constitution v1.0.0 apply. LLM-assisted judgment is deferred to a future spec; v1 contains zero judgment points."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Sleep through US market open and wake up to executed trades (Priority: P1)

The operator declares a small set of trading rules (each tied to one whitelisted US-listed symbol with explicit entry conditions and quantity caps), starts the worker before going to bed, and wakes up after the US session has closed to find that the worker has either (a) executed orders that match the rules and respected all risk limits, or (b) recorded a clear reason for not executing.

**Why this priority**: This is the core value of the entire system. Without this, none of the other capabilities matter. It is the smallest end-to-end slice that proves "money in → rule fires → order placed → outcome recorded" works for real.

**Independent Test**: Configure one rule for one whitelisted symbol with a small notional cap, start the worker, let it run through one US session, and verify the audit log contains either an order/fill record or an explicit non-execution reason for that rule.

**Acceptance Scenarios**:

1. **Given** a whitelisted symbol and a trigger rule (time-, price-, or indicator-based) with a quantity that fits all sizing caps, **When** the trigger condition is met during US regular hours, **Then** the system places the configured order and records the order and fill (if any) in the audit log.
2. **Given** a rule whose target symbol is not on the whitelist, **When** the worker starts, **Then** the system refuses to load the rule and records the rejection reason without halting other rules.
3. **Given** a rule whose quantity violates the per-trade size cap, **When** the trigger condition is met, **Then** the system rejects the order before submission and records the violation in the audit log.
4. **Given** the broker API is temporarily unreachable when a trigger fires, **When** the system attempts to submit, **Then** the system retries within configured limits, falls back to circuit-breaker on sustained failure, and records the outcome in the audit log without partial state.
5. **Given** an indicator-based rule that requires N bars of historical data, **When** the worker starts and fewer than N bars are available, **Then** the system marks the rule as not-yet-armed and records the reason; the rule begins evaluating only once enough bars are accumulated.

---

### User Story 2 — Daily reconciliation prevents silent state drift (Priority: P2)

After every US trading day closes, the system compares its internal record of positions and cash against the broker's reported state. If they disagree, the system halts new order submission and surfaces the discrepancy clearly so the operator can investigate.

**Why this priority**: Without reconciliation, the system can drift from reality (orphan orders, missed cancels, stale fills) and continue trading on a wrong assumed state. P1 is technically usable without P2, but only for a few days before trust degrades.

**Independent Test**: Manually inject a synthetic discrepancy (e.g., stale local position) and verify that the next reconciliation halts new orders and produces an actionable mismatch report.

**Acceptance Scenarios**:

1. **Given** internal positions match broker state, **When** daily reconciliation runs, **Then** the system records a successful reconciliation and continues normal operation.
2. **Given** internal positions do not match broker state, **When** reconciliation runs, **Then** the system halts new order submission, records the mismatch with both views side-by-side, and surfaces a clear alert.
3. **Given** reconciliation is halted due to mismatch, **When** the operator clears the alert with a logged justification, **Then** the system resumes normal operation and the resolution is part of the audit log.

---

### User Story 3 — Morning report makes daily activity auditable in minutes (Priority: P3)

After the US market closes, the system produces a single daily report containing: orders attempted, orders executed (and their fills), orders rejected (and why), reconciliation status, and an end-of-day position/cash snapshot. The operator can read this report in the morning and decide whether to keep the worker running, change rules, or pause.

**Why this priority**: P1 and P2 produce the audit log, which is sufficient for forensics. P3 turns that raw log into a report a human can scan in under five minutes. Without it, the operator's daily check becomes a chore and trust erodes — but P1 + P2 still function.

**Independent Test**: After a session in which several rules fire and at least one is rejected, verify the report contains a single page-equivalent summary that lets the operator answer "what happened today?" without opening the raw audit log.

**Acceptance Scenarios**:

1. **Given** a completed US trading session, **When** the report is generated, **Then** it contains: orders attempted/executed/rejected counts with per-rule breakdown, P&L estimate, end-of-day positions and cash, and reconciliation status.
2. **Given** any order was rejected by a risk gate, **When** the report is generated, **Then** the rejection is listed with the gate name and the violated limit value.

---

### Edge Cases

- US market is closed (holiday, half-day, weekend) when the worker would otherwise run — the system MUST detect this and skip without errors.
- A trigger fires during the last seconds of regular hours — the system MUST either complete submission within the session or skip with a clear "session ended" reason.
- KIS access token expires while the worker is mid-decision — the system MUST refresh transparently and proceed without losing the trigger.
- An indicator-based rule loses its market-data feed mid-session — the system MUST mark the rule as not-armed for the duration of the gap and resume only after data quality is restored.
- Two rules trigger simultaneously and would together exceed the global exposure cap — the system MUST enforce caps in declared priority order and reject the lower-priority order.
- Operator edits the rules file while the worker is running — the system MUST ignore live edits and continue with the configuration loaded at startup until a controlled restart (per OD-3 resolution).
- A partial fill occurs — the system MUST record the partial fill, update its internal position, and decide (per rule) whether to keep, cancel, or resubmit the remainder.
- Daily reconciliation cannot reach the broker — the system MUST treat this as a halt-new-orders condition until reconciliation succeeds.
- Multiple consecutive days of canary metrics fall below acceptance — the system MUST automatically pause the affected strategy and surface the degradation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow the operator to declare trading rules in a configuration artifact loaded at worker startup, with each rule specifying at minimum: target symbol, trigger condition, order parameters, and per-rule sizing caps. Trigger conditions MUST support all three families: time-based, single-threshold price-based, and indicator-based (per OD-1 resolution).
- **FR-002**: System MUST refuse to load any rule whose target symbol is not on the operator's versioned whitelist.
- **FR-003**: System MUST evaluate triggers continuously during US regular trading hours and ignore them outside that window unless the rule explicitly opts into extended hours.
- **FR-004**: System MUST enforce per-trade, per-symbol, and global exposure caps before any order is submitted to the broker; orders that violate any cap MUST be rejected and logged.
- **FR-005**: System MUST NOT call any LLM in v1; no judgment points are defined for this feature. (Per OD-2 resolution. LLM-assisted judgment is reserved for a future spec.)
- **FR-006**: System MUST persist every order intent, submission, fill, cancellation, rejection, and error to an append-only audit log with monotonic timestamps.
- **FR-007**: System MUST run a reconciliation pass after the US session closes that compares internal positions and cash against the broker's reported state, and halt new order submission on any unresolved mismatch.
- **FR-008**: System MUST automatically refresh expired broker access tokens without operator intervention.
- **FR-009**: System MUST mask all secret values (API keys, tokens, account numbers) in logs, error messages, and reports.
- **FR-010**: System MUST produce a daily summary report after the US session closes covering orders attempted/executed/rejected, reconciliation result, and end-of-day positions and cash.
- **FR-011**: System MUST refuse to start if any required secret is missing from the configured secret source.
- **FR-012**: System MUST refuse to start a strategy in canary stage if a higher-stage version of the same strategy is currently active for the same symbol.
- **FR-013**: System MUST allow the operator to halt all order submission at any time via a documented operator-controlled mechanism, with the halt persisted across worker restarts until explicitly cleared.
- **FR-014**: System MUST support running a strategy in canary stage with capped capital share (declared in spec) and automatically pause the strategy if its live performance falls below predeclared acceptance metrics for a configured duration.
- **FR-015**: System MUST load rules at worker startup only and ignore any live edits to the rules configuration; new rules take effect only after a controlled worker restart (per OD-3 resolution).
- **FR-016**: System MUST acquire and persist the historical price bars required by indicator-based rules and MUST mark a rule as not-armed until its required history is fully accumulated.
- **FR-017**: System MUST detect market-data quality issues (gaps, stale ticks beyond a configured threshold) for any active indicator-based rule and treat affected rules as not-armed until quality is restored.

### Key Entities

- **TradingRule**: an operator-declared declarative description of "when X happens, do Y for symbol Z up to size W" — includes the trigger family (time / price / indicator), action, parameters, and sizing caps.
- **Trigger**: the condition portion of a TradingRule. One of three families: time-based (calendar-style schedule), price-threshold (single-side comparison against current price), or indicator-based (computed over a configured window of historical bars).
- **PriceBar**: a single OHLCV record for a symbol at a fixed interval, used to feed indicator computations and to satisfy reconciliation/data-quality checks.
- **Whitelist**: the versioned set of symbols, account IDs, order types, and sessions explicitly allowed by the operator (deny-by-default per constitution principle II).
- **Order**: a system-generated, sizing-validated instruction submitted (or attempted) to the broker; carries an immutable identifier and links back to the originating TradingRule.
- **Fill**: a confirmation of executed quantity at a price for an Order; an Order may have zero, one, or many Fills.
- **Position**: the system's current accounting of how much of a given symbol is held, updated from Fills and verified against the broker by reconciliation.
- **AuditLogEntry**: an immutable, timestamped record of any of: Order submission/cancellation/fill, configuration load, reconciliation result, halt/resume event, secret-load result, data-quality event.
- **DailyReport**: a human-readable end-of-session artifact summarizing the day's activity from the AuditLog.
- **StrategyStage**: the lifecycle state of a strategy — one of `backtest` / `canary` / `full-live` (per constitution principle VI).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The operator can declare a single trading rule, start the worker, and verify after one US session that the rule was honored exactly as declared (executed when triggered, skipped when not triggered, rejected when over caps), with zero manual intervention during the session.
- **SC-002**: Across any rolling 30-day operating window, zero orders submitted to the broker violate any declared sizing cap (per-trade, per-symbol, or global).
- **SC-003**: Across any rolling 30-day operating window, zero orders are submitted for symbols, accounts, order types, or sessions outside the operator's whitelist.
- **SC-004**: Daily reconciliation runs on every US trading day; any unresolved mismatch halts new orders within 60 seconds of detection and surfaces an alert the operator can act on.
- **SC-005**: 100% of orders, fills, cancellations, rejections, and errors are recoverable from the audit log; the operator can reconstruct any past day's activity without external state.
- **SC-006**: The daily report is available within 5 minutes of US session close on every operating day.
- **SC-007**: The operator can audit yesterday's complete activity in under 5 minutes by reading only the daily report.
- **SC-008**: A canary strategy whose live performance falls below acceptance metrics for the declared duration is automatically paused within one full trading day of the threshold breach.
- **SC-009**: Zero secrets appear in any log, error message, report, or other artifact produced by the system across any rolling 30-day window.

## Assumptions

- The operator is the sole user, owner, and on-call responder for the system; no multi-user access control is required in v1.
- The operator has, or will obtain before first live use, a real KIS account provisioned for the OpenAPI with overseas-stock trading enabled, plus the application key/secret pair.
- The operator has a host (personal machine, VPS, or small cloud instance) capable of running a long-lived process during US market hours.
- All trading is for the operator's own account; no third-party funds, no managed-account regulatory regime applies.
- USD/KRW conversion is handled by the broker; FX risk is observable but not actively hedged in v1.
- The operator provides the initial whitelist of symbols at startup time; whitelist editing tooling is out of scope for v1 beyond editing a versioned configuration artifact.
- Backtesting infrastructure is treated as a sibling concern, separately specified; this spec assumes backtest results are produced and supplied as input to canary promotion decisions, not generated by this feature.
- Notification channel (e.g., email, push) for halts and alerts is out of scope for v1; the daily report and audit log are the primary observation surfaces. Operator-controlled halt and alert surfacing happen via the existing log/report; richer channels can be a later spec.
- Indicator computation in v1 may rely on a community-standard library or a minimal in-house implementation; building a high-performance custom indicator engine is out of scope for v1.
- Historical price bars required by indicator rules are sourced through the broker's market-data interface (or an equivalent vendor reachable from the worker) and persisted locally; no third-party paid data feed is assumed.
- The constitution v1.0.0 is binding on this feature; any apparent conflict between this spec and the constitution resolves in the constitution's favor.

## Out of Scope (v1)

The following are deliberately deferred to later specs to keep v1 focused:

- **LLM-assisted judgment**: no Claude consultation occurs in v1 (per OD-2 resolution). A separate spec will introduce judgment points once the rule-based execution shell is stable.
- **Hot-reload of rules**: configuration changes require a worker restart in v1 (per OD-3 resolution).
- **Multi-asset classes**: derivatives, options, futures, short selling, leverage, crypto, and domestic Korean equities remain out of scope per constitution v1.0.0.
- **Push/email notifications**: alerting beyond logs and the daily report.
- **Backtest engine**: produced by a sibling feature spec; this feature consumes its results as input to promotion decisions.

## Open Decisions

All open decisions originally tracked here have been resolved and folded into the requirements above:

- **OD-1 — Trigger expressiveness**: resolved as **time + price-threshold + indicator** (option C). See `FR-001`, `FR-016`, `FR-017`.
- **OD-2 — LLM judgment scope**: resolved as **no LLM in v1** (option D). See `FR-005` and Out of Scope.
- **OD-3 — Live-edit semantics**: resolved as **ignore live edits, require restart** (option A). See `FR-015`.
