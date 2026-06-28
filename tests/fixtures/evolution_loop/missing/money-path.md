# money-path partial fixture

timestamp_utc: 2026-06-29T00:00:00Z
producer_commit: 9e1e492
status: PREVIEW_ONLY
signal: latest_intent_loss

This fixture intentionally includes only the money-path sidecar. All other
required evidence surfaces are absent so tests can prove missing inputs are
reported as evidence freshness issues instead of strategy failures.
