# Tasks: LLM Token Telemetry & Efficiency KPIs

**Input**: Design documents from `specs/002-token-telemetry/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: Generated for every module under the constitution's "test gate" (`telemetry/meter`, `telemetry/store`, `telemetry/prices`, `telemetry/kpi`, `telemetry/tier`, audit-payload extension, efficiency CLI). Pure plumbing (Markdown rendering, ad-hoc CLI ergonomics) ships without dedicated tests.

**Organization**: Tasks are grouped by user story so each phase ends at an independently-demonstrable checkpoint.

---

## Phase 1: Setup

- [x] T100 Create `src/auto_invest/telemetry/__init__.py` and the `specs/002-token-telemetry/` directory layout.
- [x] T101 Add migration file `src/auto_invest/persistence/migrations/0002_token_usage.sql` (CREATE TABLE + indexes + append-only triggers, IF NOT EXISTS guards).
- [x] T102 Ship default `config/llm_prices.toml` per `contracts/price-table.md`.
- [x] T103 Ship default `config/llm_kpi_thresholds.toml` per `contracts/kpi-thresholds.md`.

**Checkpoint**: `auto-invest db migrate` applies migration 0002 cleanly on a fresh database; `pytest` and `ruff check` still pass with the existing 256 tests untouched.

---

## Phase 2: Foundational

### Audit-log extension (constitution IV)

- [x] T110 Extend `EventType` in `src/auto_invest/persistence/audit.py` with `LLM_CALL` and add `LlmCallPayload` (model, decision_class, tokens_total, cost_usd, latency_ms, error_class). Update `AnyPayload` union.
- [x] T111 Extend `EventType` with `PRICE_TABLE_LOADED` and add `PriceTableLoadedPayload` (sha256, path).
- [x] T112 Add `tests/unit/test_audit_llm_call.py` covering: payload validates, frozen, no extra fields, append writes a row whose `event_type='LLM_CALL'`.

### Price table + thresholds

- [x] T120 Implement `auto_invest.telemetry.prices` (`PriceTable` pydantic model, `load`, `compute_cost`).
- [x] T121 Add `tests/unit/test_telemetry_prices.py` covering: defaults load, unknown model returns `None`, all-zero tokens returns `Decimal("0")`, cache_read uses cache-read price not input price.
- [x] T122 Implement `auto_invest.telemetry.thresholds` (`TierTable` pydantic model, `load`, `classify`).
- [x] T123 Add `tests/unit/test_telemetry_tier.py` covering: tier boundaries (≥/≤), N/A on empty, validation rejects mis-ordered bands.

### Storage + integrity

- [x] T130 Implement `auto_invest.telemetry.store` — `append_token_usage(conn, usage)`, `integrity_check(conn)`, plus a single `TokenUsage` dataclass.
- [x] T131 Add `tests/unit/test_telemetry_store.py` covering: append writes one row, append-only triggers reject UPDATE/DELETE, integrity_check returns mismatches.

**Checkpoint**: All foundational unit tests green (`pytest tests/unit/test_audit_llm_call.py tests/unit/test_telemetry_*.py`).

---

## Phase 3: User Story 1 — daily report Token Efficiency section

- [x] T200 Implement `auto_invest.telemetry.kpi` — `compute_snapshot(conn, window_start, window_end, prices, tiers, top_n=5)` returning `EfficiencySnapshot`.
- [x] T201 Add `tests/unit/test_telemetry_kpi.py` covering: empty window, mixed cache hit rates, p95 math, per-decision-class aggregation, top_n_calls ordering, deterministic output for same input.
- [x] T202 Implement `auto_invest.telemetry.meter.TokenMeter` async context manager — records start_ts on enter, persists token_usage + LLM_CALL audit row in `__aexit__` (success and exception paths).
- [x] T203 Add `tests/unit/test_telemetry_meter.py` covering: success path persists both rows with same correlation_id, exception path persists with error_class set, latency clamped ≥ 0, decision_class None preserved as NULL.
- [x] T204 Extend `auto_invest.reports.daily.build_report` to compute the snapshot for the session date and surface it on `DailyReport.efficiency`. Render a "Token Efficiency" section in `render_markdown`. Include section in `render_json`.
- [x] T205 Add `tests/unit/test_daily_report_efficiency.py` covering: zero-call session renders "(no LLM calls today)", populated session renders cache hit rate, per-decision class lines, tier letters.

**Checkpoint**: Daily report includes a populated Token Efficiency section when telemetry rows exist.

---

## Phase 4: User Story 2 — append-only invariant + integrity at startup

- [x] T300 Wire `integrity_check` into `cli.run` startup: after migrations, call it; any non-empty result writes a `DATA_QUALITY_ISSUE` audit row but does not block startup (mirroring market-data quality semantics).
- [x] T301 Add `tests/unit/test_telemetry_integrity.py` covering: orphan token_usage detected, orphan LLM_CALL detected, matched pair returns empty list.

**Checkpoint**: Startup integrity check runs on every `auto-invest run` invocation.

---

## Phase 5: User Story 3 — `auto-invest efficiency` CLI

- [x] T400 Implement `auto_invest.cli:efficiency` typer command per `contracts/efficiency-cli.md`. Parses `--window`, loads prices+thresholds, calls `compute_snapshot`, emits JSON.
- [x] T401 Add `tests/integration/test_efficiency_cli.py` covering: empty DB returns zero counters with N/A tiers, populated DB returns expected JSON, byte-stable output.

**Checkpoint**: `auto-invest efficiency --window 7d` runs against any populated DB.

---

## Phase 6: Polish

- [x] T500 Run `ruff check src tests` and `ruff format src tests` (format-only changes); fix any new findings.
- [x] T501 Run full `pytest`; verify the existing 256 tests still pass plus the new ones.
- [x] T502 Update `README.md` with a one-line pointer to `specs/002-token-telemetry/spec.md` and the `efficiency` CLI.
- [ ] T503 Wire `PRICE_TABLE_LOADED` audit emission from `cli.efficiency` and `cli.run` (one row per process). Test belongs in `tests/integration/test_efficiency_cli.py`. **Deferred to next session** — see `HANDOFF-002-003.md` item 5.

**Checkpoint**: CI-equivalent commands (`ruff check && pytest`) pass with zero new failures.
