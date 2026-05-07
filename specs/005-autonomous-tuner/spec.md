# Feature Specification (STUB): Autonomous Tuner

**Feature Branch**: `005-autonomous-tuner` (planned; not yet developed)
**Created**: 2026-05-06
**Last revised**: 2026-05-06 (constitution v2.0.0 alignment)
**Status**: Stub — promoted after 002 has ≥ 30 days of telemetry data and 007 (hardened canary) has shipped.
**Input**: Operator description: "Close the measure → analyze → act loop. Detect KPI drift and apply changes autonomously within the boundary set by constitution principle IX (Self-Modification Boundary). Goal: zero operator merges except for Kernel changes."

## Tiered authority model (constitution v2.0.0)

| Layer | Examples | Behavior |
|-------|----------|----------|
| **L1 (auto-apply)** | Cache TTL, model routing, `.claude/settings.json` knobs, subagent thresholds, KPI threshold tweaks within their own band | Apply immediately outside market hours via spec 006 deploy automation. Skip the spec 007 hardened canary (low-risk, instantly reversible). |
| **L2 (auto-merge through canary)** | Prompt templates, context-compression rules, judgment-point parameter changes, dependency upgrades that touch non-Kernel modules | Spec 007 hardened canary (≥30 trading days, multi-metric acceptance, synthetic-shock replay, property fuzz). Auto-promote on pass; auto-rollback on fail. |
| **L3 (auto-merge through canary, broader scope)** | New judgment-point declarations, new non-Kernel SQLite tables, new spec scaffolding, new test categories | Same canary as L2 but with extended observation window (≥45 trading days) because behavioral surface is larger. Auto-promote on pass. |
| **L4 (human-merge required — Kernel)** | Any file in `.specify/memory/kernel.toml` (K1-K6 + K-meta): position sizing, whitelist, judgment-point contract, audit-log structure, secret handling, market-hours guard, the kernel manifest itself, this constitution | Tuner opens a PR and waits. Human review and merge are required. |

**Boundary enforcement**: spec 006's deploy guard reads `kernel.toml` before any deploy phase. A change set whose diff intersects the Kernel is forced to L4 regardless of how the tuner classified it (defense-in-depth against tuner mis-classification).

## Detection rules (operator-tunable, all L1)

- **Cost drift**: rolling-7d `usd_per_decision_mean` exceeds Tier C → swap model routing entry for the offending `decision_class`.
- **Cache miss**: rolling-7d `cache_hit_rate < 0.40` → extend cache TTL or update session-context hook seed.
- **Latency degradation**: rolling-7d `latency_p95_ms > Tier C` → smaller model or context truncation.
- **Threshold drift**: rolling-30d KPI distribution stable inside Tier B with no Tier C events → tighten thresholds toward Tier A (autonomous improvement).

## Detection rules requiring canary (L2/L3)

- **Quality regression**: judgment-point downstream effect (e.g., reject-rate of orders that followed a `news_screen` call) deviates from control limit → roll back prompt template (L2).
- **Decision-class evolution**: a decision_class accumulates >100 calls with consistent input shape → propose a new judgment-point sub-class with finer-grained prompt (L3).

## Functional Requirements (preview)

- **FR-A01**: Tuner runs once per US session close; idempotent.
- **FR-A02**: Every action is recorded in `audit_log` with one of: `AUTO_TUNED_L1`, `AUTO_TUNED_L2_CANARY_ENTERED`, `AUTO_TUNED_L2_CANARY_PASSED`, `AUTO_TUNED_L2_CANARY_FAILED`, `AUTO_TUNED_L4_PR_OPENED`. All append-only.
- **FR-A03**: Tuner refuses to act within 30 min of US regular open or 30 min before close (operational margin around the VIII.A market-hours rule).
- **FR-A04**: All L2/L3/L4 proposals carry: detection rule that fired, observed metric, proposed change diff, rollback steps, expected metric improvement, and the canary acceptance criteria reference.
- **FR-A05**: Tuner MUST consult `kernel.toml` before classifying any change. Files matching the manifest are forced to L4.
- **FR-A06**: Tuner MUST NOT modify `kernel.toml` itself (K-meta). Adding files to the Kernel is permitted (forward-compatible safety improvement) only via L4.
- **FR-A07**: Tuner emits a daily `auto-tuner-report` JSON sibling to the daily report listing: candidate changes detected, classifications, current canary cohort, latest L4 PRs awaiting review.

## Promotion criteria

This stub is promoted to a full spec only after:

1. ≥ 30 calendar days of telemetry data exists in `token_usage` from 003 (session-cache) usage or 004 (judgment points).
2. Spec 007 (hardened canary) has shipped — autonomous merge requires its acceptance criteria.
3. Spec 006 (deploy automation) has shipped with the kernel-touch guard verified by integration test.

## Out of scope

- Multi-account or multi-strategy tuning. v1 of 005 tunes a single operator's single account.
- Cross-tuner coordination (e.g., two operators sharing a tuner). Out of scope.
- Adversarial robustness research (defending against an attacker who can submit poisoned telemetry). Documented as future work.
