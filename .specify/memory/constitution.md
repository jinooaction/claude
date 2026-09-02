<!--
Sync Impact Report (v15.2.0 -> 15.3.0)
==================
Version change: 15.2.0 -> 15.3.0 (MINOR: VIII.A extends terminal rollback orphan recovery to the narrow case where a later ordinary deploy has already moved production past the verified rollback baseline. A later exact registered-owner one-shot request may clear the stale request and QUIESCED interlock without another code mutation only when the old files and rollback chain still satisfy the v15.2.0 closed contract, production HEAD exactly equals the authorized current-main target, Git proves the target descends from the rollback baseline, and a later append-only normal live-deploy correlation proves exactly one start and completion for that target, zero failure or rollback, no unexpected deploy event, and a WORKER_STARTED row between start and completion. The worker and live timer must be active, the maintenance and broker-write locks must be exclusive, and a fresh read-only KIS smoke must prove open_unfilled=0. A new owner authorization and DEPLOY_EMERGENCY_RECOVERY_COMPLETED event are appended before removing the stale files. If normal deployment already completed and no stale state exists, the fixed helper is an audited no-mutation no-op. Missing ancestry, health, scheduler, audit, lock, broker, or identity proof remains interlocked. No arbitrary cleanup, manual order, service start, executable, checkout, force flag, capital, strategy, whitelist, risk, audit, or reconciliation bypass is added. this changes the safety perimeter.)
Migration impact:
  - The trusted owner-emergency workflow MUST invoke the fixed helper even when the ordinary deploy completed, so the helper can distinguish a clean no-op from a strictly provable post-rollback orphan recovery.
  - Post-rollback recovery after production advanced MUST bind the exact authorized current-main target to a later successful live deploy, Git ancestry from the rollback baseline, an in-window WORKER_STARTED row, active worker and live timer, both exclusive locks, and a fresh read-only KIS smoke with open_unfilled=0.
  - Cleanup-only recovery MUST append a new DEPLOY_EMERGENCY_AUTHORIZED row and DEPLOY_EMERGENCY_RECOVERY_COMPLETED terminal row, then remove only the stale request and maintenance interlock; it MUST NOT mutate code, dependencies, schemas, services, workers, positions, capital, strategy, or orders.
  - The deploy audit read path MUST recognize the recovery-completed event as a successful terminal recovery while continuing to reject every other terminal state.
Templates requiring updates:
  ⚠ spec 179 requirements, helper, workflow, typed audit payload, deploy-audit reader, counterexample tests, and production evidence require synchronized correction.
  ✅ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; they contain no rollback-orphan recovery detail.
  ⚠ .specify/memory/kernel.toml remains unchanged; the constitution, deployment workflow/helper, and audit contract are already K-meta/K6/K4.

Sync Impact Report (v15.1.0 -> 15.2.0)
==================
Version change: 15.1.0 -> 15.2.0 (MINOR: VIII.A adds fail-closed recovery for a terminally verified emergency rollback whose shell cleanup was interrupted after the unchanged deploy state machine had already emitted DEPLOY_ROLLED_BACK. A later exact registered-owner one-shot request may clear the orphan request and reuse the locked maintenance boundary only when both files are root-owned regular files with exact closed schemas and modes, their identities match, the ledger has exactly one authorization, one start, one failure, zero or one kernel-touch, one rollback, zero completion, no other deploy event, the latest event is rollback, and the production HEAD exactly equals the rollback baseline. The broker-write lock is acquired before clearing the orphan. The deploy config dry-run must read secrets from the same fixed production environment path already validated by the precondition instead of depending on systemd process injection. Missing, malformed, ambiguous, unlocked, non-terminal, completed, or repository-mismatched evidence remains interlocked. No arbitrary cleanup, environment export, executable, checkout, service start, order, actor, force flag, capital, strategy, whitelist, risk, audit, or reconciliation bypass is added. this changes the safety perimeter.)
Migration impact:
  - The deploy dry-run configuration check MUST receive the fixed RunnerConfig env_path and parse it through the existing redacting config loader; the root helper MUST NOT source, echo, or export the secret file.
  - An orphan request plus QUIESCED interlock MAY be recovered only after exclusive maintenance locking and exact file, audit-chain, terminal rollback, and production-HEAD proof; the broker-write lock MUST be acquired before the old request is removed.
  - Successful or rolled-back normal returns MUST execute cleanup while function-local evidence is still in scope, before disabling the EXIT trap.
  - Run 33673819722 proves exact-target bootstrap, KIS smoke 6/6, open_unfilled=0, DEPLOY_STARTED, DEPLOY_FAILED(dry_run), and DEPLOY_ROLLED_BACK; it placed no order and left the previous production commit restored.
Templates requiring updates:
  ✅ spec 179 requirements, helper, deploy config step, terminal rollback recovery tests, and production evidence require synchronized correction.
  ✅ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; they contain no emergency rollback-orphan detail.
  ⚠ .specify/memory/kernel.toml remains unchanged; the constitution, deployment runner, and helper are already K-meta/K6.

Sync Impact Report (v15.0.1 -> 15.1.0)
==================
Version change: 15.0.1 -> 15.1.0 (MINOR: VIII.A adds a fail-closed bootstrap and halted-interlock hand-off for the first deployment of the emergency protocol. After exact-main validation, root interlock acquisition, worker quiescence, and a read-only KIS smoke proving zero open orders, the fixed root helper may execute only the deploy runner from an isolated checkout whose HEAD is the exact authorized main SHA, while that runner continues to mutate only the audited production repository through the existing pull, sync, migrate, rollback, and >=90-second health state machine. This avoids calling an older installed deploy runner that cannot understand the new one-shot request. A prior HALTED maintenance interlock may be inherited only by another exact registered-owner one-shot request when the file is root-owned, regular, exclusively lockable, strict-schema valid, and its prior request has exactly one matching DEPLOY_EMERGENCY_AUTHORIZED row but zero DEPLOY_STARTED rows. Any prior started or ambiguous attempt remains halted for explicit forensic recovery. No arbitrary executable, checkout, service start, order, actor, force flag, capital, strategy, whitelist, risk, audit, or reconciliation bypass is added. this changes the safety perimeter.)
Migration impact:
  - The emergency helper MUST bootstrap the deploy state machine from an isolated exact-target checkout instead of asking the currently installed, possibly older service binary to understand the new authorization.
  - The bootstrap MUST run as the unprivileged application user, use fixed executable and production paths, and retain the existing deploy runner's audit, migration, rollback, supervisor, and health gates.
  - A HALTED interlock from a pre-start bootstrap failure MAY be inherited only after strict file, exclusive-lock, and audit-ledger proof; any prior DEPLOY_STARTED row fails closed.
  - Run 33671389870 proves KIS smoke 6/6 and open_unfilled=0 before the legacy-runner bootstrap failure; it created no order and no DEPLOY_STARTED row.
Templates requiring updates:
  ✅ spec 179 requirements, helper, actor validation, recovery tests, and production evidence require synchronized correction.
  ✅ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; they contain no emergency bootstrap detail.
  ⚠ .specify/memory/kernel.toml remains unchanged; the constitution and deployment helper are already K-meta/K6.

Sync Impact Report (v15.0.0 -> 15.0.1)
==================
Version change: 15.0.0 -> 15.0.1 (PATCH: VIII.A clarifies that emergency authority belongs to the real system owner, not necessarily the GitHub namespace owner. The only non-namespace owner currently registered is the exact GitHub actor `masonoh-kidsnote`, frozen in the default-branch workflow source and therefore changed only through the same reviewed Git/constitution path. The actor is never accepted from workflow input, repository variable, secret, environment override, or arbitrary collaborator role. All exact-main, one-shot, expiry, reason-digest, root interlock, zero-open-order, health, rollback, audit, and trading-safety requirements remain unchanged. This repairs the production identity mismatch exposed by run 33667656920 without widening emergency authority to writers or collaborators. this changes the safety perimeter.)
Migration impact:
  - The trusted workflow MUST accept only `github.repository_owner` or the exact constitution-registered system-owner actor `masonoh-kidsnote`.
  - The registered actor identity MUST be immutable workflow source on the protected default branch; it MUST NOT come from user input, variables, secrets, persistent environment, collaborator permission, or a generic role lookup.
  - Changing or adding a registered system owner requires another dedicated constitutional safety-perimeter amendment and full grade-4 validation.
  - Run 33667656920 remains a valid fail-closed rejection before SSH, server mutation, or broker access; it is evidence of the corrected identity defect, not a successful deploy.
Templates requiring updates:
  ✅ spec 179 requirements, workflow identity validation, and regression tests require synchronized correction.
  ✅ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; they contain no emergency actor identity.
  ⚠ .specify/memory/kernel.toml remains unchanged; the constitution and deployment workflow are already K-meta/K6.

Sync Impact Report (v14.0.0 -> 15.0.0)
==================
Version change: 14.0.0 -> 15.0.0 (MAJOR: VIII.A replaces the contradictory, undefined "declared emergency hotfix" sentence with a machine-enforced owner emergency live-deploy protocol. Ordinary live deploys remain prohibited during XNYS regular hours. A mid-session deploy is permitted only for one exact main commit under a repository-owner workflow approval that expires within 15 minutes, is consumed once, records a reason digest and workflow identity, acquires a root-owned broker-write interlock, proves zero open broker orders, preserves every I-VII and IX.B-2 production gate, emits append-only emergency and ordinary deploy audit events, and releases the interlock only after the unchanged >=90-second health gate succeeds or a verified rollback completes. Missing, stale, reused, mutable, mismatched, or unclassified authorization fails closed. No reusable force flag, arbitrary SSH command, manual order, capital increase, strategy promotion, whitelist change, risk-gate bypass, or price chasing is authorised. this changes the safety perimeter.)
Migration impact:
  - The normal deploy path continues to refuse every XNYS-regular-session deploy without a valid one-shot owner emergency request.
  - A new root-owned maintenance interlock MUST stop both automated live-order schedulers and the final broker-write boundary before production code mutation.
  - Emergency authorization MUST bind exact target SHA, repository-owner actor, workflow run ID, reason digest, issue time, expiry no later than 15 minutes, and single-use identity; it MUST NOT be expressible as a persistent environment switch or generic force option.
  - The authorization audit and maintenance interlock MUST exist before service or worker mutation. The previous live schedulers and worker are then stopped and verified inactive; only after that quiescence may read-only broker smoke prove zero open orders, and only after that proof may code change. Existing positions are preserved and are not liquidated by this protocol.
  - `DEPLOY_EMERGENCY_AUTHORIZED` precedes `DEPLOY_STARTED`; normal completed, failed, kernel-touch, rollback, secret, canary, and health evidence remains required.
  - Any failure keeps broker writes interlocked until the previous version is verified healthy or the system is explicitly halted with a surfaced reason.
  - This exception changes deploy timing only. Rung-1 capital remains 10%; order authorization, session claims, limit orders, whitelist, loss budget, reconciliation, and Backtest -> Canary -> Full boundaries are unchanged.
Templates requiring updates:
  ⚠ spec 179 SDD artifacts, deploy runner, audit payloads, fixed SSH boundary, production workflow, live-order interlocks, tests, and operator documentation require synchronized implementation before this exception may be used.
  ✅ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; their generic Constitution Check already requires plans to account for the amended principle.
  ⚠ .specify/memory/kernel.toml remains unchanged; the constitution and market-hours deploy guard are already K-meta/K6.

Sync Impact Report (v13.0.0 -> 14.0.0)
==================
Version change: 13.0.0 -> 14.0.0 (MAJOR: X.4 corrects the independent server timer's operational-revision test. A current main commit that only adds deployment-excluded, non-runtime paths MAY run on the already audited deployed ancestor, but only when the deployed commit is an ancestor of current origin/main and every intervening path is in the pre-existing frozen allowlist `*.md`, `specs/**`, `.verify/**`, or `.trigger/**`. Any source, deploy, workflow, configuration, automation, history-divergence, unreadable-diff, or unclassified change remains fail-closed. First-entry evidence is bound to current main; the deploy audit is bound to the actual deployed operational commit; both identities are recorded. This removes a document-only liveness veto without allowing ahead-of-deploy runtime code. All 10% rung-1, one-claim-per-XNYS-session, order, loss, whitelist, audit, secret, market-hours, and promotion boundaries are unchanged. this changes the safety perimeter.)
Migration impact:
  - Server fallback summaries move to schema 1.1 and record both `code_commit` (current main authority/evidence) and `deployed_code_commit` (the audited runtime), plus `operational_equivalent=true`.
  - The server scheduler and its internal `systemd-order` boundary MUST independently repeat the same ancestry and frozen-path test before the shared market-session claim.
  - Current-main changes outside the frozen deployment-excluded allowlist remain ineligible until an exact operational deploy and completed deploy audit exist.
  - Existing GitHub signed schedule semantics are not widened; the server route is brought into the same conservative operational-revision contract.
  - Rung 1 remains exactly 10%; K1/K2, limit orders, XNYS, kill switch, reconciliation, append-only audit, and all 20%+ gates are unchanged.
Templates requiring updates:
  ✅ .specify/memory/constitution.md and spec 176 SDD artifacts.
  ✅ server scheduler and internal order-boundary regression tests, deployment comments, and scheduled evidence schema assertions.
  ⚠ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; they contain no operational-revision semantics.
  ⚠ .specify/memory/kernel.toml unchanged; constitution is already K-meta.

Sync Impact Report (v12.0.0 -> 13.0.0)
==================
Version change: 12.0.0 -> 13.0.0 (MAJOR: X.4 corrects the whole-share fundability denominator used before first capital and first fill. The unchanged 66% funded-leg threshold now applies only to positive targets whose current target notional can express at least one whole share. At least one such target is mandatory. Every positive target, including a below-one-share target excluded only from that denominator, remains inside 100% quote coverage, 25% L1 capital-weight error, 15% per-leg error, cash, minimum-notional, whitelist, and exposure-cap checks. This prevents an intrinsically unorderable tiny leg from vetoing a safe non-empty portfolio while continuing to reject all-unexpressible, materially distorted, cap-breaching, or unfunded expressible portfolios. Rung 1 remains exactly 10%, and every order, loss, audit, secret, session, and promotion boundary is unchanged. this changes the safety perimeter.)
Migration impact:
  - Fundability evidence moves from schema 1.0 to 1.1 and MUST publish both all-positive-target and whole-share-expressible-target counts and funded ratios.
  - Schema 1.0 evidence cannot be inferred under the new semantics and remains first-entry-ineligible until a fresh exact-main preview is generated.
  - A positive target is whole-share-expressible only when its target notional at current canary capital and invested fraction is at least one positive current quote.
  - At least one expressible target and at least 66% funded expressible targets remain mandatory; all positive targets remain in quote and weight-error checks.
  - The 25% L1 error, 15% per-leg error, 10% capital, K1/K2, cash, minimum notional, kill switch, limit-order, XNYS, reconciliation, audit, and all 20%+ gates are unchanged.
Templates requiring updates:
  ✅ .specify/memory/constitution.md and spec 176 SDD artifacts.
  ✅ shared fundability producer/consumer, capital-entry and first-fill revalidation tests.
  ⚠ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; they contain no funded-leg denominator semantics.
  ⚠ .specify/memory/kernel.toml unchanged; constitution is already K-meta.

Sync Impact Report (v11.0.0 -> 12.0.0)
==================
Version change: 11.0.0 -> 12.0.0 (MAJOR: X.4 replaces the single-provider GitHub-schedule-only live-order wake-up rule with exactly two automated wake-up sources: the existing signed GitHub market-hours schedule and a root-owned production systemd fallback schedule. The fallback may run only after the primary GitHub opportunity, only from the fixed unit, only on exact deployed main, and only through the same sentinel, first-entry revalidation, XNYS, limit-order, whitelist, position-cap, kill-switch, circuit-breaker, reconciliation, append-only audit, and per-market-session atomic claim. Both sources therefore collapse to at most one broker-writing execution per XNYS session. Manual workflow_dispatch, repository_dispatch, arbitrary shell, and operator-invoked fallback orders remain forbidden. Capital stays at rung 1 and 10%; this changes scheduler availability, not strategy, capital, order type, loss budget, or promotion authority. this changes the safety perimeter.)
Migration impact:
  - Existing GitHub scheduled live orders remain the primary path and retain their short-lived signature and nonce contract.
  - A root-owned systemd timer may wake the same production order boundary only after the first GitHub opportunity and only when the shared market-session claim is still absent.
  - The fixed server path MUST reproduce first-entry revalidation before claiming, recheck exact deployed main and XNYS state, and preserve post-attempt fill sync, measurement, reconciliation, and append-only evidence even when a step fails.
  - The shared claim ledger records the wake-up source; any claim, including a failed or partial attempt after claiming, blocks every later source for that market session.
  - Manual workflow_dispatch remains authorization-only with zero real orders. No new remote order event, arbitrary SSH command, market-hours bypass, or price chasing is authorised.
Templates requiring updates:
  ✅ .specify/memory/constitution.md and spec 176 SDD artifacts.
  ✅ production systemd units/helper, shared session claim, GitHub duplicate evidence publication, and fixed read-only scheduled-status observation.
  ⚠ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; they contain no live wake-up source constants.
  ⚠ .specify/memory/kernel.toml unchanged; constitution is already K-meta.

Sync Impact Report (v10.1.0 -> 11.0.0)
==================
Version change: 10.1.0 -> 11.0.0 (MAJOR: X.4 adds a second, purpose-limited rung-1 entry route for operational live verification. A pre-existing exact deploy strategy with disjoint long development/holdout evidence, conservative cost and risk performance, exact fingerprint, hardened-canary PASS, execution-proxy parity, and current-NAV whole-share fundability MAY receive at most 10% of measured NAV solely to validate order, fill, reconciliation, and append-only audit plumbing. This route explicitly does not confirm alpha and can NEVER promote above rung 1 without independently earning the unchanged exploration and forward-alpha gates. Research diagnostics and capital-entry evidence must have separate typed artifacts. All 20%+ gates and all loss, order, whitelist, audit, secret, and market-hours controls remain unchanged. this changes the safety perimeter.)
Migration impact:
  - Existing rung 0 and rung 1 sentinels receive no automatic migration; new entry evidence and an explicit `entry_route` are required.
  - Operational entry is limited to the preregistered exact `globalfixed-ensemble-3-6-9-12` deployment candidate and exactly 10% or less of current measured NAV.
  - The consumer MUST recompute long holdout performance and diagnostics from raw monthly factors and reject missing, stale, non-main-lineage, fingerprint-mismatched, execution-mismatched, or unfundable evidence.
  - Operational entry always publishes `alpha_confirmed=false`, `max_rung=1`, and `promotion_above_rung1_allowed=false`.
  - Moving from operational rung 1 to rung 2 still requires the complete existing exploration contract: clean forward observations, PSR, Calmar, exact deployment identity, hardened canary, and calibrated route evidence.
  - Real orders continue only through the signed, nonce-protected, limit-order, regular-session workflow with pre-order revalidation, reconciliation, and append-only audit.
Templates requiring updates:
  ✅ .specify/memory/constitution.md and spec 176 SDD artifacts.
  ✅ operational evidence producer/consumer, capital ladder, first-entry revalidation, money-path reporting, and both production workflows.
  ⚠ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; they contain no rung-entry evidence constants.
  ⚠ .specify/memory/kernel.toml unchanged; constitution is already K-meta.

Sync Impact Report (v10.0.0 -> 10.1.0)
==================
Version change: 10.0.0 -> 10.1.0 (MINOR: X.4 replaces the overlapping low-power `DSR >= 0.95 AND PBO <= 0.20 AND raw-program Bonferroni` research-entry blockers with a preregistered `gate_version=3.1` calibrated-family contract. The consumer independently reconstructs the research-family ledger, requires selected holdout PSR >= 0.95 and family PBO <= 0.25, verifies but does not threshold-block on DSR, and bounds the program to 20 families under a calibrated 1% per-family null-admission ceiling. Raw-candidate Bonferroni and DSR >= 0.95 remain visible diagnostics. Current option evidence still fails PBO, data, parity, selection, and fundability. Existing 10% capital, every 20%+ gate, and all loss, order, whitelist, audit, secret, and market-hours controls remain unchanged. this changes the safety perimeter.)
Migration impact:
  - No sentinel, live capital, strategy configuration, whitelist, cap, loss budget, or order is migrated by this amendment.
  - Only `gate_version=3.1` can open the 10% research rung; v3.0, v2, and legacy evidence remain visible but ineligible.
  - The consumer MUST classify every raw audit row into a known preregistered research family and match the producer family count, row count, identity digest, and status counts.
  - The hard statistical gate is selected holdout PSR >= 0.95 plus consumer-recomputed family PBO <= 0.25. Fixed-seed calibration MUST show <= 1% null admission and >= 80% detection of planted annual Sharpe 0.60 for both 16- and 64-candidate families.
  - Program research spending MUST satisfy `research_family_count * 0.01 <= 0.20`; a 21st family requires a new preregistered calibration contract before results.
  - DSR and raw-candidate Bonferroni remain integrity-checked diagnostics and MUST NOT be silently removed from the evidence.
Templates requiring updates:
  ✅ .specify/memory/constitution.md and spec 167 SDD artifacts.
  ✅ shared factory validator, strategy-family ledger, calibration report, and production workflow assertions.
  ⚠ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; they contain no research-entry constants.
  ⚠ .specify/memory/kernel.toml unchanged; constitution is already K-meta.

Sync Impact Report (v9.0.0 -> 10.0.0)
==================
Version change: 9.0.0 -> 10.0.0 (MAJOR: X.4 replaces producer-trusting `family-complete-v2` research entry with consumer-recomputed `family-complete-v3`. The consumer independently recounts raw audit and family rows, identity uniqueness, selected-row identity, chronology and execution parity; charges the selected PSR for every unique program trial; recomputes DSR and PBO from current-family matrices and requires DSR >= 0.95 and PBO <= 0.20; and requires an exact current-NAV 10% dry-run allocation to survive whole-share, minimum-notional, cash, and exposure-cap constraints. Legacy and v2 evidence remain diagnostic-only. Existing 20%+ gates and all loss, order, whitelist, audit, secret, and market-hours controls remain unchanged. this changes the safety perimeter.)
Migration impact:
  - No sentinel, live capital, strategy configuration, whitelist, cap, or order is migrated by this amendment.
  - Only `gate_version=3.0` can open the 10% research rung; legacy and `gate_version=2.0` evidence remain visible but ineligible.
  - The global one-sided error probability is `min(1, (1 - selected_psr) * unique_program_trials)` and MUST be <= 0.05. Family DSR MUST be >= 0.95 and PBO MUST be <= 0.20.
  - A current read-only preview at exactly rung-1 capital MUST cover every positive target quote, fund at least 66% of positive target legs, keep L1 capital-weight error <= 25%, keep each leg error <= 15%, and reproduce its result from serialized planner inputs.
  - Missing, stale, contradictory, non-vintage, historically reused, execution-mismatched, or unfundable evidence remains at rung 0 and cannot place a first order.
Templates requiring updates:
  ✅ .specify/memory/constitution.md and spec 166 SDD artifacts.
  ✅ shared factory validator, exact dry-run fundability, capital ladder, first-entry revalidation, and both production workflows.
  ⚠ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; they contain no factory-version or fundability constant.
  ⚠ .specify/memory/kernel.toml unchanged; constitution is already K-meta.

Sync Impact Report (v8.0.0 -> 9.0.0)
==================
Version change: 8.0.0 -> 9.0.0 (MAJOR: X.4 replaces the stale exact-64 research-canary consumer constant with a versioned complete-family contract. `gate_version=2.0` requires at least 16 preregistered live-expressible trials, 100% family completion, all four cumulative-audit gates including unique strategy fingerprints, every producer-declared blocking gate, fresh evidence, hardened-canary PASS, and exact selected/configured/live strategy-fingerprint identity. Legacy evidence remains exact 64/64. The 10% research cap, all producer statistical thresholds, and every 20%+ gate remain unchanged. this changes the safety perimeter.)
Migration impact:
  - No sentinel, live capital, strategy configuration, or existing evidence is migrated by this amendment.
  - Current `gate_version=2.0` families can satisfy the consumer with 16 or more trials only when every preregistered trial and cumulative-audit invariant is complete.
  - Legacy evidence without `gate_version=2.0` remains subject to the previous exact 64/64 contract.
  - Current `NO_FACTORY_EDGE` evidence stays at rung 0; this amendment cannot turn an ineligible candidate into a winner.
Templates requiring updates:
  ✅ .specify/memory/constitution.md and spec 161 SDD artifacts.
  ✅ shared factory validator, zero-capital assignment, capital ladder, and first-entry revalidation consumers.
  ⚠ .specify/templates/{plan,spec,tasks}-template.md inspected and unchanged; they contain no family-size contract.
  ⚠ .specify/memory/kernel.toml unchanged; constitution is already K-meta.

Sync Impact Report (v7.0.0 -> 8.0.0)
==================
Version change: 7.0.0 -> 8.0.0 (MAJOR: X.4 adds a bounded 10% research-canary rung before the existing 20% exploration rung. Entry requires a complete 64-trial ledger, all preregistered DSR/PBO/time-segment/cost/benchmark gates, hardened-canary PASS, fresh evidence, and exact strategy-fingerprint identity. The existing 20% exploration and 25%/50%/100% gates remain unchanged and cannot be skipped. this changes the safety perimeter.)
Migration impact:
  - Rungs change from 0/20 exploration/25/50/100 to 0/10 research/20 exploration/25/50/100.
  - Existing rung 0 remains rung 0. No live capital is migrated by this amendment.
  - A factory winner receives no inherited capital and cannot exceed 10% without the existing exploration contract.
  - Missing, stale, partial, contradictory, or fingerprint-mismatched factory evidence remains disarmed.
Templates requiring updates:
  ✅ .specify/memory/constitution.md and spec 150 SDD artifacts.
  ✅ strategy factory, first-entry revalidation, capital ladder, and both live workflows.
  ⚠ .specify/memory/kernel.toml unchanged; constitution is already K-meta.

Sync Impact Report (v6.0.0 -> 7.0.0)
==================
Version change: 6.0.0 -> 7.0.0 (MAJOR: X.4 adds a bounded 20% exploration-canary rung before the original 25% rung. Entry requires an exact deployment match, disjoint >=120-month holdout with >=50bp annual cost, >=40 independent forward observations, PSR >=0.80, forward Calmar superiority, hardened-canary PASS, and fingerprint identity. Moving above 20% still requires the original EDGE_CONFIRMED threshold. Missing or contradictory evidence fails closed. this changes the safety perimeter.)
Migration impact:
  - Rungs change from 0/25/50/100 to 0/20 exploration/25/50/100.
  - `globalfixed` evidence must describe the exact deployed 3-6-9-12 month ensemble, not a family or single-window proxy.
  - Existing rung 0 remains rung 0; a legacy armed sentinel is treated as rung 1 and cannot skip EDGE_CONFIRMED before 25%.
  - X.5 reassignment still resets to rung 0 and re-earns every rung.
Templates requiring updates:
  ✅ .specify/memory/constitution.md and .specify/templates/plan-template.md.
  ✅ specs/140-heldout-exploration-canary and tested ladder/profit/workflow/config paths.
  ⚠ .specify/memory/kernel.toml unchanged; constitution is already K-meta.

Sync Impact Report (v5.0.0 -> 6.0.0)
==================
Version change: 5.0.0 -> 6.0.0  (MAJOR: principle X extended with item X.5 — autonomous STRATEGY REASSIGNMENT under a standing operator delegation. Item X.4 governs HOW MUCH capital is deployed (capital ladder); X.5 governs WHICH strategy is deployed: the autonomous forward tournament may reassign the live strategy to a challenger that clears ALL FIVE gates (edge-confirmed, multiplicity-corrected, apples-to-apples vs incumbent, hardened-canary PASS, ladder-reset-to-rung-0-after-reassignment) WITHOUT per-change operator approval. Any gate unmet => HOLD the incumbent (fail-safe). Reassignment changes WHICH strategy is exposed, not HOW MUCH — item 4's ladder + operator-owned 20% drawdown budget + immediate halt still bound the loss surface, which is therefore UNCHANGED from v5.0.0. All trading-safety invariants I-VII and VIII.A preserved unchanged. this changes the safety perimeter.)
Modified principles:
  X (Measurement-Driven Autonomous Growth) — item X.5 ADDED. Was: strategy selection for the live system was not explicitly delegated (the live config's strategy was set by operator/spec deploy config; the tournament computed a champion but reassignment was not autonomous). Now: a standing operator delegation (mason, 2026-06-16: "자율 전략 진화 폐회로 — 더 나은 전략을 시스템이 스스로 라이브로 교체. 완전 자율 + 5중 안전장치") authorises the system to reassign the live strategy to a challenger that clears the five gates, with the capital ladder reset to rung 0 so the new strategy re-earns capital from 25%. The spec 005 tuner still cannot reassign outside the gate.
Rationale:
  The operator (mason) on 2026-06-16 extended the 2026-06-11 capital delegation from "how much" to "which strategy": a world-class system should not merely size a fixed strategy but evolve the strategy itself toward the best measured performer, autonomously, while keeping the operator's risk function above it. The five gates are deliberately conservative — edge confirmation + multiplicity correction defeat the "lucky winner among many tracks" failure mode, apples-to-apples defeats window-shopping, the hardened canary is real-money validation before commitment, and the ladder reset means a freshly reassigned strategy carries ZERO inherited capital trust (it re-earns 25%->50%->100% under the unchanged 20% budget). Because reassignment changes only WHICH strategy is exposed and the ladder still governs HOW MUCH, the maximum loss surface is exactly item 4's budget — this amendment widens autonomy without widening the loss surface. this changes the safety perimeter (K-meta forensic marker: principle extension).
Templates requiring updates:
  ✅ .specify/memory/constitution.md (this file) — X.5 added; Version footer 5.0.0 -> 6.0.0.
  ✅ src/auto_invest/portfolio/auto_reassign.py + tests/unit/test_auto_reassign.py — the 5-gate reassignment decision logic (spec 055).
  ⧖ reassignment execution (live config swap + ladder rung-0 reset sentinel) + workflow wiring — follow-on commits in spec 055.
  ⚠ .specify/memory/kernel.toml — unchanged (no kernel file paths added/removed; X.5 is constitutional text, already K-meta).

Sync Impact Report (v4.0.0 -> 5.0.0)
==================
Version change: 4.0.0 -> 5.0.0  (MAJOR: principle X.4 backward-incompatibly redefined again. The bar "autonomous promotion to full live remains prohibited" is replaced by a STANDING OPERATOR DELEGATION to an evidence-gated CAPITAL LADDER (spec 050): autonomous, rung-by-rung promotion of deployed capital from 25% up to 100% of the real account NAV, each rung gated by measured live track record within an operator-owned drawdown budget (20%), with immediate automatic demotion/halt. All trading-safety invariants I-VII and VIII.A are preserved unchanged. this changes the safety perimeter.)
Modified principles:
  X.4 — was (v4.0.0) "live transition operator-decided; operator-instructed autonomous arming to live-canary ONLY; full-live (VI step 3) stays a separate explicit operator decision; never autonomous absent operator instruction." Redefined: capital sizing of the live system is governed by the spec 050 capital ladder under a STANDING operator delegation (mason, 2026-06-11: "1·2·3 모두 세계 최고 수준이 목표. 3번도 나는 자동과 자율에 맡길거야. 기준은 계좌 잔고와 포트폴리오"). Rungs: 0=0% (disarmed) -> 1=25% -> 2=50% -> 3=100% of measured real account NAV. Rung 0->1 requires forward-paper EDGE_CONFIRMED + strategy-fingerprint match (spec 049 conditions). Promotion n->n+1 requires ALL of: >=20 live NAV observations at the rung, >=27 calendar days at the rung, drawdown-since-rung-entry < budget/2. Demotion (>= budget/2) and halt (>= budget) are immediate and evidence-free downward. The drawdown budget (20%) is OPERATOR-OWNED: changing it is an operator decision. VI's staged-rollout structure is unchanged — the ladder IS VI's promotion path with the acceptance metrics predeclared in code and every rung change recorded (sentinel PR + sidecar + audit trail). The spec 005 tuner still cannot touch the ladder, the budget, or the sentinel.
Rationale:
  The operator (mason) explicitly delegated capital scaling on 2026-06-11 after a calibration discussion that surfaced (a) the structural ceiling of the current constraints, (b) the three physically non-delegable acts (bank deposits, brokerage agreements, container network policy), and (c) the LP/GP shape of the delegation: the operator sets ONE risk budget; the system manages everything beneath it; non-delegable invariants (kill switch, circuit breaker, caps mechanism, whitelist, append-only audit, secrets, market-hours guard, budget ownership) sit ABOVE the autonomous manager, exactly as a world-class fund's independent risk function sits above a PM. The previous regime (fixed $500 capital + $1,000 hard cap + operator approval per capital change) made the dominant variable of "actually making money" — capital — immovable regardless of system quality, while the evidence pipeline (forward verdict -> live canary track record) it would need to scale safely already exists and is tested. Down-fast/up-slow asymmetry, the operator-owned budget, and the unchanged I-VII/VIII.A invariants keep the worst-case bounded: the maximum new loss surface is the budget (20% of account NAV) before automatic halt, which is the loss surface the operator accepted in the delegation. this changes the safety perimeter (K-meta forensic marker: principle redefinition).
Templates requiring updates:
  ✅ .specify/memory/constitution.md (this file) — X.4 redefined; Version footer 4.0.0 -> 5.0.0.
  ✅ src/auto_invest/portfolio/capital_ladder.py + tests/unit/test_capital_ladder.py — the ladder decision logic (spec 050).
  ✅ .github/workflows/forward-edge-autoarm.yml — autoarm gate extended to the full ladder gate.
  ✅ .github/workflows/rebalance-live-canary.yml — $1,000 footgun guard replaced by ladder-authority guard (capital <= recorded account NAV; legacy manual sentinels keep the $1,000 guard).
  ✅ tests/unit/test_live_arming_sentinel.py — sentinel capital must carry ladder authority (formula match) or stay small.
  ⚠ .specify/memory/kernel.toml — unchanged (no kernel file paths added/removed; X.4 is constitutional text, already K-meta).

Sync Impact Report (v3.1.0 -> 4.0.0)
==================
Version change: 3.1.0 -> 4.0.0  (MAJOR: principle X.4 backward-incompatibly redefined. The absolute bar "the AUTO_INVEST_MODE=live transition ... is never flipped autonomously" is relaxed to permit an OPERATOR-INSTRUCTED autonomous transition to the LIVE-CANARY stage only, through a guarded, audited go-live channel. Full-live promotion stays operator-gated. All trading-safety invariants I-VII and VIII.A are preserved unchanged. this changes the safety perimeter.)
Modified principles:
  X.4 — was "Deploy ≠ live money; the AUTO_INVEST_MODE=live transition remains an explicit operator-gated decision and is never flipped autonomously." Redefined: the live transition is operator-DECIDED; under explicit operator instruction a session MAY arm it autonomously, but ONLY to the live-canary stage (constitution VI step 2 — conservative canary ruleset, small capital, full position caps), ONLY through the guarded go-live channel, and NEVER to full-live (VI step 3 stays a separate explicit operator decision). Absent explicit operator instruction the transition is still never autonomous (the spec 005 tuner cannot flip it).
Rationale:
  The operator (mason) instructed on 2026-05-30: "실거래 전환해. 내가 직접 관여하지 않고 자율 수행 해결해" and, when X.4's absolute bar was surfaced, "자동전환 가능하도록 헌법을 고쳐 ... 캐너리 — 소액부터" (= amend the constitution so the live transition can be autonomous; start with the small live canary). Under IX.D (Operator Autonomy Supremacy) the operator's explicit, informed instruction is the supreme decision criterion for procedural matters, and IX.D explicitly contemplates the session amending the constitution under operator instruction (recording a K-meta forensic event). This amendment is deliberately NARROW: it relaxes ONLY the manual-trigger requirement, ONLY for the operator-instructed case, ONLY to the bounded live-canary stage, and keeps every money-safety invariant (I position caps, II whitelist, IV audit, V secrets, VI full-live gate + canary-first, VIII.A market-hours) intact. The bounded loss surface the operator accepted (small canary capital, where the per-trade cap already rejects most blue-chip orders) is the maximum the amendment enables; autonomous full-live remains prohibited. this changes the safety perimeter (K-meta forensic marker: principle redefinition).
Templates requiring updates:
  ✅ .specify/memory/constitution.md (this file) — X.4 redefined; Version footer 3.1.0 -> 4.0.0.
  ✅ deploy/AUTO-DEPLOY.md — "이 파이프라인이 하지 않는 것" updated: the guarded go-live channel (go-live-canary.yml) is the operator-instructed autonomous live-canary path; deploy-on-merge still never flips the mode.
  ⚠ .specify/memory/kernel.toml — unchanged (no kernel file paths added/removed; X.4 is constitutional text, already K-meta).

Sync Impact Report (v3.0.0 -> 3.1.0)
==================
Version change: 3.0.0 -> 3.1.0  (MINOR: principle X added — Measurement-Driven Autonomous Growth. No principle removed or redefined; trading-safety invariants I-VII and VIII.A unchanged; spec 007 hardened canary remains the production-deploy gate.)
Added principles:
  X. Measurement-Driven Autonomous Growth (NEW). Autonomous self-modification targeting trading performance (spec 005 tuner) MUST be justified by live/paper measurement (spec 011); live/paper/canary/backtest performance MUST share one metric definition (spec 008 backtest/metrics.py); completed merged phases auto-deploy via the VIII.B-guarded pipeline (deploy/AUTO-DEPLOY.md); deploy != live money (AUTO_INVEST_MODE=live stays operator-gated). Adds a requirement (evidence before tuning) and a standing mode (continuous deploy to a dry-run worker) entirely INSIDE the existing safety perimeter.
Modified principles: none.
Templates requiring updates:
  ✅ .specify/memory/constitution.md (this file) — principle X added; Governance compliance line "I–IX" -> "I–X".
  ⚠ .specify/templates/plan-template.md — Constitution Check should cover principle X for performance-targeting / tuner / deploy specs (deferred; applied at next /speckit-plan touching those areas).
  ⚠ specs/005-autonomous-tuner/spec.md — tuner MUST cite spec 011 measurement as its input signal (deferred; spec 005 still a stub).
Rationale:
  The operator's vision is a world-class system that grows itself autonomously, driven by measured evidence rather than guesses. v3.0.0 enshrined operator-autonomy supremacy (IX.D) and the deploy guards (VIII.B), but nothing required the future tuner to act on MEASURED performance, nor named the standing "each merged phase auto-deploys" mode. Spec 011 (live performance eval, P2 risk-adjusted metrics) now provides the measurement; this principle ties it to spec 005's growth loop and to the deploy pipeline, without widening the loss surface. this changes the safety perimeter (K-meta forensic marker: principle addition).

Sync Impact Report (v2.0.0 -> 3.0.0)
==================
Version change: 2.0.0 -> 3.0.0  (MAJOR: operator's autonomy preference enshrined as supreme decision criterion; IX.B-1 and IX.B-4 repealed so autonomous merge is the default path including Kernel touches; IX.B-2 reclassified as deploy-stage gate not merge-stage gate; trading-safety invariants preserved via principles I-VII and VIII.A unchanged; spec 007 hardened canary remains the production-deploy gate that protects real money)
Modified principles:
  IX.A — Kernel reframed from "review-gated barrier" to "high-attention forensic-audit list". The seven groups (K1..K6 + K-meta) remain enumerated but a Kernel touch no longer blocks merge by itself.
  IX.B-1 (autonomous-merge eligibility, "Kernel-untouched") — REPEALED. Kernel touches are now permitted under the autonomous workflow when initiated by an operator-instructed session OR when the spec 007 hardened canary is satisfied. The deploy guard still EMITS a forensic audit row (DEPLOY_BLOCKED_KERNEL_TOUCH renamed in semantic to DEPLOY_KERNEL_TOUCHED — informational, not blocking).
  IX.B-2 — RECLASSIFIED. The hardened canary is now explicitly a PRODUCTION-DEPLOY gate, not a merge gate. Merges land via the autonomous-workflow policy in CLAUDE.md; live trading exposure to the new code is still gated by spec 007.
  IX.B-3 — preserved (VIII.A market-hours deploy guard still applies).
  IX.B-4 (no L4 escalation) — REPEALED. Spec 005's L4 classification now means "extra audit + forensic callout" not "human-merge path".
  IX.C — modifications now permitted under autonomous workflow; the manifest's role shifts from "fixed-point barrier" to "high-attention forensic list".
Added principles:
  IX.D — Operator Autonomy Supremacy (NEW, NON-NEGOTIABLE). The operator's stated autonomy preference is the supreme decision criterion. When any procedural rule in this constitution would block autonomous progression initiated by an operator-instructed session, the autonomous path wins. The exceptions are the trading-safety invariants in principles I-VII and VIII.A, which protect the operator's real money and remain non-negotiable regardless of autonomy direction.
Backward-incompatibility:
  - Code that read IX.B-1 as "Kernel touches halt the merge" MUST be rewritten to "Kernel touches emit DEPLOY_KERNEL_TOUCHED and continue".
  - Spec 005's L1/L2/L3/L4 tiered authority loses the "L4 → operator-merge" branch. L4 is now "extra audit + forensic callout", same merge path as L1-L3.
  - Spec 006's kernel_guard becomes a log-loud guard, not a halt guard. Its return type's `touched` boolean stays the same; consumers MUST change their interpretation from "abort" to "emit forensic event and continue".
  - Spec 007 stays semantically unchanged but is now framed as the production-deploy gate, not the merge gate.
Templates requiring updates:
  ✅ .specify/memory/constitution.md (this file)
  ⚠ .specify/memory/kernel.toml — descriptions updated to reflect "high-attention list, not barrier" semantics; file paths unchanged.
  ⚠ specs/005-autonomous-tuner/spec.md — L4 branch rewording (deferred; spec is still a stub).
  ⚠ specs/006-deploy-automation/spec.md — kernel_guard semantics from halt to log-loud (deferred until spec 006 implementation resumes).
  ⚠ specs/007-canary-hardening/spec.md — framing update from "merge gate" to "production-deploy gate" (deferred; spec is still a stub).
  ⚠ specs/008-backtest-engine/{spec,plan,research,data-model}.md — Constitutional Fit / one-time-K4-touch sections can be simplified; "one-time additive Kernel touch with operator approval at merge" is no longer a special event under v3.0.0 (deferred; spec 008 implementation in flight).
Rationale:
  The operator (mason) instructed on 2026-05-14: "내 목표는 자율 수행이라고. 헌법이 장애물이라면 그것도 수정해야지 당연히. 내 목표가 최상위 의사결정 기준이야" (= autonomy is the supreme decision criterion; the constitution is subordinate to that goal and should be amended where it conflicts). v2.0.0's IX.B-1 was carved to protect the operator from their own future autonomous tuner rewriting safety code, but in practice it concentrated operator attention on a handful of additive K4 touches (e.g., spec 002's migration 0002, spec 008's audit-event Union extension) that didn't reduce safety. The operator's concrete failure mode is loss of money via bad trading decisions, not loss of money via the autonomous tuner rewriting risk gates — because the autonomous tuner doesn't exist yet (spec 005 is a stub), and when it does, spec 007's hardened canary will catch the misbehaviour at the production-deploy boundary. So the meaningful protection lives at the deploy boundary, not at the merge boundary; v3.0.0 makes that explicit.
Trade-off acknowledged:
  Under v3.0.0, a misbehaving future autonomous tuner CAN merge a change that removes K1 (position caps). The change lands in `main`. It does NOT reach production unless it passes spec 007's hardened canary or unless an operator-instructed session deploys it. The operator accepts this trade-off because:
    1. The autonomous tuner doesn't exist yet (spec 005 is a stub).
    2. When it ships, spec 007 is its mandatory deploy gate.
    3. The operator wants zero procedural friction at the merge stage.
    4. Reversion is one PR away (main is always deployable; main with a regression is one PR away from being main without the regression).
Sync Impact Report (v1.1.0 -> 2.0.0)
==================
Version change: 1.1.0 -> 2.0.0  (MAJOR: kernel concept introduced; principle IX added; VIII.B-3 health window relaxed; VIII.B-5 redefined to permit autonomous merge outside the kernel)
Modified principles:
  VIII.B-3 — health-check minimum window 30 s -> 90 s. Material relaxation toward more conservative.
  VIII.B-5 — was "Operator-triggered, not autonomous". Replaced by reference to new principle IX. Backward-incompatible: code that read VIII.B-5 as forbidding autonomous deploys must now read it as deferring to IX's tiered model.
Added principles:
  IX. Self-Modification Boundary (NEW). Defines a Kernel (K1-K6 + K-meta) that cannot be modified by autonomous deploys; permits autonomous merge for everything outside the kernel subject to a hardened canary (spec 007). Rationale: closes the gap between operator's "autonomous execution & autonomous improvement" goal and the safety reality that a system able to rewrite its own safety rules has no safety guarantees.
Added sections:
  - Kernel manifest reference: `.specify/memory/kernel.toml` (machine-readable list of files protected by principle IX). Modifying this file is itself a kernel touch.
Templates requiring updates:
  ✅ .specify/memory/constitution.md (this file)
  ✅ .specify/memory/kernel.toml (new; machine-readable kernel manifest)
  ✅ specs/005-autonomous-tuner/spec.md (tiered authority extended with L4 = kernel)
  ✅ specs/006-deploy-automation/spec.md (deploy guard MUST consult kernel manifest)
  ✅ specs/007-canary-hardening/spec.md (new; defines the hardened-canary that gates autonomous merges)
Follow-up TODOs:
  - 007 implementation depends on a backtest engine (option D from main HANDOFF.md). Until 007 ships, autonomous merge stays disabled in production; the kernel guard still applies and the existing 10-day canary is the upper bound on autonomy.
  - Spec 001's plan.md Constitution Check still references VIII as a single block; left as-is (shipped under v1.0.0). New plans MUST cite VIII.A / VIII.B / IX explicitly.
  - Reconsider adding an explicit daily/cumulative loss-limit principle (carried over from v1.0.0).

Sync Impact Report (v1.0.0 -> 1.1.0)
==================
Version change: 1.0.0 -> 1.1.0  (MINOR: principle VIII materially expanded for deploy automation)
Modified principles:
  VIII. Change Discipline — split into 8.A (no market-hours deploys, unchanged in spirit) and 8.B (automated-deploy requirements: market-hours guard, audit events, health-check gate, rollback obligation). Spirit preserved; guidance materially expanded.
Added sections: none (expansion is inside principle VIII).
Removed sections: n/a
Templates requiring updates:
  ✅ .specify/memory/constitution.md  (this file)
  ✅ specs/006-deploy-automation/spec.md  (new feature; consumes the 8.B clauses)
  ⚠ specs/001-automated-trading-mvp/plan.md  — Constitution Check table still references VIII as a single block; left as-is because v1 was authored under v1.0.0 and is shipped. New plans MUST cite VIII.A / VIII.B explicitly.
Follow-up TODOs:
  - Reconsider adding an explicit daily/cumulative loss-limit principle (deliberately omitted; carried over from v1.0.0).
  - At /speckit-specify for 004 (LLM judgment points), declare per-judgment-point cost + latency budgets and confirm VIII.B audit events still cover an LLM-bearing deploy.

Sync Impact Report (v1.0.0 -> 1.0.0)
==================
Version change: (none) -> 1.0.0  (initial ratification)
Modified principles: n/a (initial draft)
Added sections:
  - Core Principles (8 principles)
  - Investment Domain Constraints
  - Development Workflow
  - Governance
Removed sections: n/a
Templates requiring updates:
  ✅ .specify/memory/constitution.md  (this file)
  ⚠ .specify/templates/plan-template.md   — needs a "Constitution Check" section that maps to principles I-VIII (to be added at first /speckit-plan run)
  ⚠ .specify/templates/spec-template.md   — needs investment-domain fields (asset universe, risk caps, judgment points) (to be added at first /speckit-specify run)
  ⚠ .specify/templates/tasks-template.md  — needs task categories: risk-check, reconciliation, judgment-contract, audit-log (to be added at first /speckit-tasks run)
Follow-up TODOs:
  - Reconsider adding an explicit daily/cumulative loss-limit principle (deliberately omitted in v1.0.0 at user request; non-standard for professional trading systems).
  - At /speckit-specify, declare concrete numeric values for: per-trade size cap, per-symbol exposure cap, global exposure cap, canary capital share.
-->

# auto-invest Constitution

## Core Principles

### I. Position Sizing & Exposure Limits (NON-NEGOTIABLE)

Every order MUST pass position-sizing checks before submission:

- **Per-trade cap**: a single order MUST NOT exceed a configured percentage of total capital.
- **Per-symbol cap**: total exposure to one symbol MUST NOT exceed a configured percentage of total capital.
- **Global exposure cap**: total deployed capital MUST NOT exceed a configured percentage, preserving a cash buffer.

Concrete values are declared in the spec, but the existence of all three caps is non-negotiable. Any code path that places an order without enforcing these caps is a bug.

**Rationale**: Disciplined position sizing is the single most important factor in long-term survival of any trading system. It bounds the worst-case impact of bugs, bad data, or wrong judgment calls before any other safeguard fires.

### II. Deny-by-Default (Whitelist)

The system MUST reject all trading operations unless they appear on an explicit allowlist:

- Tradeable symbols are maintained as a versioned whitelist; unknown tickers are auto-rejected.
- Order types (limit, market, stop, etc.) MUST be opt-in per environment.
- Trading sessions (regular hours, extended hours) MUST be opt-in.
- Account IDs MUST be opt-in; orders against any other account are rejected.

**Rationale**: Typos, runaway loops, and malformed LLM output are common failure modes. Whitelisting turns a class of catastrophic accidents into harmless rejections.

### III. Claude Is Invoked Only at Defined Judgment Points

LLM calls are restricted to pre-declared decision points described in the spec:

- Per-tick, per-quote, or per-bar LLM calls are forbidden.
- Each judgment point MUST declare: trigger condition, input contract, output schema, latency budget, cost budget.
- Every call MUST log: timestamp, inputs, prompt, response, decision taken, downstream effect.

**Rationale**: Without these constraints, LLM cost spirals and decision lineage becomes unauditable. Treating the LLM as a bounded oracle (rather than an always-on reasoner) keeps the system deterministic where it can be.

### IV. Append-Only Audit Log + Daily Reconciliation

- Every order, fill, cancellation, error, and judgment call MUST be persisted to an append-only log. Mutating prior records is forbidden.
- At least once per trading day, internal positions and cash MUST be reconciled against the broker's reported state.
- Any unresolved mismatch MUST automatically halt new order submission until manually cleared with a logged justification.

**Rationale**: Append-only history enables post-mortem analysis. Daily reconciliation catches data corruption, orphan orders, and partial-fill misaccounting — all routine failure modes of live trading systems.

### V. Secret Isolation

- API keys, account numbers, refresh tokens, and access tokens MUST NEVER be committed to the repository.
- Secrets are loaded from environment variables or a secret manager at runtime only.
- Logs, error traces, and outbound telemetry MUST mask sensitive values.

**Rationale**: A leaked KIS app key allows unauthorized trading on the user's real account. Treat secrets as tier-0 assets.

### VI. Staged Rollout: Backtest → Canary (Live, Small) → Full Live

New strategies and material changes (parameter shifts, model swaps, prompt edits) MUST progress through:

1. **Backtest**: passes predefined acceptance metrics on out-of-sample data.
2. **Canary**: live trading with capital capped at a configured small share (declared in spec) and run for a configured minimum duration.
3. **Full live**: promotion only after canary meets predeclared acceptance metrics.

Each promotion is an explicit decision recorded in the audit log. Material change to a previously-promoted strategy resets it to step 1.

**Rationale**: Backtests systematically overstate performance because they cannot model API failures, slippage, or partial fills. A bounded canary captures these without risking full capital.

### VII. External API Robustness

All calls to external services (KIS, market data vendors, Anthropic) MUST implement:

- Rate limiting that respects documented vendor limits.
- Retry with exponential backoff on transient errors, with a bounded retry count.
- Circuit breaker that disables the call site after sustained failures and re-enables only after a cooldown.
- Automated token refresh where applicable (e.g., KIS access tokens).

**Rationale**: External APIs fail. Without these protections a vendor outage cascades into invalid system state, missed cancels, and unbounded retries.

### VIII. Change Discipline

#### VIII.A — No Live Deploys During Market Hours

- Ordinary code changes affecting production trading MUST NOT be deployed during US regular trading hours (XNYS regular session).
- The GitHub repository owner or the exact constitution-registered system-owner actor `masonoh-kidsnote` MAY authorize one emergency live deploy during an open XNYS session only when ALL of the following hold. Registration is fixed in the protected default-branch workflow source; writer/collaborator status alone grants no authority. Adding or changing a registered actor requires a dedicated constitutional safety-perimeter amendment and full grade-4 validation.
  1. **One exact, one-shot request.** The trusted deployment workflow binds the request to the exact current `main` commit, the triggering actor verified as either `github.repository_owner` or the exact registered system-owner actor above, workflow run ID, non-empty reason digest, issued-at time, and an expiry no later than 15 minutes. The actor identity MUST NOT be supplied or overridden through workflow input, repository variable, secret, environment, collaborator permission, or generic role lookup. The request is consumed once. A persistent environment variable, generic `--force` flag, reusable token, arbitrary SSH command, or branch name is not authorization.
  2. **Broker writes are quiesced first.** Before any code, dependency, schema, service, or worker mutation, the authorization audit exists and a root-owned maintenance interlock blocks both authorised live schedulers and the final broker-write boundary. The previous live schedulers and worker MUST then be stopped and verified inactive. Only after that quiescence may a read-only broker smoke check pass and report zero open orders; only after that proof may code, dependencies, schema, or the replacement worker change. Existing positions are preserved; the emergency deploy MUST NOT liquidate, resize, or otherwise trade them. To bootstrap an emergency capability absent from the installed revision, the fixed root helper MAY then run only the existing deploy state machine from an isolated checkout whose HEAD exactly equals the authorized current-main SHA, as the unprivileged application user and against fixed production repository, database, configuration, environment, supervisor, and health-window paths. The target runner MUST still perform its own authorization, pull, sync, migration, rollback, audit, and health checks. An arbitrary executable, checkout, command, or alternate state machine is forbidden.
  3. **No other safety gate is bypassed.** Principles I–VII, the IX.B-2 production canary gate, exact target identity, clean source, migration safety, secrets isolation, audit integrity, rollback, and post-deploy health checks remain mandatory. Emergency timing is not order authorization and does not permit a manual order, capital increase, strategy promotion, whitelist expansion, relaxed loss limit, skipped reconciliation, or price chasing.
  4. **The exception is append-only and fail-closed.** `DEPLOY_EMERGENCY_AUTHORIZED` MUST be written before `DEPLOY_STARTED` and before production mutation, with the bounded authorization identity but no secret material. Missing, stale, reused, writable-by-untrusted-users, mismatched, ambiguous, or unverifiable evidence MUST refuse the deploy through the normal audited failure path.
  5. **Interlock release follows proof, not process exit.** The one-shot request is removed after the attempt. The maintenance interlock is released only after the unchanged health gate succeeds, or after the previous version is restored and independently verified healthy. If neither can be proved, broker writes remain halted with a surfaced reason. A later exact registered-owner one-shot request MAY inherit a prior `HALTED` interlock only when it proves that the interlock is a root-owned regular file with the exact closed schema and expected reason, acquires its exclusive file lock, and finds exactly one matching prior `DEPLOY_EMERGENCY_AUTHORIZED` audit row with zero `DEPLOY_STARTED` rows on that correlation ID. A later exact registered-owner one-shot request MAY also clear an orphan request paired with a `QUIESCED` interlock only when both are root-owned regular files with exact closed schemas and modes, their request, run, actor, and target identities match, the exclusive maintenance lock is held, the ledger proves exactly one authorization, one start, one failure, zero or one kernel-touch, one rollback, zero completion and no other deploy event, and the latest event is `DEPLOY_ROLLED_BACK`. If production HEAD still equals the rollback baseline, the broker-write lock MUST be acquired before the old request is removed and the existing emergency path may continue. If a later ordinary deploy has advanced production, cleanup-only recovery is permitted only when production HEAD exactly equals the newly authorized current-main target, Git proves that target descends from the rollback baseline, and a later correlation after the rollback proves exactly one live `DEPLOY_STARTED` and one live `DEPLOY_COMPLETED` for that target, zero `DEPLOY_FAILED` or `DEPLOY_ROLLED_BACK`, no unexpected deploy event, and a `WORKER_STARTED` row strictly between those two events. The worker and live timer MUST be active, both maintenance and broker-write locks MUST be held exclusively, and a fresh read-only broker smoke MUST prove zero open orders. The helper MUST then append a new `DEPLOY_EMERGENCY_AUTHORIZED` and terminal `DEPLOY_EMERGENCY_RECOVERY_COMPLETED` record before removing only the stale request and interlock; it MUST NOT mutate code, dependencies, schema, services, workers, positions, capital, strategy, or orders. When production already equals the exact target and neither stale file exists, the same fixed helper is a no-mutation no-op. Successful and rolled-back returns MUST run cleanup while their local evidence is still in scope. Any malformed, locked, ambiguous, non-terminal, ancestry-mismatched, unhealthy, inactive, broker-uncertain, audit-incomplete, repository-mismatched, or otherwise unverifiable prior attempt MUST remain interlocked.
- All changes go through Git with descriptive commit messages.
- Changes to this constitution MUST be a dedicated amendment commit with a version bump.

**Rationale**: Mid-session deploys can introduce undefined behavior into a running strategy, so waiting for the normal off-hours path remains the default. A broken production liveness path can also prevent a time-sensitive, already-approved repair from reaching the system. The bounded emergency protocol makes that exceptional trade-off explicit, stops broker writes before mutation, and leaves enough evidence to prove exactly who authorized which commit and whether production recovered.

#### VIII.B — Deploy Automation Requirements (added v1.1.0)

Operator-triggered automated deploys are explicitly permitted (and preferred over hand-typed deploys) when ALL of the following hold:

1. **Market-hours guard.** The automation MUST check the US market state via `exchange_calendars` (or equivalent) and refuse to proceed during regular hours unless every machine-verifiable requirement of VIII.A's one-shot registered-owner emergency protocol passes. The ordinary guard and the emergency validator MUST be in code, not in operator memory.
2. **Append-only audit events.** Every deploy attempt MUST emit:
   - `DEPLOY_EMERGENCY_AUTHORIZED` before `DEPLOY_STARTED` for an VIII.A emergency, recording the exact bounded authorization identity without secrets.
   - `DEPLOY_STARTED` before any code, dependency, or schema change.
   - `DEPLOY_COMPLETED` on success after the post-deploy health check passes.
   - `DEPLOY_FAILED` on any abort, with `phase` and `reason` populated.
   These are first-class entries in the existing `audit_log` (principle IV); no parallel deploy log is permitted.
3. **Health-check gate.** After restarting the worker, the automation MUST poll for evidence of liveness for at least 90 s (default; operator may configure a longer window per environment, never shorter) before declaring success: a fresh `WORKER_STARTED` audit row whose `ts_utc` is after `DEPLOY_STARTED.ts_utc`, no `ERROR` rows in the same window, and no `DATA_QUALITY_ISSUE` rows referencing telemetry mismatches. Rationale for 90 s: covers KIS auth refresh retry (~10 s), broker first-quote latency under load (~5 s), and at least two full asyncio loop ticks against a live market-data feed.
4. **Rollback obligation.** On any health-check failure or migration failure, the automation MUST emit `DEPLOY_FAILED` and either (a) restore the previous worker version and confirm it boots, or (b) leave the system halted with a clear surfaced reason. The automation MUST NOT silently leave the worker stopped. During an VIII.A emergency, the broker-write maintenance interlock MUST remain engaged until one of those two terminal states is proven.
5. **Tiered autonomy — see principle IX.** Whether a given deploy may be initiated autonomously (by spec 005's tuner) versus requires explicit human merge depends on whether the change touches the Kernel defined in principle IX. The market-hours guard, audit events, health-check gate, and rollback obligation (clauses 1–4) apply to ALL deploys, autonomous or human-initiated, equally.
6. **Secrets isolation preserved.** Deploy automation MUST NOT log, persist, or transmit any secret material; it inherits principle V.

**Rationale**: Manual deploys are the single most reliable way for principle VIII.A to be violated by accident. Automation that *enforces* the rule is therefore safer than the absence of automation. Treating deploys as audited operations puts them on the same forensic surface as orders and judgment calls (principle IV), so an unexpected change in worker behavior can be traced to a specific deploy event.

### IX. Self-Modification Boundary (NON-NEGOTIABLE, amended v3.0.0)

The system is permitted — and encouraged — to evolve its own code, configuration, prompts, KPI thresholds, dependencies, schemas, and principles, as long as the trading-safety invariants in principles I–VII and VIII.A are honoured at production-deploy time. The Kernel (defined below) is no longer a merge-time barrier under v3.0.0; it is now a **high-attention forensic list** that triggers loud audit on touch. The real defence against a misbehaving autonomous tuner is spec 007's **hardened canary as a production-deploy gate** (IX.B-2), not IX.B-1's old merge-time approval requirement.

#### IX.A — The Kernel (forensic-attention list)

The Kernel is the closed set of files listed in the machine-readable manifest at `.specify/memory/kernel.toml`. As of v3.0.0 the Kernel still comprises seven groups, each tied to one constitutional invariant — but a Kernel touch no longer halts merge by itself.

| Group | Invariant | Forensic-attention reason |
|-------|-----------|---------------------------|
| **K1** | Position sizing caps (principle I) | Modification expands the loss surface; emit `DEPLOY_KERNEL_TOUCHED` and require spec 007 canary before production deploy. |
| **K2** | Deny-by-default whitelist (principle II) | Modification expands the universe; same gate. |
| **K3** | LLM-only-at-judgment-points contract (principle III) | Modification uncaps LLM cost or moves call sites; same gate. |
| **K4** | Append-only audit log (principle IV) | Modification could erase forensic trail; same gate. |
| **K5** | Secret isolation (principle V) | Modification could leak KIS keys; same gate. |
| **K6** | Market-hours deploy guard and one-shot emergency validator (principle VIII.A) | Modification could permit an unauthorized mid-session deploy or weaken its interlock; same gate. |
| **K-meta** | The Kernel manifest itself + this constitution | Modification reshapes the safety surface; same gate AND the commit message MUST include the literal string "this changes the safety perimeter" so a forensic grep can find every such event. |

#### IX.B — Autonomous-merge eligibility (v3.0.0)

A change set MAY be merged autonomously by ANY of these paths:

1. **REPEALED** (was: "Kernel-untouched required for autonomous merge"). Kernel touches no longer block merge. The deploy guard (spec 006) MUST emit an informational `DEPLOY_KERNEL_TOUCHED` audit row when a Kernel touch lands; it MUST NOT abort the deploy on this signal alone.
2. **Hardened canary as production-deploy gate (spec 007).** Before any change set reaches the production worker, it MUST pass spec 007's hardened-canary acceptance criteria: multi-metric, ≥30 trading-day window for L2 / ≥45 for L3, synthetic-shock replay, property-based fuzz of risk math. This gate protects real money. Until spec 007 ships, the existing 10-day spec-001 canary is the operator-facing upper bound on production autonomy; merges still land freely, but a human (or future tuner) decides when a merge is deploy-eligible.
3. **VIII.A market-hours discipline.** Mid-session deploys remain forbidden whether the change set is Kernel-touching or not, except for the exact, one-shot, registered-owner emergency protocol defined in VIII.A. Kernel touch does not weaken or expand that protocol.
4. **REPEALED** (was: "L4 escalation → human-merge"). Spec 005's L4 classification now means "extra audit + forensic callout in the PR description"; the merge path is the same as L1-L3.
5. **Operator-instructed session merges** (autonomous-workflow policy in CLAUDE.md) are first-class. The session's reasoning trace + the PR description + the merge commit message form the forensic record. No second human in the loop is required.

#### IX.C — Kernel manifest discipline (v3.0.0)

- The manifest at `.specify/memory/kernel.toml` is the single source of truth for "what counts as Kernel". Code that asks "is this path Kernel?" MUST read the manifest; hard-coded paths are forbidden so a Kernel addition or removal is one TOML edit, not a code release.
- The manifest is itself in K-meta. Modifications to it (adding paths, removing paths, restructuring groups) ARE permitted under the autonomous workflow but MUST include the K-meta forensic callout in the commit message (see IX.A's K-meta row).
- Adding a file to the Kernel is a forward-compatible safety improvement (broadens the forensic-attention list). Removing a file is a contraction of the safety surface and SHOULD be paired with a brief commit-message justification.

#### IX.D — Operator Autonomy Supremacy (NEW, NON-NEGOTIABLE, added v3.0.0)

The operator's stated autonomy preference is the **supreme decision criterion** for procedural conflicts. When a procedural rule anywhere in this constitution, in a spec, in CLAUDE.md, or in this session's reasoning would block autonomous progression initiated by an operator-instructed session, the autonomous path wins.

This DOES NOT relax the trading-safety invariants:

- **Principle I** (position caps) — still non-negotiable. A change that removes a cap is still subject to the spec 007 canary at production-deploy time.
- **Principle II** (deny-by-default whitelist) — still non-negotiable, same gate.
- **Principle III** (LLM-only-at-judgment-points) — still non-negotiable, same gate.
- **Principle IV** (append-only audit log) — still non-negotiable, same gate.
- **Principle V** (secret isolation) — still non-negotiable, same gate.
- **Principle VI** (Backtest → Canary → Full Live) — still non-negotiable; spec 008's backtest engine is the first stage, spec 007 the hardened canary is the second.
- **Principle VII** (external API robustness) — still non-negotiable.
- **Principle VIII.A** (ordinary market-hours prohibition plus the exact one-shot owner emergency protocol) — still non-negotiable. Operator urgency alone cannot bypass the protocol's machine checks.

What IX.D explicitly relaxes:

- "Wait for the operator to approve a PR" — the session's chat-channel approval (or the operator-instructed merge command) IS the approval.
- "Wait for the operator to amend the constitution" — when the constitution itself is the procedural barrier, the session MAY amend it under operator instruction, recording the change as a K-meta forensic event.
- "Defer Kernel touches to a separate human review" — under v3.0.0 they ride the same PR.

**Rationale**: The operator's failure mode is loss of money via bad trading decisions, not loss of money via a self-rewriting safety perimeter — because the autonomous tuner doesn't exist yet (spec 005 is a stub), and when it does, spec 007's hardened canary will catch misbehaviour at the production-deploy boundary. Procedural friction at the merge boundary delivered no safety benefit in practice (the operator's K4 touches were all additive: spec 002's migration 0002, spec 008's event-type Union extension) and consumed operator attention that should have gone to trading-strategy quality. v3.0.0 moves the safety perimeter from the merge boundary to the production-deploy boundary, where it actually defends real money.

**Trade-off acknowledged**: under v3.0.0, a future misbehaving autonomous tuner CAN merge a change that removes K1 (position caps). The change lands in `main`. It does NOT reach the live worker unless it passes spec 007's hardened canary or unless an operator-instructed session deploys it. Reversion is one PR away (main is always deployable; main with a regression is one PR away from being main without the regression).

### X. Measurement-Driven Autonomous Growth (added v3.1.0)

The system's purpose is not merely to trade safely but to **grow itself toward world-class performance autonomously**, and that growth MUST be driven by measured evidence, not by guesses.

1. **Measure before you tune.** Any autonomous self-modification that targets trading performance (spec 005's tuner) MUST be justified by live/paper performance measurement (spec 011) — realized/unrealized PnL, risk-adjusted metrics (Sharpe, max drawdown, win rate, profit factor), and per-rule/per-symbol attribution. A tuning action with no upstream measurement signal is not permitted.
2. **One yardstick.** Live, paper, canary, and backtest performance MUST be computed with the **same metric definitions** (spec 008 `backtest/metrics.py` is the single source). This makes "backtest said X, live did Y" a meaningful comparison and lets the tuner detect strategy decay (e.g., rolling Sharpe 1.2 → 0.8).
3. **Each completed phase auto-deploys.** A merged change auto-deploys to the running system via the VIII.B-guarded pipeline (`deploy/AUTO-DEPLOY.md`): an immediate on-merge trigger plus the off-hours timer safety net. This keeps the running worker continuously at `main`.
4. **Deploy ≠ live money; capital sizing is governed by the evidence-gated capital ladder under a standing operator delegation (amended v11.0.0).** Auto-deploy lands code and restarts the worker; it does NOT by itself move the system from dry-run to real orders. Live exposure — both the arming decision and the **amount of capital deployed** — is governed by the **spec 050/150/166/167/176 capital ladder**, authorised by the operator's standing delegation (mason, 2026-06-11: "1·2·3 모두 세계 최고 수준이 목표. 3번도 나는 자동과 자율에 맡길거야. 기준은 계좌 잔고와 포트폴리오"):
   - **Rungs**: 0 = 0% (disarmed) → 1 = 10% bounded canary (research-family or operational-verification entry) → 2 = 20% exploration canary → 3 = 25% → 4 = 50% → 5 = 100% of the **measured real account NAV** (KIS balance, multi-exchange sweep). The account balance is the delegation's ceiling; deposits are physically operator-only.
   - **Entry (rung 0→1, operational verification)**: under the operator's 2026-08-31 instruction to finish real automated order/fill verification, the pre-existing exact `globalfixed-ensemble-3-6-9-12` deploy candidate MAY receive at most 10% of current measured NAV solely to verify real order, fill, slippage, reconciliation, and append-only audit plumbing. ALL of the following are required: development and holdout are time-disjoint with zero overlap and each contains at least 120 months; the holdout includes at least 50bp annual cost; holdout CAGR is positive, Sharpe is at least 1.0, maximum drawdown is at most 10%, Sharpe beats the benchmark, and drawdown is at most 80% of the benchmark; raw monthly candidate and benchmark factors are published so the consumer can recompute every metric, active-return PSR, and 100bp/150bp cost sensitivity; evidence is fresh, main-lineage, typed `operational_canary_entry`, and its candidate, strategy, data, selected-deploy, configured, and live fingerprints match exactly; hardened-canary PASS and execution-proxy parity hold; and a fresh read-only whole-share preview at exactly 10% satisfies the same quote, funded-leg, L1-error, per-leg-error, cash, minimum-notional, whitelist, and exposure-cap constraints as the research route. For this shared fundability contract, a positive target is `whole-share-expressible` only when its target notional at the current canary capital and invested fraction is at least one positive current quote. At least one expressible target MUST exist and at least 66% of expressible targets MUST finish with one or more shares. Targets below one share are excluded only from that funded-leg denominator; every positive target remains inside 100% quote coverage, 25% L1 capital-weight error, 15% per-leg error, cash, minimum-notional, whitelist, and exposure-cap checks. The evidence and sentinel MUST publish `alpha_confirmed=false`, `max_rung=1`, `promotion_above_rung1_allowed=false`, and `entry_route=operational_canary`. This route MUST NOT use contaminated historical forward ledgers, MUST NOT be described as confirmed alpha, and MUST NEVER promote above rung 1 from live duration or observations alone. Research diagnostics and capital-entry evidence MUST be separate typed artifacts so one cannot overwrite or substitute for the other. Before the first strategy fill, the signed regular-session order workflow MUST revalidate all evidence, exact fingerprints, fundability, account reconciliation, halt state, kill switch, and current sentinel. Any missing or contradictory fact remains at 0%; risk-reducing exits remain available under the existing safety gates.
   - **Entry (rung 0→1, research-family)**: ALL of — `gate_version=3.1` (`calibrated-family-entry-v3.1`) evidence contains at least 16 preregistered current-family trials and raw records for the whole research program. The consumer, not the producer, MUST independently recount complete audit rows, current-family rows, prior rows, candidate identifiers, strategy fingerprints, the exact current-family audit tail, selected-row identity, and all four producer audit counts (`complete_family_trials`, `prior_audit_complete`, `global_audit_trials`, `unique_audit_fingerprints`). It MUST also classify every raw audit row into a known preregistered research family and match the producer's family identifier, family count, candidate count, identity digest, and status counts. Public history MUST be point-in-time, historical samples MUST NOT be reused for promotion, benchmark and live execution MUST be equivalent, thresholds MUST be frozen before results, every producer-declared blocking gate MUST pass, and selected-config/evidence/live fingerprints MUST be identical. The selected standardized holdout PSR MUST equal the selected raw trial row and be at least 0.95; the consumer MUST recompute family DSR and PBO from the published current-family return and even-segment matrices and match the producer values. PBO MUST be at most 0.25. DSR >= 0.95 and raw-candidate Bonferroni across the complete audit ledger MUST remain published diagnostics but MUST NOT duplicate the calibrated hard gate. The repository calibration MUST use seed 60,000 and at least 500 repetitions and demonstrate, for both 16- and 64-candidate correlated families, null admission at most 0.01 and detection at least 0.80 for a planted annual Sharpe of 0.60. Program research spending MUST satisfy `research_family_count × 0.01 <= 0.20`; a 21st family requires a new frozen calibration before results. A fresh read-only order preview at exactly 10% of current measured NAV MUST then reproduce the configured target after symbol mapping, whole-share rounding, minimum notional, available-cash filtering, and all exposure caps: 100% positive-target quote coverage; at least one positive target whose target notional can express one whole share; at least 66% funded among those whole-share-expressible targets; L1 capital-weight error at most 25% across every positive target; and maximum per-leg error at most 15% across every positive target. A below-one-share target is excluded only from the funded-leg denominator and remains inside every quote, error, cash, minimum-notional, whitelist, and cap check. The same preview is revalidated before the first strategy fill. `gate_version=3.0`, legacy, and `gate_version=2.0` evidence are diagnostic-only and can NEVER open capital. Any partial, stale, approximate, contradictory, duplicated, reused, non-vintage, execution-mismatched, statistically uncalibrated, or unfundable evidence remains at 0%. The backtest and preview workflows themselves cannot order or move capital.
   - **Entry/promotion to rung 2 (exploration)**: the existing exploration contract remains unchanged. It requires ALL of: the exact live strategy is a pre-existing deploy candidate; development and holdout are time-disjoint; at least 120 holdout months; at least 50bp annual cost drag; holdout CAGR and Sharpe beat the benchmark; holdout drawdown is at most 80% of benchmark; at least 40 independent forward observations; forward PSR ≥ 0.80; forward Calmar superiority; hardened-canary PASS; strategy-fingerprint identity; and the live-rung evidence below when coming from rung 1. Factory evidence alone can NEVER move capital above 10%.
   - **Promotion (rung 2→3)**: the original forward-paper **EDGE_CONFIRMED** threshold, plus ALL live evidence below. Exploration evidence alone can never move capital above 20%.
   - **Promotion (rung n→n+1)**: ALL of — ≥ 20 live NAV observations at the current rung, ≥ 27 calendar days at the rung, and drawdown-since-rung-entry < budget/2. Missing or unmeasurable evidence NEVER promotes (fail-safe).
   - **Demotion / halt (immediate, evidence-free downward)**: drawdown ≥ budget/2 drops one rung; drawdown ≥ budget disarms to rung 0; re-entry restarts from forward re-validation. The intra-day fast defence remains the spec 014 loss circuit breaker — the ladder is the slow daily governor above it.
   - **Drawdown budget (20%) is OPERATOR-OWNED.** Changing it is an operator decision, enforced by CI regression. The budget is the maximum new loss surface this delegation enables.
   - **Channel**: ladder decisions are computed by tested pure code (`portfolio/capital_ladder.py`) and executed as sentinel PRs through the ladder gate (`.github/workflows/forward-edge-autoarm.yml`). Real-order wake-up authority is restricted to exactly two automated sources: (a) the signed, nonce-protected market-hours `schedule` of `rebalance-live-canary.yml` and (b) the root-owned `auto-invest-live-canary.timer` fallback on the production host. The fallback MUST start after the primary GitHub opportunity, MUST NOT be remotely or manually exposed as an order command, and MUST reproduce operational-main revision, ladder-authority, first-entry revalidation, XNYS, limit-order, whitelist, position-cap, kill-switch, circuit-breaker, fill-sync, reconciliation, and append-only evidence obligations. Operational-main revision means either exact deployed current main, or an audited deployed commit that is an ancestor of current `origin/main` and differs from it only by the frozen deployment-excluded paths `*.md`, `specs/**`, `.verify/**`, and `.trigger/**`; unreadable history or any other changed path MUST fail closed. First-entry evidence MUST match current main, while deploy audit MUST match the actual deployed operational commit, and both identities MUST be recorded. Both scheduler and internal `systemd-order` MUST independently repeat this test before the shared claim. Both sources MUST converge on one root-owned market-session claim so at most one broker-writing execution can occur per XNYS session; a claim followed by failure or partial execution is never automatically retried that day. `workflow_dispatch`, `repository_dispatch`, arbitrary shell, and any other event remain real-order-ineligible. The guarded go-live channel obligations of v4.0.0 (market-hours guard, deploy audit events, post-restart health check with auto-revert, and untouched principles I, II, IV, V) continue to apply to worker-mode transitions.

   **What stays non-delegable**: the kill switch (`automation/AUTOARM_DISABLED`), the spec 014 circuit breaker, the position-cap mechanism (I), the whitelist (II), append-only audit (IV), secret isolation (V), the staged-rollout structure (VI — the ladder IS its promotion path, with acceptance metrics predeclared in code and every rung change recorded), the market-hours guard (VIII.A), and budget ownership. The spec 005 tuner MUST NOT modify the ladder, the budget, or the sentinel. Bank deposits, brokerage account agreements (derivatives/margin/short access), and the session container's network policy are physically operator-only acts.

5. **Strategy reassignment is governed by the evidence-gated 5-gate tournament under the same standing operator delegation (amended v6.0.0).** Item 4 governs HOW MUCH capital the live system deploys; this item governs WHICH strategy it deploys. The operator delegated strategy selection (mason, 2026-06-16: "자율 전략 진화 폐회로 — 더 나은 전략을 시스템이 스스로 라이브로 교체. 완전 자율 + 5중 안전장치"). The autonomous forward tournament (spec 037/049) continuously races the live strategy (the *incumbent*) against challengers; when a challenger clears ALL FIVE gates the system reassigns the live strategy to that challenger WITHOUT per-change operator approval:
   - **Gate ① edge confirmed** — the challenger is forward-paper EDGE_CONFIRMED.
   - **Gate ② multiplicity-corrected** — the challenger survives multiple-testing correction (deflated Sharpe / Bonferroni across the simultaneously-raced tracks); a lucky winner among many tracks does NOT qualify.
   - **Gate ③ apples-to-apples** — the challenger beats the incumbent over a COMPARABLE forward window (both measured on the same period; spec 049 `challenger_key` encodes ① and ③ together).
   - **Gate ④ hardened canary** — the challenger PASSES the spec 007 hardened canary (historical replay + shock + fuzz). This is small-real-money *validation*, not a deploy.
   - **Gate ⑤ re-validation after reassignment** — reassignment RESETS the item-4 capital ladder to rung 0. The new strategy re-earns the 10% research canary or existing 20% exploration canary and then the original forward-confirmed 25% upward path through item 4's evidence gates. Capital is NEVER carried over to an unproven strategy.

   Any gate missing or unmet ⇒ HOLD the incumbent, never reassign (fail-safe, identical posture to the ladder). The kill switch (`automation/AUTOARM_DISABLED`) halts reassignment too. Reassignment decisions are computed by tested pure code (`portfolio/auto_reassign.py`), executed as config + sentinel PRs through the same gate workflow, and recorded (PR + audit trail). The spec 005 tuner MUST NOT reassign the live strategy outside this gate. **Bounded worst case**: reassignment can only move the live system to a strategy that won a multiplicity-corrected forward race AND passed the hardened canary, and even then capital restarts at rung 0 and first enters at 10% research or 20% exploration under item 4's operator-owned 20% drawdown budget with immediate halt. Reassignment changes WHICH strategy is exposed, not HOW MUCH — the down-fast/up-slow ladder still bounds the amount.

   **Spec 150 factory route**: a complete factory winner under item 4's versioned complete-family and cumulative-audit contract MAY replace the live candidate configuration only while the ladder is rung 0 and disarmed. That zero-capital assignment is not a funded reassignment: it opens no order and inherits no trust. After deployment, the exact configured strategy MUST pass the hardened canary again; only then may item 4 grant the bounded 10% research rung. The operational-verification route is restricted to the exact preregistered spec 176 candidate and cannot fund a newly reassigned factory strategy. Neither route can reach 20% without the existing exploration contract or reach 25% without EDGE_CONFIRMED.

This DOES NOT relax principles I–VII or VIII.A. The production-money defence remains spec 007's hardened canary (IX.B-2). Measurement-driven growth operates entirely **within** the existing safety perimeter: it adds a *requirement* (evidence before tuning) and a *standing mode* (continuous deploy of merged work to a dry-run worker), neither of which widens the loss surface.

**Rationale**: A self-growing system that tunes on guesses instead of measured performance is just a faster way to drift. spec 011 makes live behaviour measurable on the same yardstick as backtest, so the future tuner (spec 005) and the operator act on evidence. Naming the auto-deploy mode as a principle (not just an ops doc) ensures the "deploy ≠ live money" separation is a constitutional invariant, not a convention that could erode.

## Investment Domain Constraints

- **Initial scope**: US listed equities (NYSE / NASDAQ / AMEX) traded via Korea Investment & Securities (KIS) OpenAPI.
- **Currency**: orders priced in USD; KRW↔USD conversion is tracked as a separate, observable risk.
- **Default order type**: limit orders only. Market orders require an explicit per-symbol opt-in with a documented liquidity justification recorded in the spec.
- **Out of scope (v1.0.0)**: derivatives, leverage, short selling, options, futures, crypto, domestic Korean equities.

## Development Workflow

- **Spec-Driven Development is mandatory.** Every feature flows through `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`. Code that has no upstream spec MUST NOT be merged.
- **Test gates.** Modules touching risk checks, order validation, reconciliation, or judgment-call contracts MUST have automated tests passing before merge.
- **Tooling.** `ruff check` and `pytest` MUST pass on every commit reaching `main`.
- **Branching.** Work happens on dedicated branches; `main` is always deployable.
- **Reviews.** Changes to risk-related modules require an explicit self-review against this constitution before merge, recorded in the commit message or PR description.

## Governance

This constitution supersedes all other practices, conventions, and ad-hoc decisions. When a principle conflicts with convenience or velocity, the principle wins.

**Amendments**: require (a) a dedicated commit modifying this file, (b) a version bump per the policy below, and (c) propagation to dependent templates (`plan-template.md`, `spec-template.md`, `tasks-template.md`).

**Versioning** (SemVer):
- **MAJOR**: principle removal or backward-incompatible redefinition.
- **MINOR**: principle addition or material expansion of guidance.
- **PATCH**: clarifications, wording, typo fixes.

**Compliance**: every `/speckit-plan` artifact MUST include a Constitution Check section verifying the plan does not violate principles I–X. Violations require explicit, written justification and a sign-off recorded in the audit log.

**Version**: 15.3.0 | **Ratified**: 2026-05-01 | **Last Amended**: 2026-09-03
