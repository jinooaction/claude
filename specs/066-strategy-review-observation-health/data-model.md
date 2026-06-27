# Data Model: Strategy Review Observation Health

## TrackResult

- `key`: Stable track identifier from `scripts/forward_tournament_probe.py`.
- `is_incumbent`: Whether this is the live validation track.
- `verdict`: Parsed forward verdict label.
- `n_obs`: Number of forward observations.
- `min_obs`: Minimum observations required for comparability.
- `comparability`: `COMPARABLE`, `PREMATURE`, or `UNKNOWN`.

Validation:

- `UNKNOWN` means the track verdict cannot be trusted for candidate-quality comparison.
- `PREMATURE` means the track is known but below its statistical comparison boundary.
- `COMPARABLE` means `n_obs >= min_obs` and the verdict label is usable.

## Observation Health

- `track_count`: Number of configured tournament tracks.
- `known_count`: Number of tracks with parseable verdicts.
- `unknown_count`: Number of tracks with missing or unusable verdicts.
- `max_n_obs`, `min_n_obs`: Observation span among known tracks.
- `lagging_keys`: Known tracks with at least two fewer observations than the maximum.
- `observation_health`: `OK`, `DEGRADED`, or `BLOCKED`.
- `observation_note`: Operator-facing explanation.

Validation:

- No known verdicts -> `BLOCKED`.
- Incumbent unknown -> `BLOCKED`.
- Any unknown non-incumbent track -> `DEGRADED`.
- At least one comparable known track and at least one below-minimum known track -> `DEGRADED`.
- All known tracks below minimum -> `OK`, with `lagging_keys` retained as progress metadata.
- All known tracks comparable -> `OK`, with `lagging_keys` retained as forensic metadata.

## TournamentLeaderboard

The existing serialized leaderboard includes observation-health fields and sorted track rows.

Validation:

- This feature does not change the JSON schema keys.
- Consumers that only check `observation_health` keep working.
- Consumers that display `lagging_keys` still see lagging candidates even when health is `OK`.
