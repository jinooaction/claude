# Research: Degraded Execution State

## Decision: Use a sell-only state instead of the halt flag for uncertain reads

**Decision**: Represent uncertain account state as `DEGRADED_SELL_ONLY` and apply it only to BUY orders.

**Rationale**: The existing halt flag is a full stop. Fill-sync, NAV, and reconciliation uncertainty should stop new exposure but still allow exits and repair. Sell-only mode matches the failure mode without trapping the account.

**Rejected Alternative**: Set the halt flag on every inconclusive read. This is safer in a narrow sense but blocks SELL and recovery flows that may reduce risk.

## Decision: Combine persisted and runtime blockers

**Decision**: Evaluate durable blockers from SQLite on each route and add worker-local runtime blockers for the latest fill-sync, NAV, and loss-mark observations.

**Rationale**: `SUBMISSION_UNKNOWN` and reconciliation outcomes already persist. Fill-sync and NAV failures are current worker observations and can be cleared by the next successful read without adding a new table.

**Rejected Alternative**: Store a new account state table. That would require migration and lifecycle semantics wider than this PR.

## Decision: Keep absence of reconciliation neutral

**Decision**: No reconciliation run means `HEALTHY` for this feature; only explicit latest `INCONCLUSIVE` degrades BUY.

**Rationale**: Existing workers do not require a reconciliation before their first order. Turning absence into a blocker would be an operational behavior change beyond the targeted safety contraction.

## Decision: Do not include cross-process account locks

**Decision**: Leave account-wide locks and single authority for spec 116.

**Rationale**: Spec 115 can be reviewed as a small deny-by-default BUY gate. Locking changes process ownership and deployment semantics.
