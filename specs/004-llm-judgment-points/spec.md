# Feature Specification (STUB): LLM Judgment Points

**Feature Branch**: `004-llm-judgment-points` (planned; not yet developed)
**Created**: 2026-05-06
**Status**: Stub — promoted to Draft only after 30 days of telemetry data exists.
**Input**: User description: "Introduce the first LLM-assisted decision points to auto-invest. v1 declared zero judgment points (FR-005). This feature lifts that restriction for an explicitly enumerated, narrow set of decisions; constitution III requires each judgment point to declare trigger condition, input contract, output schema, latency budget, cost budget."

## Summary

This feature is the first that actually invokes Claude inside the trading loop. It MUST land on top of:

- **002-token-telemetry**: every call instrumented; cost reportable.
- **003-session-cache**: operator-side savings for SDD workflow.

All judgment points declared here ride the canary stage (constitution VI) for ≥ 10 trading days before promotion.

## Candidate judgment points (to be narrowed during /speckit-clarify)

| Tag | Trigger condition | Input contract | Output schema | Latency budget | Cost budget |
|-----|-------------------|----------------|---------------|----------------|-------------|
| `volatility_assessment` | `realized_vol_5m > rule.threshold` for any whitelisted symbol | summary stats (no raw bars) | `{action: "hold"|"size_down"|"halt", confidence: 0..1, reason: str}` | p95 < 2 s | $0.01/call |
| `news_screen` | scheduled headlines matched a whitelisted ticker during pre-market | headline text + symbol | `{stance: "bull"|"bear"|"neutral", confidence: 0..1}` | p95 < 5 s | $0.02/call |
| `daily_summary` | end-of-session, once per operating day | aggregated counters from audit_log | `{narrative: str≤500, alerts: list[str]}` | p95 < 10 s | $0.05/call |

Each candidate is an explicit FR; the operator may drop any of them at clarify time.

## Constitution gates (non-negotiable)

- III: each judgment point ships its prompt-template, input contract, output schema, latency budget, cost budget.
- IV: every call recorded in token_usage + LLM_CALL audit row (002 already provides this).
- VI: every judgment point starts in canary stage at 5 % capital share.
- VII: anthropic client wrapped with retry / rate-limit / circuit-breaker mirroring `broker/client.py`.

## Out of Scope

- Multi-turn agentic loops; v2 calls are single-shot request/response.
- LLM-driven order placement; LLM output is advisory and consumed by deterministic gate logic.
- Custom fine-tunes; ride the published Claude models.

## Promotion criteria

This stub is promoted to a full spec only after:

1. ≥ 30 calendar days of telemetry data exists in `token_usage` from 003 (session-cache) usage.
2. Operator has reviewed the resulting cost profile and accepts the v2 budget.
3. The first canary judgment point has a fall-back deterministic path (so a failed LLM call does not block trading).
