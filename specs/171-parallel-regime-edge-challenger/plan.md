# Implementation Plan: Parallel Regime Edge Challenger

**Branch**: `codex/171-parallel-regime-edge-challenger` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)

## Summary

Separate the proxy-parity observer's ephemeral bars database from its long-lived KIS token cache,
then implement one frozen 16-candidate correlation-and-joint-weakness overlay around the deployed
trend incumbent. Select only on pre-2007 development data, leave a one-month embargo, evaluate once
on the remaining holdout, and publish a no-order research verdict with full gate decomposition.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: standard library, NumPy, existing analytics significance helpers and public-data adapters  
**Storage**: JSON/Markdown research evidence; ephemeral SQLite bars DB; shared KIS token JSON  
**Testing**: pytest, Ruff, JSON validation, deterministic probe replay, KIS read-only production observer  
**Constraints**: no look-ahead, no post-result parameter changes, no orders, no promotion, fail closed

## Constitution Check

- **Risk grade**: 4, because the evidence may become an input to a future first-capital decision.
- **Position/whitelist/order controls**: UNCHANGED. No live configuration or order route changes.
- **Backtest -> Canary -> Full**: PRESERVED. A historical pass can only create a research candidate.
- **Judgment points**: NONE. The algorithm is deterministic; no LLM is called per bar or period.
- **Secrets**: STRENGTHENED. An existing valid token is reused without printing it; failure stays closed.
- **Auditability**: STRENGTHENED. Candidate identities, data split, cost assumptions, gates, and controls are serialized.
- **Program multiplicity**: 18 families gives a 0.18 false-acceptance budget under the calibrated 0.20 ceiling.
- **Rollback**: revert the token-cache CLI/observer change and challenger module independently. Reverting the
  observer fix restores extra token issuance but cannot open capital; reverting the challenger removes only
  research evidence because no live mapping is changed.

## Project Structure

```text
src/auto_invest/analytics/regime_adaptive_challenger.py
src/auto_invest/cli.py
scripts/regime_adaptive_challenger_probe.py
deploy/observe-on-instance.sh
tests/unit/test_regime_adaptive_challenger.py
tests/integration/test_regime_adaptive_challenger_probe.py
tests/unit/test_forward_edge_autoarm_workflow.py
specs/171-parallel-regime-edge-challenger/
```

## Design Decisions

1. Add `--token-cache` without changing the legacy default, limiting operational impact to explicit callers.
2. Rebuild total-return levels from existing monthly factors; period t weights use levels ending at t-1.
3. Define one-way turnover as half the absolute change across stock, bond, gold, and cash weights.
4. Charge identical costs to challenger and incumbent so a low-turnover strategy does not receive a hidden advantage.
5. Freeze the candidate grid and report fingerprint before observing production results.
6. Keep the challenger outside the live factory evidence until it passes this contract and a separate paper-forward phase.

## Implementation Order

1. Commit and push all preregistration artifacts.
2. Write failing token-cache and strategy invariance tests.
3. Implement the smallest CLI/observer liveness correction.
4. Implement deterministic monthly candidate evaluation and report validation.
5. Run focused tests, then the preregistered production-data probe exactly once.
6. Run negative/positive/time-shift/cost controls and full repository verification.
7. Merge, verify the dry-run worker and sidecars, and refresh HANDOFF through a separate PR if needed.
