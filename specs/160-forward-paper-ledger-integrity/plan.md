# Implementation Plan: Forward Paper Ledger Integrity

**Branch**: `Codex/160-forward-paper-ledger-integrity` | **Date**: 2026-08-25 | **Spec**: [spec.md](spec.md)
**Input**: Production evidence from forward run `32806587413` and capital-ladder run `32806947129`.

## Summary

Invalidate forward paper evidence whose simulated account borrowed cash, preserve the old databases for audit, and move all seven producers and consumers to a clean versioned database epoch. Add a command-level negative-cash interlock before any NAV snapshot is appended. No live order, capital, strategy threshold, whitelist, cap, constitution, or kernel changes.

## Technical Context

**Language/Version**: Python 3.11, Bash, GitHub Actions YAML
**Primary Dependencies**: Typer CLI, SQLite, existing audit/performance/forward verdict modules
**Storage**: Seven isolated SQLite paper databases plus append-only audit rows
**Testing**: pytest, ruff, Ruby YAML parser, shell syntax, strict agent harness
**Target Platform**: Linux production worker and GitHub Actions
**Project Type**: CLI trading automation and operational workflows
**Performance Goals**: One clean backfill/rebalance/NAV cycle per track within the existing 30-minute workflow timeout
**Constraints**: No legacy database deletion; no live broker order; no threshold weakening; fail closed before evidence publication
**Scale/Scope**: Seven forward tracks and their candidate-history, ladder, IC, and cross-asset consumers

## Constitution Check

- Grade 3 safety-evidence change. The output can only remove eligibility or create new clean paper evidence; it cannot increase live exposure.
- Rung 0 stays at zero capital until existing exploration or full edge contracts pass.
- The 0.80 exploration and 0.95 full thresholds remain unchanged.
- Exact strategy fingerprints, historical holdout, hardened canary, live-entry revalidation, K1 caps, K2 whitelist, audit logs, and `Backtest -> Canary -> Full` remain mandatory.
- Missing, negative-cash, under-observed, or mismatched evidence remains fail closed.
- Legacy DBs are retained. Rollback changes the active path mapping only and never deletes data.

Post-design check: PASS. The design changes paper evidence lineage and a pre-snapshot validity check only.

## Project Structure

```text
src/auto_invest/cli.py
src/auto_invest/analytics/candidate_history_support.py
scripts/daily_cross_asset_ml_probe.py
deploy/observe-on-instance.sh
.github/workflows/rebalance-paper-forward.yml
tests/integration/test_forward_verdict_cli.py
tests/integration/test_candidate_result_executor_probe.py
tests/unit/test_candidate_history_support.py
tests/unit/test_security_workflow_hardening.py
tests/unit/test_forward_workflow_leaderboard_json.py
specs/160-forward-paper-ledger-integrity/
```

**Structure Decision**: Reuse the existing CLI, observation helper, and workflow. The clean epoch is a path mapping, not a new service or migration that mutates old databases.

## Complexity Tracking

No constitutional exceptions.
