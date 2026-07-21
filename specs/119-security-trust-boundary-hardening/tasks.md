# Tasks: Security Trust Boundary Hardening

- [x] T001 Establish feature pointer and SDD artifacts for grade 3 security work.
- [x] T002 Add CI guard scripts for secure SSH, numeric validation, and public sidecar redaction.
- [x] T003 Pin third-party GitHub Actions and enforce strict known_hosts plus non-root SSH.
- [x] T004 Harden go-live fail-closed behavior and environment rollback.
- [x] T005 Require exact code and ruleset hashes for canary approval evidence.
- [x] T006 Replace deploy PID race with atomic process-bound locking.
- [x] T007 Harden broker token cache permissions and atomic writes.
- [x] T008 Block new BUY exposure on stale intent/submitting and missing open-position marks.
- [x] T009 Strengthen unknown broker-order recovery matching.
- [x] T010 Add verified reduce-only/oversell classification to risk gates and order routing.
- [x] T011 Redact public sidecar evidence before publication.
- [x] T012 Add focused regression tests and workflow scanners.
- [x] T013 Run focused and full validation.
- [x] T014 Prepare the PR body, commit, push, open PR, and merge if gates allow.
- [x] T015 Add a server-side SSH boundary repair script for root key retirement,
  forced-command deploy identity provisioning, and gateway-only deploy workflow
  calls.
- [x] T016 Require the GitHub `production` environment for live mode, real-order,
  and halt-release workflows.
