# Phase 0 Research: LLM Token Telemetry & Efficiency KPIs

Each entry follows: **Decision** / **Rationale** / **Alternatives considered**.

---

## R-T1. Meter integration shape (decorator vs context manager vs SDK monkey-patch)

**Decision**: Async context manager `TokenMeter(decision_class, correlation_id, conn)` that yields a small `MeteredCall` object. The call site does:

```python
async with TokenMeter(decision_class="news_screen", correlation_id=cid, conn=conn) as call:
    response = await client.messages.create(...)
    call.record_response(response)
```

The meter records `start_ts` on enter, `end_ts` on exit, persists exactly one `token_usage` row in `__aexit__` (success path) or in the exception path (with `error_class` populated).

**Rationale**:
- Explicit at the call site (constitution III: Claude is invoked only at defined judgment points; the meter being explicit reinforces the discipline).
- Exception-safe by construction: `__aexit__` runs even on `KeyboardInterrupt`, satisfying the edge case in spec.md.
- No global SDK monkey-patch — preserves auditability of every call site (the integration test for FR-T01 can grep for direct SDK calls without the meter wrapping).

**Alternatives considered**:
- **Decorator `@metered`**: convenient but hides the meter from the call site, weakening the constitution III explicitness. Rejected.
- **SDK monkey-patch**: catches bypass attempts automatically but makes the meter implicit and fragile against SDK upgrades. Rejected.

---

## R-T2. Storage shape — separate table vs JSON in audit_log.payload_json

**Decision**: A dedicated `token_usage` table with typed columns, plus a parallel `LLM_CALL` row in `audit_log` carrying only the `correlation_id`. Both are append-only.

**Rationale**:
- KPI computation is hot-path-ish for the daily report; typed columns + indexes (model, decision_class, ts_utc) keep aggregation queries trivial.
- Audit log keeps lineage in one place (FR-T03) but does not duplicate the typed numeric columns.
- Mirrors the existing pattern: `orders` is typed, `audit_log` references it via `correlation_id`.

**Alternatives considered**:
- **JSON-only inside `audit_log.payload_json`**: simpler, but every KPI query becomes a JSON-extract scan. Rejected on SC-T02 grounds (100 ms budget for 1,000 rows).
- **Two append-only tables (one per call type)**: premature; v2 starts with a small set of decision classes that fit one table.

---

## R-T3. Cost computation source — runtime API vs static price table

**Decision**: Static TOML price table at `config/llm_prices.toml`, loaded at startup, validated by pydantic. Operator updates the table when Anthropic publishes price changes; the loader records a `PRICE_TABLE_LOADED` audit row with the file's SHA-256 so cost-history is reproducible.

**Rationale**:
- The Anthropic API does not expose authoritative pricing in the response. Hard-coding inside Python would couple price updates to code releases — unacceptable for a system that runs against live cost.
- TOML matches the existing config-loading idiom (R-7 from 001).
- Operator-editable + audited = correct ownership.

**Alternatives considered**:
- **Hard-coded constants in Python**: convenient, fragile against price changes. Rejected.
- **Live price API (none exists from Anthropic)**: not available.
- **Per-environment override via env var**: poor visibility; multiple sources of truth. Rejected.

---

## R-T4. Tier classification — fixed thresholds vs operator-editable

**Decision**: Operator-editable `config/llm_kpi_thresholds.toml`. Default values declared in `contracts/kpi-thresholds.md` reflect the conversation's "world-class Tier A" targets:

| KPI | Tier C ≥ | Tier B ≥ | Tier A ≥ |
|-----|----------|----------|----------|
| `cache_hit_rate` | 0.40 | 0.70 | 0.90 |
| `tokens_per_decision_p95` (lower is better) | ≤ 8000 | ≤ 3000 | ≤ 1500 |
| `usd_per_decision_mean` (lower is better) | ≤ 0.05 | ≤ 0.01 | ≤ 0.003 |
| `latency_p95_ms` (lower is better) | ≤ 5000 | ≤ 2000 | ≤ 800 |

**Rationale**:
- Different operating regimes (latency-sensitive intraday vs cost-sensitive overnight) want different targets. Operator-editable preserves that flexibility without code changes.
- Defaults match the proposal ("Tier A = world-class") so an operator who never edits the file still gets the canonical bar.
- Including the threshold table in the JSON output (FR-T09) makes the classifier self-describing for downstream tools.

**Alternatives considered**:
- **Hard-coded thresholds in Python**: opaque to the operator; every tweak is a code change. Rejected.
- **Per-decision-class thresholds**: adds expressiveness but inflates the threshold matrix. Defer to a future spec.

---

## Summary

All Technical-Context unknowns have a recorded decision. Phase 1 (data model + contracts) can proceed.
