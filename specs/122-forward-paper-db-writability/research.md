# Research: Forward Paper DB Writability

## Decision: Repair only selected forward paper storage inside `observe paper-track-run`

**Rationale**: The latest forward paper sidecar shows every prep command failing at SQLite insert with `OperationalError: attempt to write a readonly database`. The helper already intends `paper-track-run` to mutate paper-only DBs, so the smallest correct repair is to restore writability for the selected paper DB and its SQLite sidecar files before the paper prep starts.

**Alternatives considered**:

- Workflow-level retry: rejected because retrying cannot fix a read-only DB file.
- Chowning all of `data/`: rejected because it is broader than needed and could touch live DB or live halt files.
- Running the paper prep as root: rejected because it weakens the app-user boundary and can recreate the same root-owned DB drift.

## Decision: Keep live-money files explicitly out of scope

**Rationale**: The user wants faster progress toward real money, but the safe way is to restore evidence accumulation. Live files such as `data/auto_invest.db`, `data/halt.flag`, `.env`, live strategy config, and capital sentinels are not needed for paper prep writability.

**Alternatives considered**:

- Repair live halt flag permissions together with paper flags: rejected because the live halt flag is an operator/safety surface.
- Repair `data/auto_invest.db` ownership opportunistically: rejected because the observed failure is in `forward_*.db`, not the live DB.

## Decision: Add tests as command-surface invariants

**Rationale**: The risk is not algorithmic complexity; the risk is accidentally widening the root helper. Text-based tests already guard this repository's SSH boundary and paper workflow contracts.

**Alternatives considered**:

- Full shell integration test with sudo/chown: rejected locally because it would require root-like filesystem behavior and still would not prove the production server state.
