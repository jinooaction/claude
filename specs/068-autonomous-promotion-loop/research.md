# Research: Autonomous Promotion Loop

## Decision: Backtest is a necessary filter, not live execution validation

**Rationale**: Backtests can test strategy logic, parameter robustness, walk-forward behavior, transaction cost assumptions, and benchmark-relative performance. They cannot observe actual broker order rejection, partial fills, live account holdings, cash availability, API timing, settlement constraints, or reconciliation behavior.

**Alternatives considered**:

- Treat a very strong backtest as sufficient for live money: rejected because it bypasses execution-path evidence and violates staged rollout.
- Require live canary before any forward paper: rejected because forward paper is cheaper and should screen weak strategies before broker exposure.

## Decision: First slice is read-only promotion classification

**Rationale**: Automatically registering new forward tracks requires modifying workflow/config surfaces and could create noisy or unsafe expansion. The safer first slice produces a promotion queue and makes the missing bridge visible while preserving existing money gates.

**Alternatives considered**:

- Auto-create portfolio configs and workflow arms immediately: deferred to a follow-up spec after the queue contract is proven.
- Fold promotion into `evolution_loop.py`: rejected because candidate discovery and promotion state are related but distinct responsibilities.

## Decision: Existing spec 050 and 055 remain authority

**Rationale**: Capital scaling and live strategy reassignment already have tested gates. The promotion loop should identify when evidence is ready for those gates, not create a second path.

**Alternatives considered**:

- Add a direct "promotion to live" decision: rejected because it would duplicate and weaken existing safety boundaries.
