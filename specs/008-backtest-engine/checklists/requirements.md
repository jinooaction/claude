# Specification Quality Checklist: Backtest Engine

**Purpose**: Validate specification completeness and quality before proceeding to `/speckit-clarify` and `/speckit-plan`.
**Created**: 2026-05-07
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
  - The spec references the *existing* live pipeline (Worker.tick, risk-gate stack, audit_log) by role, not by implementation. Mentions of `worker/loop.py` and `worker/schedule.py` appear only in the context of the Kernel manifest, which is itself a constitutional artifact, not an implementation choice introduced here. SQLite + WAL is mentioned because the existing audit log already uses it (constitution IV).
- [x] Focused on user value and business needs
  - Each user story explains the operator-facing value (P1 stories 1 & 2) and the constitutional value (story 3, audit retention; story 4, forensic artifact).
- [x] Written for non-technical stakeholders
  - The "Why this feature exists" section frames the feature in constitutional terms (autonomous merge gate); the user stories are operator-facing scenarios. Risk-gate / audit-log terminology is project vocabulary, not generic engineering vocabulary.
- [x] All mandatory sections completed
  - User Scenarios & Testing, Requirements, Success Criteria all present and populated.

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
  - All five clarifications resolved in the 2026-05-07 `/speckit-clarify` session and recorded in the spec's `## Clarifications` section. FR-B06 (vendor), FR-B07 (fill model), FR-B17 (migration kernel-touch policy), FR-B18 (OPEX freeze), FR-B21 (promotion thresholds) all updated in place; previous markers removed.
- [x] Requirements are testable and unambiguous
  - Each FR-B## either has a binary acceptance condition (e.g. FR-B12 byte-identical reports), a numerical threshold (FR-B21 default thresholds), or a referenced contract (FR-B13 contracts directory). The three NEEDS-CLARIFICATION items are bounded — once the operator picks an option, the FR becomes testable without further spec edits.
- [x] Success criteria are measurable
  - SC-B01..SC-B07 each name a quantifiable outcome (single-command, 100% gate-coverage, hash-equality across ≥100 runs, 30-second wall-clock, single SQL query, ≥10 000 fuzz iterations).
- [x] Success criteria are technology-agnostic (no implementation details)
  - SC-B05 names a wall-clock budget but no framework. SC-B06 names "single SQL query" against the existing audit_log table — that table is a project-level contract from spec 001 / constitution IV, not a v8 implementation detail.
- [x] All acceptance scenarios are defined
  - Each P1 user story has 2–3 Given/When/Then scenarios; P2 stories have 2 each.
- [x] Edge cases are identified
  - Nine edge cases enumerated, covering data completeness, corporate actions, whitelist exit, delisting, audit-log concurrency with the live worker, dataset hash drift, fill-model boundary cases, NaN bars, and timeframe-vs-resolution mismatch.
- [x] Scope is clearly bounded
  - "Out of scope for spec 008" enumerates eight explicit exclusions (hardened canary itself, autonomous tuner, intraday bars, multi-strategy parallel runs, walk-forward, benchmark comparison, fees/taxes, level-2 simulation).
- [x] Dependencies and assumptions identified
  - Dependencies section lists three hard prerequisites (already on main) plus one hard consumer (spec 007). Assumptions section captures seven explicit reasonable-default choices.

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
  - FR-B01..B21 are tied through user-story acceptance scenarios (FR-B01/B02/B03 → User Story 1 acceptance #1; FR-B11/B12/B13 → User Story 2 #1 and Story 4 #1, etc.).
- [x] User scenarios cover primary flows
  - Story 1 (canary-harness consumer flow), Story 2 (operator manual-backtest flow), Story 3 (audit retention), Story 4 (artifact retention). Stories 1 and 2 are the two independent P1 MVP slices.
- [x] Feature meets measurable outcomes defined in Success Criteria
  - SC-B01..B07 trace to FR-B11 (report contents), FR-B01..B03 (gate-coverage), FR-B12 (reproducibility), FR-B14..B17 (audit invariants), FR-B18..B19 (synthetic-shock dataset).
- [x] No implementation details leak into specification
  - The spec references existing constitutional artifacts (kernel.toml, audit_log) and existing pipeline roles (risk-gate, Worker.tick). It does not propose a new framework, library, or architectural pattern; that lives in `/speckit-plan`.

## Constitution alignment (project-specific)

- [x] Spec explicitly states it is **not a Kernel change** (constitution IX.B-1).
  - Stated in the Input field, in "Why this feature exists", in FR-B02, and in the Constitution touchpoints table.
- [x] Spec consumes — and does not duplicate — existing safety-critical code paths.
  - FR-B01 forbids forked risk-gate logic; FR-B02 forbids editing K1/K2/K4/K6 files.
- [x] Spec extends — and does not parallel — the append-only audit log.
  - FR-B14..B17 reuse the existing `audit_log` table; SC-B06 forbids a parallel backtest log.
- [x] Spec recognises the migration-naming kernel-edge case.
  - FR-B17 surfaces the question explicitly so the operator can resolve it during `/speckit-clarify` rather than discovering it during deploy-guard rejection.

## Notes

- All clarifications closed during the 2026-05-07 `/speckit-clarify` session:
  1. **OHLCV vendor** (FR-B06) → yfinance + KIS historical, both via a vendor-agnostic adapter interface; Polygon and CSV deferred.
  2. **Fill model** (FR-B07) → hybrid: limit orders use range-aware-at-limit; market orders (per-symbol opt-in only) use next-bar-open + 5 bps default slippage. Branched on the live `order_type`.
  3. **Migration kernel-touch policy** (FR-B17) → new migration is added to `kernel.toml` K4 in the same change set as spec 008's first landing. That landing is a one-time K-meta human-merge event; subsequent engine work is non-Kernel.
  4. **Promotion verdict thresholds** (FR-B21) → v1 baseline frozen: `total_return_pct ≥ 0`, `max_drawdown_pct ≤ 10`, `sharpe ≥ 0.5`. Advisory only in v1; binding gate is spec 007.
  5. **Synthetic-shock OPEX freeze** (FR-B18) → `synthetic_shock_v1` membership frozen at 2026-05-07 to: 2020-03-12, 2020-04-20, 2024-08-05, 2026-03-20. Subsequent OPEX days do not auto-roll.
- Spec is now ready for `/speckit-plan`. Recommended next command: `/speckit-plan`.
