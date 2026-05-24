# Feature Specification (STUB): Autonomous Tuner

**Feature Branch**: `005-autonomous-tuner` (planned; not yet developed)
**Created**: 2026-05-06
**Last revised**: 2026-05-06 (constitution v2.0.0 alignment)
**Status**: Stub — 착수 가능 (운영자 지시 2026-05-24: 텔레메트리 30일 게이트 제거; spec 006·007·011 선행 조건 충족). 즉시 본 스펙으로 승격 가능.
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

운영자 지시(2026-05-24)로 **착수 게이트인 "텔레메트리 30일 누적" 요건은 제거**됐다. 나머지 두 선행 조건(spec 007·006 출시)은 이미 충족됐으므로 **즉시 본 스펙으로 승격·구현 착수 가능**하다(`/speckit-specify`→`/speckit-plan`→`/speckit-tasks`).

1. ~~≥ 30 calendar days of telemetry data~~ — **제거됨**(운영자 지시). spec 011(라이브 성과 측정)이 측정 신호 면을 이미 제공하므로 튜너 구현은 데이터 누적을 기다리지 않는다. 단, **런타임에 튜너가 실제로 임계값·룰을 자동 조정하는 행동은 헌법 원칙 X(측정 기반 — 충분한 증거 없이는 튜닝 금지)에 계속 종속**된다. 즉 "코드를 언제 쓰기 시작하는가"(이제 즉시)와 "튜너가 thin 데이터로 행동해도 되는가"(아니오, 원칙 X)는 별개다.
2. Spec 007 (hardened canary) has shipped — **충족**. 자율 머지는 그 합격 기준(≥30 거래일 캐너리 윈도 등)을 통과해야만 한다(IX.B-2, 안전 경계 불변).
3. Spec 006 (deploy automation) has shipped with the kernel-touch guard verified by integration test — **충족**.

**안전 경계(불변)**: 30일 게이트 제거는 착수 시점만 앞당긴다. 자율 튜너의 머지는 여전히 spec 007 하드닝 캐너리가 유일한 경로(IX.B-2)이고, Kernel 터치는 L4(인간 머지)로 강제되며(`kernel.toml` 가드), 실거래(`AUTO_INVEST_MODE=live`)는 운영자 토글 전용이다.

## Out of scope

- Multi-account or multi-strategy tuning. v1 of 005 tunes a single operator's single account.
- Cross-tuner coordination (e.g., two operators sharing a tuner). Out of scope.
- Adversarial robustness research (defending against an attacker who can submit poisoned telemetry). Documented as future work.
