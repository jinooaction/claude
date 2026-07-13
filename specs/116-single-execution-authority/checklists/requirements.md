# Requirements Checklist: Single Execution Authority

- [x] Goal separates broker write authority from strategy planning.
- [x] Non-goals exclude real orders, sentinel arming, capital changes, and cap changes.
- [x] Lock must be acquired before live gate evaluation, not only around HTTP POST.
- [x] Cancel and submit use the same authority.
- [x] Paper and dry-run behavior remains non-mutating.
- [x] Verification includes focused regressions, full tests, lint, handoff facts, and strict harness.
