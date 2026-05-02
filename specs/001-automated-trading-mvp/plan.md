# Implementation Plan: Automated US-Equity Trading MVP

**Branch**: `claude/review-codebase-status-xell9` (working branch; spec dir: `specs/001-automated-trading-mvp/`)
**Date**: 2026-05-02
**Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-automated-trading-mvp/spec.md`

## Summary

Build a Python 3.11 background worker, packaged as `auto_invest`, that loads operator-declared TOML rules at startup, evaluates time/price/indicator triggers during US regular hours, and routes resulting orders through a deny-by-default risk gate to KIS OpenAPI. Every order, fill, error, halt, and reconciliation result is persisted to an append-only SQLite audit log. After session close, the worker reconciles internal state against KIS and emits a daily report. **No LLM is invoked in v1** (per OD-2). The implementation favors a small surface of well-tested in-house adapters over heavy frameworks, so the safety-critical gates and the audit log can be inspected and reasoned about line by line.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**:
- `httpx` — HTTP client for KIS REST and WebSocket
- `tenacity` — retry with exponential backoff (constitution VII)
- `pandas` + `pandas-ta` — indicator computation (FR-016)
- `exchange_calendars` — US market session boundaries (FR-003)
- `pydantic` — config/rule validation (already transitive via anthropic; v2)
- `python-dotenv` — secret loading (constitution V)
- `apscheduler` — schedule reconciliation and report jobs
- `tomllib` (stdlib) — config parsing
- `sqlite3` (stdlib) — append-only audit log + price bars + positions

**Storage**: SQLite single-file database at `data/auto_invest.db` (gitignored), WAL mode, INSERT-only tables for audit log.
**Testing**: `pytest` for unit + integration; `pytest-asyncio` for async; recorded HTTPS fixtures (no live KIS calls in CI).
**Target Platform**: Linux long-running process (Python 3.11). Operator runs locally or on a small VPS.
**Project Type**: single-package CLI/worker.
**Performance Goals**:
- Trigger-evaluation latency p95 < 1 s per active rule per cycle.
- Order submission to broker p95 < 2 s under normal API health.
- Daily report generation < 30 s after session close (well within SC-006's 5-minute budget).
**Constraints**:
- Respect KIS REST rate limits (≈20 req/s per app key) and WebSocket subscription caps (per-account limit on simultaneous symbol streams).
- Worker MUST survive transient network failures without losing audit log integrity.
- Append-only invariant: no row in audit tables is ever updated or deleted in normal operation.
**Scale/Scope (v1)**: ≤ 50 whitelisted symbols, ≤ 20 active rules, single account, single operator. Designed to grow to ~200 symbols without architectural change.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan satisfies it | Status |
|---|-----------|---------------------------|--------|
| I | Position Sizing & Exposure Limits | `risk/gates.py` enforces three ex-ante checks before any order is dispatched: per-trade ≤ 5% of capital, per-symbol ≤ 20%, global ≤ 80%. Caps live in config; gate module fails closed. Default values declared in this plan; operator can override per environment. | ✅ pass |
| II | Deny-by-Default (Whitelist) | `config/whitelist.py` loads symbol/account/order-type/session whitelists at startup. `risk/gates.py` rejects any operation outside the whitelist before broker contact. | ✅ pass |
| III | Claude at Defined Judgment Points Only | v1 declares zero judgment points (per OD-2). No LLM client is constructed. Vacuously satisfied. | ✅ pass |
| IV | Append-Only Audit Log + Daily Reconciliation | `persistence/audit.py` writes to INSERT-only SQLite tables with monotonic sequence ids. `reconciliation/runner.py` runs after each session close and halts new orders on mismatch. | ✅ pass |
| V | Secret Isolation | Secrets loaded via `python-dotenv` from `.env` (gitignored). `logging_config.py` installs a redaction filter that masks all values registered as secrets. Worker refuses to start if any required secret is missing (FR-011). | ✅ pass |
| VI | Backtest → Canary → Full Live | `StrategyStage` enum gates promotion. Canary capital share capped at 5% by default. `strategy/canary.py` autopauses a strategy whose live metrics fall below acceptance for the configured duration (FR-014). Backtest engine itself is out of scope (sibling spec); this feature consumes its results. | ✅ pass |
| VII | External API Robustness | `broker/client.py` wraps every KIS call with `tenacity` retry (exponential backoff, bounded), a per-host rate limiter, and a circuit breaker that disables the call site after sustained failures. Token refresh is automatic in `broker/auth.py`. | ✅ pass |
| VIII | Change Discipline | All work on dedicated branches; no automated deploy in v1; the worker is started manually by the operator. The "no deploys during market hours" rule is operator-enforced for v1. | ✅ pass |

**No constitution violations identified. Complexity Tracking section below is intentionally empty.**

## Project Structure

### Documentation (this feature)

```text
specs/001-automated-trading-mvp/
├── plan.md                     # This file (/speckit-plan output)
├── spec.md                     # Feature spec (already finalized)
├── research.md                 # Phase 0 output
├── data-model.md               # Phase 1 output
├── quickstart.md               # Phase 1 output
├── contracts/
│   ├── rules-config.md         # Operator-facing TOML schema
│   ├── cli.md                  # CLI command surface
│   └── daily-report.md         # Daily report shape
├── checklists/
│   └── requirements.md         # Spec quality checklist
└── tasks.md                    # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/auto_invest/
├── __init__.py
├── __main__.py                 # python -m auto_invest entrypoint -> cli.app
├── cli.py                      # operator CLI (run / halt / resume / report / status)
├── logging_config.py           # JSON logger + secret-redaction filter (constitution V)
├── config/
│   ├── __init__.py
│   ├── loader.py               # load + validate TOML, freeze, refuse on missing secrets (FR-011, FR-015)
│   ├── rules.py                # TradingRule, Trigger, Action pydantic models
│   ├── whitelist.py            # Whitelist model (FR-002)
│   └── caps.py                 # SizingCaps model (constitution I)
├── broker/                     # KIS adapter (in-house thin client)
│   ├── __init__.py
│   ├── auth.py                 # access-token mgmt + refresh (FR-008)
│   ├── client.py               # httpx wrapper: rate-limit + retry + circuit breaker
│   ├── overseas.py             # overseas-equity REST endpoints used in v1
│   └── models.py               # OrderRequest / OrderResult / Quote / PositionSnapshot
├── market_data/
│   ├── __init__.py
│   ├── feed.py                 # poll bars from KIS; emit PriceBar events
│   ├── store.py                # PriceBar SQLite persistence (FR-016)
│   └── quality.py              # gap / staleness detection (FR-017)
├── strategy/
│   ├── __init__.py
│   ├── triggers.py             # time / price-threshold / indicator trigger evaluators
│   ├── indicators.py           # pandas-ta facade with strict input validation
│   └── canary.py               # canary metric tracking + autopause (FR-014)
├── risk/
│   ├── __init__.py
│   └── gates.py                # whitelist + sizing + halt + stage-uniqueness gates (constitution I, II)
├── execution/
│   ├── __init__.py
│   └── order_router.py         # rule-fire -> gates -> broker submit -> audit
├── persistence/
│   ├── __init__.py
│   ├── db.py                   # connection, schema migrations
│   ├── audit.py                # INSERT-only audit log writer (constitution IV)
│   └── positions.py            # local position state
├── reconciliation/
│   ├── __init__.py
│   └── runner.py               # end-of-session reconcile + halt-on-mismatch (FR-007)
├── reports/
│   ├── __init__.py
│   └── daily.py                # daily report from audit log (FR-010)
└── worker/
    ├── __init__.py
    ├── loop.py                 # asyncio main loop, lifecycle
    ├── schedule.py             # exchange_calendars wrapper, session boundaries
    └── halt.py                 # halt-flag file detection (FR-013)

tests/
├── conftest.py
├── unit/
│   ├── test_caps.py
│   ├── test_whitelist.py
│   ├── test_rules_loader.py
│   ├── test_risk_gates.py
│   ├── test_triggers.py
│   ├── test_indicators.py
│   ├── test_audit.py
│   └── test_secret_masking.py
├── integration/
│   ├── test_broker_client.py        # uses recorded fixtures, no live calls
│   ├── test_reconciliation.py
│   ├── test_canary_autopause.py
│   └── test_worker_loop.py
└── fixtures/
    ├── kis_responses/                # JSON capture for client tests
    └── rules/                        # sample TOML rules

data/                                  # gitignored
└── auto_invest.db                     # runtime SQLite (created on first run)

.env.example                           # documents required secrets (KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO)
```

**Structure Decision**: Single-package layout under `src/auto_invest/` with one module per bounded context (config, broker, market_data, strategy, risk, execution, persistence, reconciliation, reports, worker). This matches the v1 scope (single operator, single account, single process) without inviting premature distribution. Each module has a tight import boundary so risk gates, audit logging, and broker calls can be reviewed and tested in isolation — directly supporting constitution principles I, II, IV, and VII.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations. Section intentionally empty.*

## Post-Design Constitution Re-Check

*Per `/speckit-plan` workflow: re-evaluate after Phase 1 design artifacts (data-model, contracts, quickstart) are produced.*

| # | Principle | Re-check after Phase 1 | Status |
|---|-----------|------------------------|--------|
| I | Position Sizing & Exposure Limits | `data-model.md` defines `SizingCaps` with explicit invariants and the four cap-enforcing gates in `risk/gates.py`. `contracts/rules-config.md` makes the cap validation rules part of the operator contract. | ✅ pass |
| II | Deny-by-Default (Whitelist) | Loader contract refuses any rule referencing a symbol/account/order-type/session not on the whitelist; gate code mirrors the same check before broker submission. | ✅ pass |
| III | Claude at Defined Judgment Points Only | Plan, data model, and contracts contain zero references to LLM clients or judgment points. Vacuously satisfied. | ✅ pass |
| IV | Append-Only Audit Log + Daily Reconciliation | `data-model.md` documents append-only invariants per table; `current_positions` is a derived cache provably reproducible from `fills`. Daily reconciliation entity persisted in `reconciliation_runs`. | ✅ pass |
| V | Secret Isolation | Quickstart and CLI contracts both route the operator through `.env`-based loading; logging research entry (R-8) defines the redaction filter that runs upstream of every handler. | ✅ pass |
| VI | Backtest → Canary → Full Live | `StrategyStage` enum modeled in data-model; `strategy_stage_history` records every transition; canary cap and autopause defaults declared in research R-11. | ✅ pass |
| VII | External API Robustness | `broker/client.py` design (research R-12) wraps every call with retry + rate limit + breaker; defaults declared. | ✅ pass |
| VIII | Change Discipline | Reload semantics (rules-config contract) explicitly require restart; CLI contract documents shutdown sequence; `db migrate` is a separate explicit step. | ✅ pass |

**No new violations introduced by Phase 1 design. Plan is ready for `/speckit-tasks`.**
