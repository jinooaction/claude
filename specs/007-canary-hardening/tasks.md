---

description: "Tasks for spec 007 — Hardened Canary for Autonomous Production-Deploy"
---

# Tasks: Hardened Canary for Autonomous Production-Deploy

> ✅ **SHIPPED — 전부 완료, main 에 머지됨.** `src/auto_invest/canary/`
> (run·metrics·shock·fuzz·diff·bands·report·data_model·replay_window·cli) 구현
> 완료, 카나리 테스트 93개 통과. K4 추가 이벤트 4종(`CANARY_ENTERED`/`PASSED`/
> `FAILED`/`KERNEL_TOUCH_DETECTED`)은 `audit.py` 에 존재. `config/canary_bands.toml`
> 존재. T004(.gitignore `data/canary/`)는 기존 `data/` 무시 규칙으로 이미 커버.
> 이 체크박스들은 한동안 0% 로 표시된 **stale 상태**였음(2026-05-24 재조정). 실제
> 상태는 코드+테스트가 진실. spec 007 은 자율 프로덕션 배포의 안전 게이트(IX.B-2)로
> 가동 준비 완료.

**Input**: Design documents from `/specs/007-canary-hardening/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Tests ARE included. Spec 007 IS a safety mechanism; FR-C04 and SC-C02 / SC-C04 are property assertions that require automated coverage.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are absolute under repo root `/home/user/claude/`

## Path Conventions

- Source: `src/auto_invest/canary/` (new package)
- K4 touch: `src/auto_invest/persistence/audit.py` (additive only)
- Tests: `tests/unit/`, `tests/integration/`
- Config: `config/canary_bands.toml` (new file)
- Artefact root: `data/canary/` (gitignored, created at runtime)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency setup, package skeleton.

- [x] T001 Add `hypothesis` to `[project.dependencies]` in `pyproject.toml`; run `uv sync` and commit the updated `uv.lock`.
- [x] T002 [P] Create empty package skeleton: `src/auto_invest/canary/__init__.py`, `src/auto_invest/canary/__main__.py` (with `if __name__ == "__main__": from .cli import main; main()`), and `tests/unit/__init__.py` if missing.
- [x] T003 [P] Create `config/canary_bands.toml` populated with the L2 + L3 defaults from `contracts/canary-bands-toml.md` (drawdown 3.0/2.0, gate-violations 0, audit-integrity 0, latency 20.0/15.0, llm-cost 10.0/7.5, trading_days 30/45).
- [x] T004 [P] Add `data/canary/` to `.gitignore`.

**Checkpoint**: Skeleton + deps ready. Continue to foundational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: K4 additive touch + data model + config loader + git diff helper. EVERY user story depends on these. Implement and test these first.

**⚠️ CRITICAL**: No user story work begins until Phase 2 is complete and green.

- [x] T005 K4 additive touch — append four event-type literals (`CANARY_ENTERED`, `CANARY_PASSED`, `CANARY_FAILED`, `CANARY_KERNEL_TOUCH_DETECTED`) to the `EventType` Literal in `src/auto_invest/persistence/audit.py`, and add four pydantic payload models (`CanaryEnteredPayload`, `CanaryPassedPayload`, `CanaryFailedPayload`, `CanaryKernelTouchDetectedPayload`) per `data-model.md` § "Audit-event payloads". This is the only K4 touch in this spec; commit message MUST surface the K4 label.
- [x] T006 [P] Add unit test `tests/unit/test_canary_audit_events.py` covering each new payload's serialisation, the K4-additive contract (no UPDATE/DELETE, no existing literal mutated), and `CanaryPassedPayload` serialized size < 1 KB (R-C11).
- [x] T007 [P] Create `src/auto_invest/canary/data_model.py` with: `CanaryRun`, `KernelTouch`, `CanaryMetrics`, `MetricResult`, `FuzzCounterexample`, `SeedBundle`, plus `TierBands` (used by the config loader) — all frozen pydantic v2 models matching `data-model.md`.
- [x] T008 [P] Add `src/auto_invest/canary/bands.py` exposing `load_bands(path: Path) -> dict[str, TierBands]` and `CanaryBandsConfigError`. Validate per `contracts/canary-bands-toml.md` (reject negative, non-zero on the two count metrics, `trading_days < 30`/`< 45`, unknown tiers).
- [x] T009 [P] Add unit test `tests/unit/test_canary_bands_toml.py` covering: defaults round-trip, missing-key rejection, negative-number rejection, `risk_gate_violations != 0` rejection, `trading_days < 30` rejection, unknown-tier rejection.
- [x] T010 Create `src/auto_invest/canary/diff.py` with: `resolve_rev(ref_or_sha) -> str` (calls `git rev-parse`); `resolve_baseline(audit_conn, candidate_rev) -> str` (queries `audit_log` for latest `CANARY_PASSED.payload.candidate_rev != candidate_rev`; falls back to `origin/main`); `diff_paths(baseline_sha, candidate_sha) -> list[str]` (calls `git diff --name-only`); `intersect_kernel(touched_paths, manifest) -> list[KernelTouch]`.
- [x] T011 [P] Add unit test `tests/unit/test_canary_diff.py` covering: rev resolution (HEAD, tag, SHA); baseline chains through audit log (R-C1); working-tree ignored (R-C7); kernel intersection groups paths by K1..K6/K_meta; empty diff returns empty list.

**Checkpoint**: Foundational layer green. User-story phases can now begin (and may be parallelised).

---

## Phase 3: User Story 1 — Operator-instructed canary run promotes a winning change (Priority: P1) 🎯 MVP

**Goal**: A single CLI invocation (`python -m auto_invest.canary run --tier L2`) evaluates a candidate-vs-baseline pair across the 5-metric battery on a 30-day replay window, emits `CANARY_PASSED` / `CANARY_FAILED`, and writes the full `data/canary/<run_id>/` artefact tree. This is the MVP — without it, no other US works.

**Independent Test**: feed a known-good change (no semantic difference, e.g. a comment-only edit) through `canary run` against the same fixture history spec 008's `test_backtest_end_to_end.py` uses. Verify exit `0`, `CANARY_PASSED` row present, `canary-run.json.outcome == "passed"`, all 5 metrics `inside_band == true`.

- [x] T012 [US1] Add `src/auto_invest/canary/replay_window.py` exposing `replay_window(*, candidate_rev, baseline_rev, window_trading_days, history_dir, audit_conn) -> tuple[BacktestRun, BacktestRun]`. Internally invokes spec 008's `auto_invest.backtest.run.run_backtest(...)` twice (once per rev) — see R-C2. Returns the candidate and baseline summary models. NOTE: this task assumes a clean `git checkout` per rev OR direct pass-through of the cached parquet dataset; choose pass-through since spec 008 already caches by `dataset_version`.
- [x] T013 [P] [US1] Add `src/auto_invest/canary/metrics.py` exposing `evaluate_metrics(candidate, baseline, bands: TierBands, *, audit_baseline_mean: float) -> CanaryMetrics`. Computes the five `MetricResult`s per `data-model.md` § `CanaryMetrics`. Treat the two count metrics with `band_must_equal=0`; the three rate metrics with `band_upper=<tier value>`. `inside_band = (observed <= band_upper) if band_upper else (observed == band_must_equal)`.
- [x] T014 [P] [US1] Add unit test `tests/unit/test_canary_metrics.py` covering: canned-`BacktestRun` pair → 5-metric eval; a 4-of-5 pass still returns `outcome` candidate-failed (R-C6); `band_must_equal=0` with `observed_value=1` is outside band; negative `latency_p95_regression_pct` (improvement) is inside band.
- [x] T015 [US1] Add `src/auto_invest/canary/report.py` exposing `write_report(run: CanaryRun, out_dir: Path) -> Path`. Writes `canary-run.json` (pydantic `model_dump_json(indent=2)` with sort_keys via custom encoder), `metrics.csv` (one row per metric with columns id, observed_value, band_upper, band_must_equal, inside_band, source), and creates the `shock-replay/`, `replay-window/{candidate,baseline}/`, `property-fuzz/` sub-trees (empty for US1; populated in US2). Sort `kernel_touches[].files` and `failing_metrics` lexicographically.
- [x] T016 [P] [US1] Add unit test `tests/unit/test_canary_report.py` covering: schema match vs `contracts/canary-run-json.md`; byte-identical re-write on identical input modulo `started_at`/`finished_at`/`canary_run_id`; `failing_metrics` and `kernel_touches[].files` sorted.
- [x] T017 [US1] Add `src/auto_invest/canary/run.py` exposing `run_canary(options: CanaryOptions) -> CanaryRun`. Sequence: resolve revs → query baseline → emit `CANARY_ENTERED` → compute kernel-touch diff → if non-empty emit `CANARY_KERNEL_TOUCH_DETECTED` (US2 deeper integration; US1 emits an empty list path) → call `replay_window` → call `evaluate_metrics` → decide outcome → emit `CANARY_PASSED` / `CANARY_FAILED` → call `write_report` → return.
- [x] T018 [US1] Add `src/auto_invest/canary/cli.py` with Typer subcommands `run`, `shock`, `fuzz` matching `contracts/canary-cli.md`. Wire the exit codes (`0` pass, `1` fail, `2` data-incomplete, `3` internal, `4` usage). For US1 only `run` is fully wired; `shock` and `fuzz` raise `NotImplementedError` (filled in US2).
- [x] T019 [P] [US1] Add integration test `tests/integration/test_canary_end_to_end.py` invoking `cli.run` against the same fixture rev pair spec 008's `test_backtest_end_to_end.py` uses (or a minimal local rev pair). Assert: exit `0`, `CANARY_PASSED` row by `correlation_id`, all 5 `MetricResult.inside_band == true`, every FR-C07-required file under `data/canary/<run_id>/` exists.

**Checkpoint**: MVP complete. `canary run` works end-to-end for the happy path. Phase 4 + 5 can now proceed (and may be parallelised).

---

## Phase 4: User Story 2 — Regression caught by audit-integrity check + synthetic shock + property fuzz (Priority: P1)

**Goal**: Extend the canary harness so adversarial signals (synthetic-shock replay, property-based fuzz, audit-integrity baseline-mean check) participate in pass/fail. Without US2 the canary is essentially a long backtest comparison — US2 is what makes it "hardened".

**Independent Test**: inject a synthetic regression that drops 1/1000 fills (per spec.md US2 independent test). Verify `audit_integrity_failures > 0` → `CANARY_FAILED` with `failing_metrics: ["audit_integrity_failures"]`. Separately, monkey-patch `per_trade_cap_gate` with a deliberate off-by-one (`>=` → `>`) and assert fuzz catches it within 10k iterations (SC-C02).

- [x] T020 [US2] Add `src/auto_invest/canary/shock.py` exposing `run_synthetic_shock_battery(*, candidate_rev, baseline_rev, history_dir, audit_conn, out_dir) -> list[ShockResult]`. Loops over `auto_invest.backtest.synthetic_shocks.resolve_synthetic_shocks()`'s output; invokes `run_backtest(..., synthetic_shock=True, shock_date=d)` once per rev per date; collects per-date `BacktestRun`s. Writes each pair under `shock-replay/<YYYY-MM-DD>/{candidate,baseline}/backtest-run.json` and `audit_log.json`. (R-C3.)
- [x] T021 [P] [US2] Add `src/auto_invest/canary/fuzz.py` per `contracts/property-fuzz-protocol.md`. Public surface: `run_fuzz_pass(*, iterations: int, seed: int, out_dir: Path) -> list[FuzzCounterexample]`. Uses Hypothesis programmatic invocation (NOT pytest), captures ALL failing examples (does not short-circuit on first; R-C4), persists `seeds.txt` and `counterexamples.json`. Wrap with `InMemoryExampleDatabase` per R-C5 reproducibility contract.
- [x] T022 [P] [US2] Add unit test `tests/unit/test_canary_fuzz.py` covering: zero-counterexample case on stock `risk.gates`; monkey-patch off-by-one (`>=` → `>` in `per_trade_cap_gate`) catches within 10k iterations (SC-C02); shrinking produces a minimal counterexample; `counterexamples.json` schema matches `data-model.md` `FuzzCounterexample`.
- [x] T023 [US2] Audit-integrity baseline-mean computation — extend `src/auto_invest/canary/metrics.py` with `compute_audit_integrity_baseline_mean(audit_conn, baseline_window_end: date, lookback_days: int = 30) -> float`. Counts `DATA_QUALITY_ISSUE` rows in the 30 days prior to baseline window end; returns running mean per FR-C01 #3. Pass through to `evaluate_metrics`.
- [x] T024 [P] [US2] Add unit test extension to `tests/unit/test_canary_metrics.py::test_audit_integrity_baseline_mean_check` — seed an audit DB with N `DATA_QUALITY_ISSUE` rows in lookback window; assert candidate canary with `audit_integrity_failures = N + 1` fails (above baseline) and with `audit_integrity_failures = N - 1` passes.
- [x] T025 [US2] Wire `shock`, `fuzz`, and audit-integrity baseline into `run.py` orchestrator: replace the US1 stub kernel-touch path with a proper emit of `CANARY_KERNEL_TOUCH_DETECTED` (using `diff.intersect_kernel`); call `shock.run_synthetic_shock_battery` after `replay_window`; call `fuzz.run_fuzz_pass`. Failure precedence: any shock day with `risk_gate_violation_count > 0` → set `metrics.risk_gate_violations.observed_value` accordingly; any non-empty fuzz counterexample set → set `metrics.risk_gate_violations.observed_value` too AND record fuzz counterexamples in artefact tree. Decision is still all-or-nothing per FR-C06.
- [x] T026 [P] [US2] Add integration test `tests/integration/test_canary_kernel_touch.py`: construct a candidate rev whose diff against baseline touches `src/auto_invest/risk/gates.py`. Invoke `canary run`. Assert: `CANARY_KERNEL_TOUCH_DETECTED` row precedes the synthetic-shock `BACKTEST_STARTED` rows in audit time; the 5-metric battery STILL ran; final outcome reflects metric results, not the kernel-touch verdict (R-C8).
- [x] T027 [P] [US2] Add integration test `tests/integration/test_canary_audit_integrity_drop.py` — fixture: candidate that drops every 1000th fill (silent regression). Assert canary fails on `audit_integrity_failures` only (other 4 metrics pass).
- [x] T028 [P] [US2] Wire `canary shock` and `canary fuzz` subcommands in `cli.py` to call `shock.run_synthetic_shock_battery` and `fuzz.run_fuzz_pass` respectively. Update `--help` text to match `contracts/canary-cli.md`.

**Checkpoint**: Adversarial battery active. Spec 007's safety claims (SC-C01, SC-C02, US2 acceptance) are now testable end-to-end.

---

## Phase 5: User Story 3 — Operator can audit any canary decision retroactively (Priority: P2)

**Goal**: Reproducibility + forensic completeness. The same `(candidate_rev, baseline_rev, seed, window_start_date)` MUST produce byte-identical artefacts (SC-C04). The artefact tree MUST contain every signal needed to reconstruct a pass/fail decision without re-running the canary.

**Independent Test**: run a canary twice against identical inputs; diff the two `data/canary/<run_id_a>/` and `data/canary/<run_id_b>/` trees; assert byte-identicality after stripping `canary_run_id`, `started_at`, `finished_at`.

- [x] T029 [US3] Add `SeedBundle` capture in `run.py`: at canary start, allocate `hypothesis_database_seed` from `--hypothesis-seed` (or derive from `canary_run_id`); record `synthetic_shock_dates` resolved from spec 008's loader; record `quarterly_opex_resolved_for`. Persist into `CanaryRun.seed_bundle` so it flows into `canary-run.json`.
- [x] T030 [P] [US3] Add integration test `tests/integration/test_canary_reproducibility.py` — invoke `canary run` twice with the same `--hypothesis-seed`. Read both `canary-run.json` files, strip the three modulo fields, assert byte-equality. Also assert `metrics.csv` byte-equality (no `started_at` in there) and `property-fuzz/seeds.txt` byte-equality.
- [x] T031 [P] [US3] Add integration test `tests/integration/test_canary_no_network.py` — install a socket-level guard (monkey-patch `socket.socket.connect` to raise) before invoking `canary run`. Assert: full canary run completes without any `connect` attempt. Defends FR-C05 + the side-effect contract in `canary-cli.md`.
- [x] T032 [US3] Polish: `python -m auto_invest.canary --help` returns the contracts/canary-cli.md surface verbatim (or close); `canary run --dry-run` prints resolved revs + planned out_dir without emitting `CANARY_ENTERED` or writing artefacts.
- [x] T033 [P] [US3] Update `src/auto_invest/canary/__init__.py` to export the public surface: `run_canary`, `CanaryRun`, `CanaryMetrics`, `MetricResult`, `FuzzCounterexample`, `CanaryBandsConfigError`, `load_bands`. This is the import surface spec 005 (future tuner) and spec 006 (future deploy runner) will consume.

**Checkpoint**: Spec 007 v1 feature-complete. Phase 6 is polish.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: README, lint, dataset-incomplete handling, quickstart smoke test.

- [x] T034 [P] Add `data-incomplete` (exit 2) path in `run.py`: catch spec 008's `dataset_version not found` / `missing_history_for_date` exceptions and exit cleanly with code 2 + helpful message naming the missing dates and the `ingest-history` remediation command (per quickstart.md "Common failure modes").
- [x] T035 [P] Add `tests/unit/test_canary_cli_exit_codes.py` covering each exit code path (0, 1, 2, 3, 4) deterministically via mocked dependencies.
- [x] T036 [P] Run `uv run ruff check src tests` and `uv run ruff format --check src tests`; fix any violations. The codebase ships lint-clean per main-baseline; spec 007 must preserve that.
- [x] T037 [P] Add a `docs/`-style note (inline at the top of `src/auto_invest/canary/__init__.py` or a brief README under the canary package) explaining: purpose, entrypoint, link back to `specs/007-canary-hardening/quickstart.md`. Match spec 008's pattern.
- [x] T038 Quickstart smoke — manually walk through `specs/007-canary-hardening/quickstart.md` in sequence on a fresh checkout; fix any drift between the doc and reality (e.g., command names, output paths, exit-code descriptions).
- [x] T039 [P] Final test sweep: `uv run pytest` MUST pass clean. Spec 008's existing 494 tests MUST remain green (regression check). The new canary tests should add roughly 25-35 tests bringing the total to ~520-530.
- [x] T040 Update HANDOFF.md on `main` (in a follow-up PR after this one merges) to reflect spec 007 SHIPPED status + revise the "Spec 007 — stub. Blocked on spec 008." line. This task is OUT OF SCOPE for the spec 007 PR itself (it's the post-merge follow-up).

**Checkpoint**: Lint clean, tests green, docs aligned. Mark PR ready for review.

---

## Dependency graph

```
Phase 1 (T001-T004)
   ↓
Phase 2 (T005-T011)  ← K4 touch + foundations
   ↓
   ├─► Phase 3 US1 (T012-T019)  ← MVP: replay + 5-metric + CLI + report
   │      ↓
   │      └─► Phase 4 US2 (T020-T028)  ← shock + fuzz + audit-integrity + kernel-touch wire-up
   │             ↓
   │             └─► Phase 5 US3 (T029-T033)  ← reproducibility + no-network + dry-run
   │                    ↓
   └────────────────────► Phase 6 polish (T034-T039)
                            ↓
                          T040 (post-merge follow-up to HANDOFF.md)
```

US1 is the MVP. US2 extends to "hardened" by adding adversarial signals. US3 closes the forensic loop. Polish is cross-cutting and can run in parallel with US3.

## Parallel-execution opportunities

Within each phase, `[P]` markers indicate file-level independence. Parallel batches:

- **Phase 1**: T002 + T003 + T004 in parallel (different files).
- **Phase 2**: T006 + T007 + T008 + T009 + T011 in parallel after T005 / T010 land.
- **Phase 3 US1**: T013 + T014 + T016 + T019 in parallel after T012 / T015 / T017 / T018 land.
- **Phase 4 US2**: T021 + T022 + T024 + T026 + T027 + T028 in parallel after T020 / T023 / T025 land.
- **Phase 5 US3**: T030 + T031 + T033 in parallel after T029 lands; T032 can run any time after Phase 3.
- **Phase 6**: T034 + T035 + T036 + T037 + T039 all in parallel.

## Test count budget

Following spec 008's pattern (which shipped at 494 tests passing):

- Phase 2 foundational tests (T006, T009, T011): ~10-15 tests.
- US1 tests (T014, T016, T019): ~10-15 tests.
- US2 tests (T022, T024, T026, T027): ~15-20 tests.
- US3 tests (T030, T031): ~5 tests.
- Polish tests (T035): ~5-10 tests.

Total new tests: ~50-65. Total expected on main after merge: ~545-560.

## MVP scope reminder

The smallest deliverable that gates a production deploy is **US1 alone**: a `canary run` that evaluates 5 metrics over a 30-day window and emits `CANARY_PASSED` / `CANARY_FAILED`. US2 is what makes it "hardened" (without it the canary just compares two long backtests). US3 makes it forensically auditable. Ship in this priority order; if time pressure hits, US2 is the load-bearing follow-up and MUST land in the same PR (the spec's "hardened" promise depends on it).
