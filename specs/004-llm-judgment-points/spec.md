# Feature Specification (STUB): LLM Judgment Points

**Feature Branch**: `004-llm-judgment-points` (planned; not yet developed)
**Created**: 2026-05-06
**Status**: Stub — 착수 가능 (운영자 지시 2026-05-24: 텔레메트리 30일 누적 대기 없이 즉시 착수 허용). 본 스펙으로 승격하려면 `/speckit-specify`→`/speckit-plan`→`/speckit-tasks`.
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

운영자 지시(2026-05-24)로 **착수 게이트인 "텔레메트리 30일 누적" 요건은 제거**됐다. 즉시 본 스펙으로 승격·구현을 시작할 수 있다. 다음은 이제 착수 전 차단 게이트가 아니라 **구현·런타임 중 충족해야 할 항목**이다(안전 경계는 그대로):

1. ~~≥ 30 calendar days of telemetry data~~ — **제거됨**. 토큰 텔레메트리(spec 002)는 병행하여 쌓이며, 비용 프로파일이 thin 한 초기에는 보수적 예산으로 시작한다. (구현 자체는 데이터 누적을 기다리지 않는다.)
2. 운영자가 결과 비용 프로파일을 검토하고 v2 예산을 수용한다 — 구현 중/후 검토 항목.
3. 첫 캐너리 판단 지점은 결정론적 폴백 경로를 가진다(LLM 호출 실패가 거래를 막지 않도록) — 구현 시 필수.

**안전 경계(불변)**: 헌법 III(판단 지점 계약 선언)·IV(감사 기록)·VI(판단 지점은 5% 자본 캐너리에서 ≥10 거래일)·VII(Anthropic 클라이언트 견고성)은 그대로 적용된다. 30일 게이트 제거는 "언제 코드를 쓰기 시작할 수 있는가"만 바꾸며, 런타임 안전 계약은 건드리지 않는다.
