# Research: Account-Wide Micro GTAA Autonomous Rebalance

## Decision: Use the broker account snapshot as the live planning source

**Rationale**: The live KIS account already contains holdings that were not created by the current local fill ledger. A plan based only on local `current_positions` treats those holdings as invisible and can only conclude that cash is insufficient. Live planning must read KIS positions, KIS purchasable cash, and quotes before deciding whether to sell, hold, or buy.

**Alternatives considered**:
- Keep using only local ledger positions: rejected because it ignores confirmed account capital and cannot solve the current cash constraint.
- Import broker holdings into the fill ledger as synthetic fills: rejected for this feature because it would blur append-only order evidence with external starting state.
- Use manual one-time liquidation: rejected because the user explicitly requires continuous autonomous operation from the application point onward.

## Decision: Separate target-buy eligibility from liquidation-only eligibility

**Rationale**: Existing holdings can be valid sell candidates without being valid future buy candidates. The target micro GTAA universe remains `SPYM`, `IEF`, `GLDM`. Legacy holdings discovered from current broker evidence can be listed as liquidation-only so the system may reduce them but must never buy them.

**Alternatives considered**:
- Add legacy holdings to the portfolio universe: rejected because it would change the strategy and allow unintended buys.
- Refuse to touch legacy holdings: rejected because it leaves the account cash-constrained and contradicts the requested account-wide profit view.
- Add a side-agnostic whitelist expansion without extra guardrails: rejected because it would make a config mistake able to authorize buys of legacy holdings.

## Decision: Prefer sell-only cycles when current cash cannot fund buys

**Rationale**: The previous live attempt showed broker rejections when buying power was insufficient. If sell candidates exist and KIS purchasable cash is below planned buys plus the 1% buffer, the safest autonomous step is to submit only eligible sell orders. Later buys require a fresh KIS cash read that confirms purchasing power.

**Alternatives considered**:
- Submit sells and buys in the same command and rely on broker settlement behavior: rejected because purchasable cash availability can lag fills.
- Continue blocking all orders on cash shortfall: rejected because it never frees capital from existing holdings.
- Estimate sale proceeds as cash for the same run: rejected because the broker, not the strategy, controls purchasable cash.

## Decision: Allow account-wide dry-run preview to perform read-only KIS calls

**Rationale**: A meaningful account-wide preview cannot be produced from static repository files. Dry-run must still mean no orders, but in this mode it may read broker positions and cash to produce the exact plan that the live cycle would evaluate.

**Alternatives considered**:
- Keep dry-run fully offline: rejected because it cannot classify current broker holdings.
- Use yesterday's smoke-test snapshot: rejected because cash and holdings are drift-prone.
- Require an operator-supplied JSON snapshot: rejected as too manual for continuous operation.

## Decision: Publish next-step evidence in the existing sidecar

**Rationale**: The money-path report already consumes `automation/rebalance-micro-gtaa-last-run`. Extending that sidecar with account-wide mode, sell-only state, cash requirement, and next expected step keeps the operator and later sessions on one evidence surface.

**Alternatives considered**:
- Create a new sidecar branch: rejected because it splits the state needed for one trading path.
- Rely only on GitHub Actions logs: rejected because logs are not the durable operating state.
- Rely only on Telegram: rejected because alerts are not sufficient for reproducible handoff.
