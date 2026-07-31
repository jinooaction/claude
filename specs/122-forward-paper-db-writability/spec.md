# Feature Specification: Forward Paper DB Writability

**Feature Branch**: `codex/122-forward-paper-db-writability`
**Created**: 2026-07-31
**Status**: Draft
**Input**: User description: "빨리 돈벌게해줘" after live money surfaces showed `PREVIEW_ONLY` / `NO_EDGE_YET`, while the latest forward paper run showed every `paper-track-run` prep step failing with `OperationalError: attempt to write a readonly database`.

## User Scenarios & Testing

### User Story 1 - Keep Forward Paper Observations Accumulating (Priority: P1)

As the operator, I need every forward paper track to keep writing its daily bars, paper rebalance, and NAV snapshot into its own track DB, so the system can keep earning evidence toward an edge instead of silently re-reading stale observations.

**Why this priority**: The current money path is blocked by missing edge. If the forward paper DBs are read-only, the evidence engine cannot move forward even when workflows look fresh.

**Independent Test**: Can be tested by checking that `observe paper-track-run <track> <capital>` repairs writability for the selected `data/forward_*.db` files before `backfill-bars`, without touching live data.

**Acceptance Scenarios**:

1. **Given** a forward paper DB exists but is not writable by the application user, **When** the fixed observe helper runs `paper-track-run`, **Then** it restores owner/write bits for that track DB and the paper prep can write new bars.
2. **Given** a track DB does not exist yet, **When** the fixed observe helper runs `paper-track-run`, **Then** the `data/` directory is writable by the application user so the paper-only DB can be created.
3. **Given** any forward track, **When** the helper repairs storage, **Then** it repairs only that track's `forward_*.db`, write-ahead log, shared-memory file, and track halt flag.

---

### User Story 2 - Preserve Live-Money Safety Boundaries (Priority: P1)

As the operator, I need this repair to stay inside paper-only evidence production and not touch live orders, live capital, live strategy, secrets, audit logs, or the live halt flag.

**Why this priority**: The fastest path to real money is better evidence, not bypassing the gates that protect the account.

**Independent Test**: Can be tested by inspecting the helper and workflow tests: the repair path excludes `data/auto_invest.db`, `data/halt.flag`, `.env`, live sentinels, live order commands, shell eval, and service control.

**Acceptance Scenarios**:

1. **Given** the live audit/order DB exists, **When** `paper-track-run` repairs storage, **Then** `data/auto_invest.db` is not modified.
2. **Given** the live halt flag exists, **When** `paper-track-run` repairs storage, **Then** `data/halt.flag` is not created, deleted, chmodded, or chowned.
3. **Given** the workflow is manually dispatched, **When** it runs through the observe gateway, **Then** it remains paper-only and places zero broker orders.

### Edge Cases

- A `forward_*.db-wal` or `forward_*.db-shm` file exists from a prior SQLite run and is owned by root: the helper must repair it with the matching DB.
- A track halt file exists: only the track-specific `data/forward_*.halt.flag` may be touched; the live `data/halt.flag` remains observation-only.
- The `data/` directory is missing or root-owned: it may be created or made writable for the application user, but no live DB files are chowned recursively.
- An unsafe path is ever introduced into a track config: the helper must fail closed before chown/chmod.

## Requirements

### Functional Requirements

- **FR-001**: The observe helper MUST ensure paper track storage is writable before `backfill-bars`, `rebalance-once --mode paper`, and `nav-snapshot --mode paper`.
- **FR-002**: The storage repair MUST be limited to `data/forward_*.db`, `data/forward_*.db-wal`, `data/forward_*.db-shm`, and `data/forward_*.halt.flag` for the selected track.
- **FR-003**: The storage repair MUST NOT touch `data/auto_invest.db`, `data/halt.flag`, `.env`, live request sentinels, whitelist/caps, capital settings, audit logs, or live strategy files.
- **FR-004**: The workflow and helper MUST remain paper-only for forward track prep and MUST NOT submit broker orders or arm live trading.
- **FR-005**: The helper MUST fail closed if a configured paper storage path does not match the allowed forward-paper path pattern.
- **FR-006**: Tests MUST prove the writability repair exists, is called before paper prep, and excludes live-money files.
- **FR-007**: Post-deploy verification MUST rerun the forward paper workflow or an equivalent observe path and confirm paper prep no longer fails with `attempt to write a readonly database`.

### Key Entities

- **Forward Paper Track DB**: A per-track SQLite database such as `data/forward_global.db` that stores paper-only bars, paper positions, and NAV snapshots.
- **Track Halt Flag**: A per-track halt flag such as `data/forward_global.halt.flag` that isolates paper track gates from the live halt flag.
- **Observe Helper**: The root-installed fixed-command helper that validates a command and then runs approved operations as the application user.
- **Live-Money Files**: `data/auto_invest.db`, `data/halt.flag`, `.env`, and live strategy/capital sentinels. These are explicitly out of scope for this repair.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Focused unit tests prove the helper repairs only forward paper storage and never names live DB or live halt files in the repair block.
- **SC-002**: Shell syntax checks pass for `deploy/observe-on-instance.sh` and related SSH boundary helper scripts.
- **SC-003**: A post-deploy forward paper run reports `prep ssh_exit=0` for the paper tracks, or any remaining failure is different from `OperationalError: attempt to write a readonly database`.
- **SC-004**: `money-path` and `capital-path-readiness` continue reporting `PREVIEW_ONLY` / `NO_EDGE_YET` unless the existing evidence gates independently change; this repair must not bypass them.
- **SC-005**: Full validation passes: focused tests, full pytest, ruff, HANDOFF fact check, strict harness, PR quality gate, and sidecar truth checks.

## Assumptions

- The latest forward paper prep failures are caused by file ownership or mode drift on server-side paper DB files, not by a strategy logic failure.
- Repairing paper DB writability is safer than bypassing the forward evidence gate, because it restores the existing paper-only evidence path.
- The existing `observe paper-track-run` command is already approved to mutate paper-only DBs; this change restores that intended capability after permission drift.
- This work does not make real money live. It only lets the evidence pipeline keep moving toward the existing gates.

## Release Ledger

completed_candidate_id: candidate-forward-paper-db-writability
next_candidate_id: none
