# Feature Specification (STUB): Autonomous Token-Efficiency Tuner

**Feature Branch**: `005-autonomous-tuner` (planned; not yet developed)
**Created**: 2026-05-06
**Status**: Stub — promoted only after 002 has ≥ 30 days of measurement data.
**Input**: User description: "Close the measure → analyze → act loop. Use 002's telemetry to detect KPI drift and either auto-apply L1 changes (cache TTL, model routing, .claude/settings.json knobs), or open PRs for L2/L3 changes (prompt edits, judgment-point additions, code edits). All changes pass through constitution VI's staged rollout."

## Three-layer authority model (recap from 002)

| Layer | Examples | Behavior |
|-------|----------|----------|
| L1 (auto-execute) | model routing table, cache TTL, `.claude/settings.json` perms, subagent thresholds | apply immediately outside market hours; queue inside market hours |
| L2 (auto + canary) | prompt template edits, context-compression rules | backtest → 5 % canary → full live |
| L3 (PR only) | new judgment points, constitution edits, trading code | tuner opens a PR, human merges |

Constitution VIII (no live deploys during market hours) constrains L1 to outside-hours auto-apply.

## Candidate detection rules (operator-tunable)

- **Cost drift**: rolling-7d `usd_per_decision_mean` exceeds Tier C → propose model downgrade for the offending decision_class.
- **Cache miss**: rolling-7d `cache_hit_rate < 0.40` → propose cache TTL extension or session-context hook update.
- **Latency degradation**: rolling-7d `latency_p95_ms > Tier C` → propose smaller model or context truncation.
- **Quality regression**: when 004 ships, judgment-point downstream effect (e.g., subsequent reject-rate) deviates beyond control limit → propose prompt rollback (L2).

## Functional Requirements (preview)

- **FR-A01**: Tuner runs once per US session close; idempotent.
- **FR-A02**: Every action is recorded in audit_log (`AUTO_TUNED` event type, append-only).
- **FR-A03**: Tuner refuses to act when within 30 min of US regular open or 30 min before close.
- **FR-A04**: All L2/L3 actions output a structured proposal (PR body) with: detection rule, observed metric, proposed change, rollback steps, expected metric change.
- **FR-A05**: Tuner MUST NOT modify the constitution itself; constitution edits are L3-PR-only and never auto-merged.

## Promotion criteria

1. 002 has 30+ days of data.
2. 004 has shipped at least one judgment point so there is something to tune.
3. Operator has approved the L1/L2/L3 split (any reclassification gets logged in this spec's amendment history).
