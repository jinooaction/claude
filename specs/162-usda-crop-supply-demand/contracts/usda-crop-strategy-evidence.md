# Contract: USDA Crop Strategy Evidence

The canonical `strategy_factory.json` MUST expose:

- `schema_version`, `gate_version`, `code_commit`, `timestamp_utc`, and `batch_id`
- exactly 16 candidates and 16 complete current trials
- exactly 704 prior and 720 total unique audit records
- USDA source coverage, URLs, hashes, freshness, and split fingerprint
- same-date archive aliases accepted only when their preregistered crop inputs match
- development winner selected without holdout access
- a descriptive all-candidate holdout scan that can never authorize promotion
- at least 120 holdout months and 10/25/50bp cost metrics
- unchanged full and paper gate rows with blocking flags
- calibrated false-positive and actual-holdout detection-power context
- provisional, selected, and paper candidate identities
- exact latest target weights and their fingerprint
- explicit live implementation/parity status
- safety declaration: no broker, orders, capital, whitelist, caps, or arming changes

Any count mismatch, duplicate fingerprint, malformed or conflicting source, failed control, code mismatch, stale evidence, or live-parity mismatch MUST fail closed before capital consumption.
