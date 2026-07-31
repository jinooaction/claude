# Data Model: Forward Paper DB Writability

## Entity: ForwardPaperTrack

- **track**: One of `trend`, `notrend`, `rmbeta`, `multiasset`, `global`, `globalfixed`, `wide`.
- **portfolio_path**: The paper portfolio config paired with the track.
- **db_path**: The track-specific SQLite DB path under `data/forward_*.db`.
- **halt_path**: The track-specific halt flag under `data/forward_*.halt.flag`.
- **construct_top_n**: Optional universe-construction limit used by equity ranking tracks.

## Entity: PaperStorageRepair

- **target_paths**: The selected track DB, SQLite write-ahead log, SQLite shared-memory file, and selected track halt flag.
- **allowed_patterns**: `data/forward_*.db`, `data/forward_*.db-wal`, `data/forward_*.db-shm`, `data/forward_*.halt.flag`.
- **owner**: Existing application user, `auto-invest` by default.
- **mode**: Owner read/write, no group or world access.

## State Transitions

1. Track storage is missing or not writable.
2. `observe paper-track-run` validates track and capital.
3. Helper creates the `data/` directory for the application user if needed.
4. Helper repairs only existing selected forward paper storage files.
5. Paper prep runs as the application user.
6. Forward paper sidecar reports prep success or a non-writability failure.

## Explicit Non-Entities

- `data/auto_invest.db` is not part of this feature.
- `data/halt.flag` is not part of this feature.
- `.env`, live strategy files, live request sentinels, audit logs, capital settings, whitelist/caps, and broker order state are not part of this feature.
