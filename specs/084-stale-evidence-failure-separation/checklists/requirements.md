# Requirements Checklist: Stale Evidence Failure Separation

- [x] Scope is read-only and excludes broker, order, capital allocation, live settings, whitelist/caps, and paid external services.
- [x] Released candidates are separated from priority candidates.
- [x] Stale and missing sidecars are represented as observability issues.
- [x] Money-path readiness and live-money gates remain authoritative and unchanged.
- [x] Probe manifest and workflow path filters include new inputs.
- [x] Tests cover unit routing, probe manifest, JSON output, Markdown output, and workflow safety.
