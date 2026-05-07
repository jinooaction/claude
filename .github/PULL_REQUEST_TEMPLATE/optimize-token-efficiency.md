# Token-Efficiency Spec Bundle (002 + 003) + 004/005 stubs

Closes the "world-class token efficiency, autonomous growth & execution"
direction discussed with the operator on 2026-05-06. Ships measurement
infrastructure now, stages the next two specs as stubs gated on real
data.

## Summary

- **Spec 002 — token telemetry & efficiency KPIs (shipped):** every
  Anthropic API call passes through a `TokenMeter` async context
  manager, lands in a new append-only `token_usage` SQLite table,
  also writes an `LLM_CALL` audit row, and feeds a tier-classified
  KPI snapshot (cache hit rate, tokens/decision, $/decision, p95
  latency). Operators get a `auto-invest efficiency --window Nd` JSON
  CLI plus a "Token Efficiency" section in the daily report.
- **Spec 003 — Claude Code session cache (shipped, validation
  pending):** repo-local `.claude/settings.json` (read-only Bash + uv
  allowlist, deny-by-default for destructive ops) plus a SessionStart
  hook that surfaces the long-lived constitution + active-spec
  context with a SHA-256 fingerprint so prompt caching can amortize
  it across `/speckit-*` invocations.
- **Spec 004 — LLM judgment points (stub):** three candidate decision
  points listed (`volatility_assessment`, `news_screen`,
  `daily_summary`). Promotion gated on 30 days of telemetry data.
- **Spec 005 — autonomous tuner (stub):** L1/L2/L3 authority model
  documented (auto-apply / canary-then-apply / PR-only). Promotion
  gated on 002 data + 004 ship.

## What this PR does NOT do

- Does NOT add any LLM judgment point (FR-005 still holds; the meter
  is dormant until 004 ships).
- Does NOT change risk gates, order routing, reconciliation, or
  audit-log semantics for orders/fills (only adds two new event
  types: `LLM_CALL`, `PRICE_TABLE_LOADED`).
- Does NOT modify the constitution. (Operator may want to consider
  amendment at 004 promotion time; not required here.)

## Constitution alignment

| Principle | Verdict | Notes |
|-----------|---------|-------|
| I — Position sizing | n/a | telemetry never places orders |
| II — Deny-by-default | ✅ | unknown model → cost_usd NULL + DATA_QUALITY_ISSUE, never silently $0 |
| III — Judgment points only | ✅ | this PR adds zero judgment points; meter is opt-in |
| IV — Append-only audit | ✅ | `token_usage` enforced by SQLite triggers; integrity check at startup |
| V — Secret isolation | ✅ | meter signature accepts no prompt/response text; only counts |
| VI — Staged rollout | n/a | observation only |
| VII — External API robustness | ✅ | meter never swallows exceptions; resilience belongs to wrapping call site |
| VIII — Change discipline | ✅ | new-feature commits on a dedicated branch |

## Test plan

- [x] `ruff check src tests` — clean
- [x] `uv run pytest` — **301 passed, 1 skipped** (256 pre-existing
      tests preserved; 45 new tests across prices/thresholds/store/
      meter/kpi/audit-extension/daily-report/efficiency-cli)
- [x] Smoke-test `auto-invest efficiency --window 7d` against an
      empty DB — returns valid JSON with `tier: "N/A"` per KPI
- [x] Smoke-test SessionStart hook
      (`.claude/hooks/session_context.py < /dev/null | jq`) — emits
      `additionalContext` plus a stable SHA-256 fingerprint
- [ ] **Operator validation in fresh Claude Code session**: confirm
      the SessionStart fingerprint shows up and prompt caching
      kicks in on the second `/speckit-*` invocation
- [ ] **Operator deploy** on host: `git pull && uv sync && uv run
      auto-invest db migrate` then restart the worker (off-hours per
      principle VIII)

## Files changed

- `specs/002-token-telemetry/{spec,plan,research,data-model,tasks}.md`
  + `contracts/{kpi-thresholds,price-table,efficiency-cli}.md`
- `specs/003-session-cache/spec.md`
- `specs/004-llm-judgment-points/spec.md` (stub)
- `specs/005-autonomous-tuner/spec.md` (stub)
- `src/auto_invest/telemetry/{__init__,meter,prices,kpi,store,thresholds}.py`
- `src/auto_invest/persistence/migrations/0002_token_usage.sql`
- `src/auto_invest/persistence/audit.py` (extends `EventType` +
  payload union with `LLM_CALL` and `PRICE_TABLE_LOADED`)
- `src/auto_invest/reports/daily.py` (Token Efficiency section)
- `src/auto_invest/cli.py` (new `efficiency` subcommand + startup
  integrity check inside `run`)
- `config/llm_prices.toml` + `config/llm_kpi_thresholds.toml`
- `.claude/settings.json` + `.claude/hooks/session_context.py`
- `tests/unit/test_telemetry_*.py`,
  `tests/unit/test_audit_llm_call.py`,
  `tests/unit/test_daily_report_efficiency.py`,
  `tests/integration/test_efficiency_cli.py`
- `README.md` (Active Specs + new CLI line)
- `HANDOFF-002-003.md` (branch handoff for the next session)

## Deferred (next-session work)

- **T503**: emit `PRICE_TABLE_LOADED` audit row from `cli.efficiency`
  and `cli.run` startup. Payload class exists; call site does not.
  Documented in `HANDOFF-002-003.md` item 5.
- **004 / 005 promotion**: see stubs.

## How to deploy (operator)

Off-hours only (constitution VIII):

```bash
git fetch origin
git checkout claude/optimize-token-efficiency-uYiKk
uv sync
uv run auto-invest db migrate          # applies migration 0002
# Stop the running worker, then:
uv run auto-invest run --capital <N>
```

Detailed runbook in `docs/runbooks/migration-0002.md`.

## Reviewer checklist

- [ ] `pytest` passes locally (301 / 1 skipped)
- [ ] `ruff check` clean
- [ ] `auto-invest db migrate --db data/auto_invest.db` applies 0002
      cleanly on a fresh DB
- [ ] Daily report renders the Token Efficiency section without an
      LLM call (expected: "(no LLM calls today)")
- [ ] No prompt or response text in any persisted column
      (`SELECT * FROM token_usage` after a smoke test against a fake
      Anthropic response)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
