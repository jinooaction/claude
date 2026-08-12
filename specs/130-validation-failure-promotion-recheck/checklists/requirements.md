# Requirements Checklist: Validation Failure Promotion Recheck Contract

**Feature**: `specs/130-validation-failure-promotion-recheck/spec.md`

- [x] Specification identifies the selected autonomous-work candidate.
- [x] User stories are independently testable.
- [x] Requirements preserve no-live safety boundaries.
- [x] Missing sidecars are treated as evidence wait, not success.
- [x] Latest learning-ledger entry precedence is defined.
- [x] Fingerprint inputs avoid volatile wall-clock run ids.
- [x] Completed candidate marker is specified for released-work.
- [x] Rollback path is simple: revert module, probe, tests, and spec 130 pointer.
