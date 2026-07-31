# Contract: Forward Paper Storage Repair

## Command Surface

The existing forced-command gateway continues to expose:

```text
observe paper-track-run <track> <capital>
```

where:

- `<track>` must be one of `trend`, `notrend`, `rmbeta`, `multiasset`, `global`, `globalfixed`, `wide`.
- `<capital>` must be a decimal number.

## Pre-Run Storage Contract

Before paper prep runs, the helper must:

1. Resolve the selected track to exactly one `TRACK_DB` and one `TRACK_HALT`.
2. Ensure `data/` exists for the application user.
3. For existing selected files only, restore ownership to the application user and mode to owner read/write only.
4. Refuse any storage path outside the allowed forward-paper patterns.

## Safety Contract

The repair must not:

- Touch `data/auto_invest.db`.
- Touch `data/halt.flag`.
- Read or write `.env` beyond the existing CLI arguments.
- Change live strategy, capital, whitelist/caps, or audit logs.
- Submit broker orders.
- Add arbitrary shell evaluation or new gateway command shapes.
