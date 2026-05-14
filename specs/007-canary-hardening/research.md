# Phase 0 Research — Hardened Canary

**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)
**Date**: 2026-05-14

Decisions are numbered `R-C<n>`. Each entry: Decision → Rationale → Alternatives considered → Validation.

---

## R-C1 — Baseline rev: last `CANARY_PASSED`, fall back to `origin/main`

**Decision**: The canary CLI's `--baseline-rev` defaults to the commit SHA in the most recent `CANARY_PASSED.payload.candidate_rev` audit row. If no prior `CANARY_PASSED` is recorded, baseline defaults to `origin/main` (the fetched main HEAD). The operator can override with an explicit `--baseline-rev <sha-or-ref>`.

**Rationale**: This gives the latency/cost regression metrics a meaningful "previous version" reference (FR-C01 #4, #5) — the last version that actually passed the canary, NOT just whatever happens to be on main. Falling back to `origin/main` is the bootstrapping case (first canary run after spec 007 ships). Recording the resolved SHA in `canary-run.json` preserves reproducibility (SC-C04).

**Alternatives considered**:
- *Always `origin/main~1`*: catches "did the most recent merge regress?" but misses the case where main has accumulated multiple unmerged canary runs (which under v3.0.0 IX.B-2 is the normal mode — merges land freely; deploys gate via canary).
- *Operator-provided baseline tag (e.g. `canary-baseline`)*: pushes a git-tag-maintenance burden onto the operator. Rejected for autonomy.
- *Telemetry-derived baseline (last 30 days production p95)*: would require the candidate code to be running somewhere to source telemetry from. The candidate hasn't deployed yet — that's the whole point of the canary. Rejected.

**Validation**: `tests/unit/test_canary_diff.py::test_baseline_resolution_chains_through_audit_log` injects two prior `CANARY_PASSED` rows and asserts the harness picks the most recent.

---

## R-C2 — Window-replay metrics: re-use spec 008's `BacktestRun` outputs verbatim

**Decision**: The window-replay metrics (drawdown, risk-gate-violation-count, audit-integrity, latency p95) for both candidate and baseline come from a pair of `auto_invest.backtest.run.run_backtest(...)` invocations. The canary harness does NOT re-implement metric math; it diffs the two `BacktestRun` summaries.

**Rationale**: SC-C04 (reproducibility) and FR-C05 (use spec 008's replay) both demand this. Spec 008 already ships byte-identical reproducibility for backtest outputs; the canary inherits that for free. Re-implementing PnL/drawdown math would risk drift between live worker and canary.

**Alternatives considered**:
- *Custom replay loop in `canary/replay_window.py`*: duplicates spec 008's R-B13 Path-B design without benefit. Rejected.
- *Stream metrics from audit_log alone*: misses per-bar PnL series needed for drawdown computation.

**Validation**: `tests/integration/test_canary_end_to_end.py` produces a canary-run.json whose `replay_window.candidate.drawdown_pct` matches the `BacktestRun.metrics.max_drawdown_pct` directly read from the spec-008 artefact.

---

## R-C3 — Synthetic-shock dates: reuse `config/synthetic_shocks.toml` from spec 008

**Decision**: The canary's synthetic-shock pass invokes `auto_invest.backtest.synthetic_shocks.resolve_synthetic_shocks()` (already shipped under spec 008) and runs spec 008's `run_backtest(synthetic_shock=True)` for each resolved date. No duplicate date list in the canary package.

**Rationale**: The synthetic-shock date set is the operator-authored safety surface (FR-C03). It must have a single source of truth. Spec 008 already loads it from `config/synthetic_shocks.toml` and resolves the `most_recent_quarterly_opex` dynamic entry. Spec 007 is a consumer.

**Alternatives considered**:
- *Maintain `config/canary_shocks.toml` separately*: doubles operator maintenance burden and risks drift. Rejected.
- *Hard-code the four dates in canary code*: violates IX.C "no hard-coded Kernel-adjacent paths". Rejected.

**Validation**: `tests/unit/test_canary_metrics.py::test_shock_dates_resolve_from_spec_008_config` patches the spec-008 loader and asserts the canary harness picks up the patch.

---

## R-C4 — Property fuzz target: pure-math against `risk.gates`, NOT integrated order flow

**Decision**: The Hypothesis suite imports `auto_invest.risk.gates` directly and exercises the four cap gates (`per_trade_cap_gate`, `per_symbol_cap_gate`, `global_exposure_gate`, plus `whitelist_gate` for completeness) with randomly generated `(OrderRequest, SizingCaps, current_state)` triples. The post-condition is `per_trade ≤ per_symbol ≤ global` evaluated on the gate-allowed envelope. Order-flow integration is NOT fuzzed — that's covered by the synthetic-shock replay.

**Rationale**: SC-C02 demands ≥0.99 catch rate on off-by-one bugs within 10k iterations. Pure-math fuzz at the K1 boundary is the most efficient signal — synthetic-shock replay is per-day, slow, and would need ~100k days to hit similar coverage. Hypothesis's shrinking gives a minimal counterexample, which is what the operator wants when forensic-reading `property-fuzz/counterexamples.json`.

**Alternatives considered**:
- *Full integrated fuzz (random order + random market state)*: slower per iteration; shrinks poorly; redundant with synthetic-shock replay. Rejected.
- *Stateful fuzz against the entire order pipeline*: out of scope for v1; could be a future spec on top of spec 007.

**Validation**: `tests/unit/test_canary_fuzz.py::test_off_by_one_in_per_trade_cap_caught_within_10k` monkey-patches a deliberate `>=` → `>` bug into `per_trade_cap_gate` and asserts the fuzz pass rejects within the budget.

---

## R-C5 — Hypothesis becomes a runtime dep, not test-only

**Decision**: Add `hypothesis ^6` to `pyproject.toml`'s main dependencies (not `[tool.uv.dev-dependencies]`). Reason: the canary CLI (`python -m auto_invest.canary fuzz`) invokes Hypothesis programmatically as part of an operator-facing acceptance pipeline; it is not just a test-time tool.

**Rationale**: Treating Hypothesis as test-only would force the canary harness to depend on the project's dev environment for production runs, which violates the principle that the live-deploy gate cannot depend on dev-only infrastructure.

**Alternatives considered**:
- *Re-implement a minimal property checker in-tree*: gives up shrinking + database-of-failing-seeds. Rejected.
- *Make Hypothesis dev-only and require operators to install dev deps for canary*: dev-deploy coupling; rejected.

**Validation**: `pyproject.toml` diff; `tests/unit/test_canary_fuzz.py` import path.

---

## R-C6 — Acceptance is all-or-nothing per FR-C06; no per-metric override

**Decision**: The harness computes all 5 metrics; the final decision is `passed` ⇔ every metric is inside its band AND zero counterexamples from fuzz AND zero risk-gate violations from shock replay. There is NO operator override flag in v1 (`--ignore-metric=drawdown` does not exist).

**Rationale**: FR-C06 is intentional defense-in-depth against tuner over-eagerness. v3.0.0's IX.D supremacy applies to procedural rules, NOT to trading-safety invariants (principles I-VII, VIII.A); FR-C06 inherits from VIII.A's no-mid-session-deploy spirit at the deploy boundary. The operator can amend bands via `config/canary_bands.toml` if a band is wrong; per-run overrides are not permitted.

**Alternatives considered**:
- *Soft-pass with operator confirmation*: re-introduces the synchronous-handoff overhead IX.D eliminated. Rejected.
- *Tier-based override (L2 strict, L3 lax)*: spec 005 still a stub; premature. Rejected for v1.

**Validation**: `tests/unit/test_canary_metrics.py::test_four_of_five_does_not_pass` asserts 4-out-of-5 still produces `CANARY_FAILED`.

---

## R-C7 — Kernel-touch detection: git diff against baseline-rev, NOT working tree

**Decision**: The harness computes the candidate-vs-baseline diff via `git diff --name-only <baseline-rev>..<candidate-rev>` and intersects the resulting path list with paths from `auto_invest.deploy.load_kernel_manifest()`. The working tree is NOT consulted — the canary tests a committed candidate, not local edits. (Spec 008's `kernel_pre_flight` covers the working-tree case for backtests; the canary's job is committed-rev evaluation.)

**Rationale**: Under v3.0.0 the canary is the production-deploy gate; production deploys ALWAYS deploy a committed SHA, never a working tree. Working-tree handling in spec 008 was for ad-hoc backtests; spec 007's contract is stricter.

**Alternatives considered**:
- *Refuse to start if working tree is dirty*: too strict; the operator might have unrelated local edits while running a canary against a remote SHA. Rejected.
- *Diff working-tree against candidate-rev*: doesn't reflect the actual deploy unit. Rejected.

**Validation**: `tests/unit/test_canary_diff.py::test_working_tree_ignored` asserts a dirty working tree does NOT change the kernel-touch verdict.

---

## R-C8 — `CANARY_KERNEL_TOUCH_DETECTED` emitted BEFORE the metric battery, not after

**Decision**: If the candidate's diff intersects `kernel.toml` paths, the harness emits `CANARY_KERNEL_TOUCH_DETECTED` immediately after `CANARY_ENTERED` and before kicking off replay. The payload carries the list of touched kernel groups (K1..K6, K-meta) and the touched file paths. The metric battery still runs to completion; pass/fail is independent.

**Rationale**: Forensic clarity (operator can `grep audit_log` for the touch event without waiting for the full run to complete) plus deterministic ordering in `canary-run.json` (the touch list is part of the run header, not buried in the decision).

**Alternatives considered**:
- *Emit only on failure*: hides the forensic signal on a passing kernel-touched run, which is exactly the case operators most want to inspect. Rejected.
- *Emit per-touched-file*: noisy; aggregated event is enough for forensic search. Rejected.

**Validation**: `tests/integration/test_canary_kernel_touch.py` asserts emission ordering via `correlation_id` and `ts_utc`.

---

## R-C9 — `data/canary/<run_id>/` layout matches spec 008's pattern exactly

**Decision**: Per-canary-run artefacts mirror spec 008's per-backtest-run layout: a directory keyed by `run_id` (UUID4), containing one top-level `canary-run.json`, one `metrics.csv`, and sub-directories for `shock-replay/<date>/`, `replay-window/{candidate,baseline}/`, and `property-fuzz/`. Spec 008's per-backtest-run artefacts produced by the canary's nested calls are stored under those sub-paths (copy, not symlink — symlinks break on Windows-using operators).

**Rationale**: Operator already knows the spec-008 layout (HANDOFF-008.md is in main); shared conventions reduce cognitive load. Copying (vs. symlinking) keeps the canary run self-contained for archival — the operator can rsync `data/canary/<run_id>/` to a different host without dragging in `data/backtest/`.

**Alternatives considered**:
- *Symlink to existing `data/backtest/<sub-run-id>/`*: breaks self-containment; rejected.
- *Single flat JSON*: loses the per-shock-day audit_log slices that FR-C07 explicitly enumerates. Rejected.

**Validation**: `tests/unit/test_canary_report.py::test_layout_matches_fr_c07` walks the directory and asserts every FR-C07-required path exists.

---

## R-C10 — Acceptance-bands config: TOML with explicit per-tier sections

**Decision**: `config/canary_bands.toml` ships with `[L2]` and `[L3]` sections, each containing the five band keys (`pnl_drawdown_pct`, `risk_gate_violations`, `audit_integrity_failures`, `latency_p95_regression_pct`, `llm_cost_regression_pct`) plus the per-tier window length (`trading_days`). Defaults match FR-C01 / FR-C02. The operator may add `[L4]` later if spec 005's L4 tier becomes a thing.

**Rationale**: Per-tier configurability is a stated need (FR-C01 says "configurable per change class"). TOML matches the rest of the project's config files (`rules.toml`, `synthetic_shocks.toml`, `caps.toml`).

**Alternatives considered**:
- *Single global section with `--strict` / `--lax` flags*: loses the per-tier intent. Rejected.
- *YAML*: introduces a YAML dependency the project does not yet have. Rejected.

**Validation**: `tests/unit/test_canary_bands_toml.py::test_default_bands_match_spec_fr_c01` round-trips the shipped file against spec FR-C01 values.

---

## R-C11 — `CANARY_PASSED` / `CANARY_FAILED` payload is the run header, not a metric snapshot

**Decision**: The terminal audit event's payload contains `canary_run_id`, `candidate_rev`, `baseline_rev`, `tier`, `window_trading_days`, `started_at`, `finished_at`, `outcome` (`passed` | `failed`), and `failing_metrics: list[str]` (empty on pass). The full per-metric numeric snapshot lives in `canary-run.json`; the audit row is a forensic index pointing to it.

**Rationale**: Audit-row payloads are read often (every deploy check, every operator audit query) and should be small. The full snapshot in JSON-on-disk is read rarely (forensic inspection). Keeping the audit row small preserves `audit_log` query performance.

**Alternatives considered**:
- *Embed all 5 metrics in the audit payload*: bloats every row; rejected.
- *Emit one `CANARY_METRIC` row per metric*: cardinality explosion; rejected.

**Validation**: `tests/unit/test_canary_audit_events.py::test_canary_passed_payload_size_bounded` asserts the serialized payload is < 1 KB.

---

## R-C12 — Spec 006 deploy-eligibility check (out-of-scope but documented contract)

**Decision**: Spec 006's deploy automation, when it ships, MUST consult `audit_log` for the most recent `CANARY_PASSED` row whose `payload.candidate_rev` matches the SHA about to be deployed. If no such row exists, the deploy is refused with `DEPLOY_BLOCKED_NO_CANARY`. This contract is documented here for spec 006's future implementation; spec 007 ships the producer side only.

**Rationale**: Establishing the contract here means spec 006's runner can be implemented without re-litigating the integration shape. Spec 006 is currently kernel-touch-guard only (runner pending per HANDOFF.md); spec 007 unblocks the runner.

**Alternatives considered**:
- *Defer the integration contract to spec 006 implementation*: risks drift; rejected.
- *Implement the deploy-side check in spec 007*: scope creep; rejected.

**Validation**: documented in `contracts/canary-run-json.md` § "Spec 006 integration"; no test in spec 007 (the producer side test is `tests/unit/test_canary_audit_events.py`).
