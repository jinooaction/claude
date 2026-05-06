# Feature Specification: LLM Token Telemetry & Efficiency KPIs

**Feature Branch**: `002-token-telemetry` (developed on `claude/optimize-token-efficiency-uYiKk`)
**Created**: 2026-05-06
**Status**: Draft
**Input**: User description: "World-class token efficiency requires measurement first. Add audit-grade telemetry for every Anthropic API call (when v2 introduces judgment points) plus efficiency KPIs surfaced in the daily report. v1 currently makes zero LLM calls (FR-005), so this feature ships the meter, the storage, and the reporting — but no judgment points. It is a pre-requisite for 003-session-cache and 004-llm-judgment-points."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Operator can answer "how much did Claude cost me yesterday?" in <1 minute (Priority: P1)

The operator opens the morning daily report and finds a "Token Efficiency" section listing: total Claude calls, total input/output/cache-read/cache-write tokens, total USD cost, cache hit rate, p50/p95 latency, and a Tier classification (A/B/C) for each KPI. The operator can decide same-day whether token spend is on budget without grepping logs.

**Why this priority**: Without this, every later optimization (caching, model routing, prompt compression) is unverifiable. Measurement precedes optimization.

**Independent Test**: Synthesize 50 fake `LLM_CALL` audit rows across two days, run `auto-invest report --date YYYY-MM-DD`, and verify the rendered Markdown contains a "Token Efficiency" section whose totals match the synthesized data exactly and whose Tier letters reflect the configured thresholds.

**Acceptance Scenarios**:

1. **Given** zero LLM calls on the session date, **When** the daily report is generated, **Then** the Token Efficiency section renders "(no LLM calls today)" without errors.
2. **Given** N LLM calls with mixed cache_read fractions, **When** the report is generated, **Then** cache hit rate = (sum cache_read_tokens) / (sum cache_read_tokens + sum input_tokens), rounded to one decimal.
3. **Given** an LLM call with `input_tokens > tokens_per_decision_tier_C threshold`, **When** the report is generated, **Then** the per-decision tokens KPI is classified `C` and the offending decision_class is named in the report.
4. **Given** the Anthropic SDK raises an exception inside a metered call, **When** the meter exits, **Then** an `LLM_CALL` row is still written with `error_class` populated and `tokens_*` set to 0; the call's downstream effect is still recorded in the audit log.

---

### User Story 2 — Telemetry never touches the audit log's append-only invariant (Priority: P1)

Every metered LLM call lands as exactly one row in a new `token_usage` table and exactly one `LLM_CALL` audit-log row, both append-only. Mutating prior rows is forbidden.

**Why this priority**: Constitution IV is non-negotiable. Telemetry is worthless if it can be silently rewritten.

**Independent Test**: Attempt `UPDATE token_usage SET ... WHERE seq=1` and `DELETE FROM token_usage WHERE seq=1` on a populated database; both must abort with the append-only trigger error.

**Acceptance Scenarios**:

1. **Given** a populated `token_usage` table, **When** any code attempts UPDATE or DELETE, **Then** the SQLite trigger raises `token_usage is append-only` and the row is unchanged.
2. **Given** a metered call writes both a `token_usage` row and an `LLM_CALL` audit row, **When** the writer is interrupted between the two writes, **Then** the partial state is detectable (token_usage row exists with no matching audit row, or vice-versa) and a startup integrity check surfaces it as a `DATA_QUALITY_ISSUE`.
3. **Given** the Anthropic SDK is not installed (e.g., dependency removed), **When** `auto-invest run` starts with zero declared judgment points, **Then** the worker boots normally and the Token Efficiency section reports zero calls; no import-time crash.

---

### User Story 3 — `auto-invest efficiency` CLI provides ad-hoc analysis (Priority: P2)

The operator runs `auto-invest efficiency --window 7d` and gets a JSON snapshot of the rolling 7-day KPIs (total cost, cache hit rate, tokens-per-decision distribution per `decision_class`, Tier letter per KPI, and the 5 most expensive single calls). Output is machine-parseable so it can feed into 005-autonomous-tuner without parsing Markdown.

**Why this priority**: P1 covers the daily-report path. P2 lets the operator (and the future autonomous tuner) reason about trends across days without rebuilding the daily report.

**Independent Test**: Populate `token_usage` across a 14-day span, run `auto-invest efficiency --window 7d --as-of YYYY-MM-DD`, and verify the JSON output includes only rows whose `ts_utc` is within `[as-of - 7d, as-of)`.

**Acceptance Scenarios**:

1. **Given** zero rows in the window, **When** the command runs, **Then** it emits a well-formed JSON object with zeroed counters and `tier: "N/A"` per KPI; exit 0.
2. **Given** rows in the window, **When** the command runs, **Then** every KPI has its tier letter, current value, and the threshold table embedded so the consumer can reproduce the classification.

---

### Edge Cases

- A metered call exits via `KeyboardInterrupt` mid-flight — the meter MUST still write a `token_usage` row with `error_class="KeyboardInterrupt"` and `tokens_total=0`, and re-raise.
- The Anthropic SDK returns a usage block with new fields not yet known to the meter — the meter MUST persist what it understands and emit a `DATA_QUALITY_ISSUE` for the unknown keys without crashing.
- The clock jumps backwards (NTP correction) between `start_ts` and `end_ts` — the meter MUST clamp `latency_ms` to `max(0, end - start)` and continue.
- `decision_class` is None — the meter MUST persist the row with `decision_class=NULL` and the report aggregator MUST group these under `(unclassified)` rather than dropping them.
- Cost computation discovers a model name not in the price table — the meter MUST persist `cost_usd=NULL` (not 0) and audit a `DATA_QUALITY_ISSUE` so the operator can refresh the price table.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-T01**: System MUST instrument every Anthropic API call made by the worker through a single `TokenMeter` context manager; direct calls to the Anthropic SDK that bypass the meter are forbidden by code review and detected by an integration test.
- **FR-T02**: System MUST persist exactly one `token_usage` row per call with at minimum: `model`, `decision_class`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`, `latency_ms`, `error_class`, `correlation_id`, `ts_utc`.
- **FR-T03**: System MUST also write an `LLM_CALL` audit-log row per call carrying the same `correlation_id` so judgment-point lineage is reconstructable from the audit log alone.
- **FR-T04**: `token_usage` MUST be append-only, enforced by SQLite triggers.
- **FR-T05**: System MUST compute the following KPIs over a configurable window (default: session date for daily report; 7 days for efficiency CLI):
  - cache hit rate (cache_read_tokens / (cache_read_tokens + input_tokens))
  - tokens per decision (mean and p95)
  - USD per decision (mean)
  - p50 / p95 latency (ms)
  - call volume per `decision_class`
- **FR-T06**: System MUST classify each KPI into Tier A / B / C / N/A using the threshold table declared in `contracts/kpi-thresholds.md`. The threshold table is operator-editable but ships with conservative defaults.
- **FR-T07**: Daily report (FR-010) MUST include a "Token Efficiency" section rendering the KPIs and tier letters for the session date.
- **FR-T08**: System MUST ship a model-name → USD-per-token price table at `config/llm_prices.toml`, used to compute `cost_usd`. Unknown model names produce `cost_usd=NULL` plus a `DATA_QUALITY_ISSUE`.
- **FR-T09**: `auto-invest efficiency --window <duration> [--as-of YYYY-MM-DD]` CLI command MUST emit a JSON snapshot covering all KPIs over the window.
- **FR-T10**: System MUST refuse to start if the price table is missing or fails schema validation; this is a startup error mirroring FR-011.
- **FR-T11**: System MUST mask any prompt or response text that the meter receives at logging time; raw prompts MUST NOT appear in `token_usage.payload_json` or in any logger handler. Only token counts, model name, decision class, and error class are persisted.
- **FR-T12**: System MUST run an integrity check at startup that flags any `LLM_CALL` audit row with no matching `token_usage` row (and vice-versa) as a `DATA_QUALITY_ISSUE`.

### Key Entities

- **TokenUsageRow**: one persisted record per metered LLM call. Append-only.
- **DecisionClass**: an operator-declared label categorizing why the LLM was called (e.g., `volatility_assessment`, `news_screen`). Free-form string; future 004 spec will declare the canonical set.
- **KPI**: a named metric with a value and a Tier letter, computed over a window.
- **TierTable**: operator-editable threshold mapping (KPI → A/B/C bands). Default values declared in `contracts/kpi-thresholds.md`.
- **PriceTableEntry**: `model` → `usd_per_input_token` / `usd_per_output_token` / `usd_per_cache_read_token` / `usd_per_cache_write_token`. Loaded from `config/llm_prices.toml`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-T01**: Across any rolling 30-day window, 100% of Anthropic API calls made by the worker have a matching `token_usage` row (verified by the FR-T12 integrity check returning zero discrepancies).
- **SC-T02**: The Token Efficiency section of the daily report renders in <100 ms for a session containing up to 1,000 LLM calls (well within the 5-minute SC-006 budget).
- **SC-T03**: Across any rolling 30-day window, zero raw prompts or responses appear in any persisted artifact produced by the system (FR-T11).
- **SC-T04**: The `auto-invest efficiency --window 7d` JSON snapshot is byte-stable for the same input data (modulo the `as_of` timestamp), enabling reproducible diffs by 005-autonomous-tuner.
- **SC-T05**: Once 004 ships judgment points, the operator can re-classify any past LLM call by editing `decision_class` retroactively — **rejected** because of FR-T04 (append-only). Any classification correction lands as a new `token_usage` row with `decision_class_correction_for=<seq>` (a future-spec field) rather than mutating history.

## Assumptions

- v1 currently makes zero LLM calls (FR-005). This feature is a pre-requisite that ships the meter; 004 will declare the first judgment point and start populating data.
- Operator runs the worker on a single host; the meter is a single-process construct (no distributed tracing required in v1).
- The Anthropic SDK exposes a usage block on every successful response with at minimum `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` (verified against `anthropic>=0.97`). Future SDK versions may add fields; the meter persists known fields and audits unknown ones (per Edge Case).
- The price table is operator-maintained; we ship a default with current public prices for Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5 as of 2026-05-06.

## Out of Scope (this feature)

- **Judgment points themselves**: declaring when/where the worker invokes Claude is reserved for 004. This feature is instrumentation only.
- **Auto-tuning of cache TTL or model routing**: reserved for 005-autonomous-tuner.
- **Cross-session distributed tracing**: single-process only.
- **Prompt content storage**: explicitly forbidden by FR-T11.
- **Token forecasting / budgeting alerts**: a separate spec can build alerting on top of this data.

## Open Decisions

All resolved at draft time:

- **OD-T1 — Should prompt content be stored?** Resolved as **no** (FR-T11). Rationale: secret material may leak into prompts; storing only counts is safer and sufficient for KPI computation.
- **OD-T2 — Per-call vs batched persistence?** Resolved as **per-call**. Rationale: matches the audit-log-per-event invariant; volume (≤ tens of calls/day in v2) does not justify batching.
- **OD-T3 — Threshold-table location?** Resolved as **`config/llm_kpi_thresholds.toml`** alongside `config/rules.toml`. Rationale: operator-editable, version-controlled in the operator's environment.
