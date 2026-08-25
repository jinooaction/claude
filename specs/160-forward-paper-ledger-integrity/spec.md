# Feature Specification: Forward Paper Ledger Integrity

**Feature Branch**: `Codex/160-forward-paper-ledger-integrity`
**Created**: 2026-08-25
**Status**: In progress
**Input**: Production replay showed fixed-capital paper ledgers with large negative cash and gross holdings many times above capital; those curves must never promote real capital.

## User Scenarios & Testing

### User Story 1 - Invalid paper economics cannot become edge evidence (Priority: P1)

As the operator, I need every forward result to represent an unlevered paper account with nonnegative cash so that a statistically attractive curve cannot be created by accidental borrowing.

**Why this priority**: The latest $12,000 tracks reported cash as low as about -$151,000 while still producing PSR and Calmar values. Statistical corrections cannot make an economically invalid ledger trustworthy.

**Independent Test**: Seed paper fills whose net purchases exceed the declared capital, run the NAV snapshot command, and verify that it exits nonzero without appending a snapshot.

**Acceptance Scenarios**:

1. **Given** paper fills whose ledger cash is negative, **When** a capital-based NAV snapshot is requested, **Then** the command fails closed and appends no `PORTFOLIO_NAV_SNAPSHOT`.
2. **Given** paper fills within available cash, **When** the same snapshot is requested, **Then** the snapshot is appended and explicitly reports a valid nonnegative-cash measurement.
3. **Given** live mode or a measurement without a paper capital basis, **When** NAV is measured, **Then** existing behavior remains unchanged.

---

### User Story 2 - Clean measurement epoch preserves old audit evidence (Priority: P1)

As the operator, I need all seven forward tracks to start from clean databases while retaining the contaminated databases for forensic audit.

**Why this priority**: Repairing only future calculations would leave old leveraged snapshots inside the active statistical suffix. Deleting them would violate audit preservation.

**Independent Test**: Inspect the production observation helper and verify that every forward producer and consumer uses one versioned clean database path while old paths are never removed or rewritten.

**Acceptance Scenarios**:

1. **Given** the seven legacy databases, **When** the new version deploys, **Then** trend, no-trend, risk-managed beta, multiasset, global, global-fixed, and wide tracks use distinct versioned databases.
2. **Given** candidate history, ladder, anchored verdict, signal-IC, and cross-asset analysis consumers, **When** they run, **Then** they read the same clean database paths as their producers.
3. **Given** old database files, **When** storage preparation runs, **Then** no old file is deleted, truncated, renamed, or edited.

---

### User Story 3 - Production reports distinguish strategy quality from evidence validity (Priority: P2)

As the operator, I need reports to say that prior PSR values are invalidated by ledger economics instead of concluding that the strategy passed or failed.

**Why this priority**: `multiasset` PSR 0.806220 and `globalfixed` PSR 0.728797 came from overleveraged paper books. Reusing either value would repeat the original judgment error.

**Independent Test**: Run the production forward workflow after deployment and verify that the sidecar names the clean measurement epoch, contains no negative-cash snapshot, and reports insufficient clean observations rather than reusing old PSR.

**Acceptance Scenarios**:

1. **Given** a newly created clean database, **When** the first forward run completes, **Then** the verdict is based only on the new epoch and cannot inherit the prior observation count.
2. **Given** missing or invalid NAV evidence, **When** money and capital paths refresh, **Then** capital remains at rung 0 and real orders remain disabled.

### Edge Cases

- A tiny rounding residual down to -$0.01 is tolerated; a value below that fails closed.
- A strategy whose holdings appreciate above the original capital but whose cash remains nonnegative is not treated as accidental borrowing.
- A track may fail independently without suppressing other tracks, but its missing verdict cannot be promoted.
- A fresh database may contain price bars but no fills; its first valid NAV remains a clean starting observation.
- Repeated workflow dispatches on the same day must not copy legacy snapshots into the clean epoch.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST reject a paper NAV snapshot when declared capital plus cumulative paper cash flow is less than -$0.01.
- **FR-002**: A rejected snapshot MUST append no NAV audit event and MUST return a nonzero process status.
- **FR-003**: A valid capital-based paper snapshot MUST report the capital basis, ledger cash, and a machine-readable valid measurement flag.
- **FR-004**: The system MUST move all seven forward tracks to versioned clean database paths and MUST preserve every legacy database untouched.
- **FR-005**: Every operational consumer of a forward track MUST read the same versioned database as its producer.
- **FR-006**: Candidate history support and exact deployment evidence MUST use the clean global-fixed, wide, and multiasset databases.
- **FR-007**: The forward sidecar MUST identify the clean ledger epoch and MUST not carry observation counts or PSR values from legacy databases.
- **FR-008**: Invalid, absent, or under-observed clean evidence MUST remain fail-closed through profit evidence, capital ladder, money path, and live-entry revalidation.
- **FR-009**: The feature MUST NOT place orders, arm live trading, allocate capital, widen the whitelist or caps, delete audit rows, or change the constitution or kernel.
- **FR-010**: Rollback MUST consist of reverting code path selection only; it MUST never require deletion of either legacy or clean databases.

### Key Entities

- **Ledger measurement**: One NAV observation with declared capital, cumulative paper cash, market value, and validity.
- **Measurement epoch**: A versioned set of seven isolated SQLite databases whose fills and NAV points share one clean economic history.
- **Track binding**: The one-to-one mapping from a strategy key to its portfolio, database, halt flag, and downstream consumers.
- **Legacy evidence**: Preserved pre-epoch fills and snapshots that remain auditable but are ineligible for promotion.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of negative-cash paper snapshot tests fail with zero new NAV audit rows.
- **SC-002**: All seven producers and every named downstream consumer resolve to the same clean epoch paths in automated contract tests.
- **SC-003**: The first production clean-epoch replay reports zero inherited observations and no inherited PSR for every track.
- **SC-004**: Production KIS smoke remains 5/5 with zero submitted orders and zero open unfilled orders.
- **SC-005**: Full tests, lint, workflow syntax, strict harness, and handoff fact validation pass before merge.

## Assumptions

- The legacy database files are kept in place as immutable forensic evidence.
- Current paper routing logic is safe from new repeated purchases after PR #566; the new negative-cash gate independently prevents recurrence from becoming statistical evidence.
- Price bars are repopulated by the existing backfill step in each clean database.
- Historical holdout evidence remains a separate research result; only contaminated forward PSR and observation counts are invalidated.
- `Backtest -> Canary -> Full`, exact strategy fingerprinting, hardened canary, K1/K2, and the 0.80 exploration / 0.95 full thresholds remain unchanged.
