# Implementation Plan: Security Trust Boundary Hardening

## Summary

Harden the trust boundary around public GitHub workflows, remote server execution, canary promotion, deploy locking, token caching, order recovery, exposure-reducing sells, and public sidecar evidence. The implementation keeps the system read-only/dry-run from this session, blocks newly identified fail-open paths, and leaves rotation of real production secrets as an operator action.

## Technical Context

- Language: Python 3.11, Bash, GitHub Actions YAML
- Storage: SQLite audit/orders tables, filesystem token cache, public sidecar branches
- Critical paths: `.github/workflows/**`, `deploy/sync-units.sh`, `src/auto_invest/deploy/**`, `src/auto_invest/broker/auth.py`, `src/auto_invest/execution/**`, `src/auto_invest/risk/gates.py`
- Testing: pytest unit/integration, ruff, workflow scanners, shell syntax checks, harness checks

## Constitution and Safety

- Risk grade: 3 because risk gates, audit payloads, deployment gates, and workflow safety controls change.
- K1 touched: `src/auto_invest/risk/gates.py`; sell handling must prevent oversell and keep exposure caps intact.
- K4 touched: `src/auto_invest/persistence/audit.py`; canary evidence gains a ruleset hash but legacy rows remain parseable.
- K-meta untouched: no constitution or kernel manifest change; commit message does not need the safety-perimeter literal.
- Money path: no real order, live mode switch, or capital allocation is executed.

## Design

1. Add reusable CI guard scripts for secure SSH setup, numeric input validation, and public sidecar redaction.
2. Pin mutable GitHub Actions and make SSH calls use `StrictHostKeyChecking=yes` with repository-provided known hosts.
3. Make go-live fail closed on unknown market/revision state and restore full `.env` backup.
4. Require `CANARY_PASSED` rows to carry exact candidate and ruleset hashes.
5. Replace deploy PID lock with an open file descriptor lock.
6. Write broker token cache through private directories and atomic replacement.
7. Extend execution-state degradation to stale BUY intents/submitting orders.
8. Strengthen unknown-order broker recovery matching with type, price, and timing evidence.
9. Add reduce-only classification to risk gates and pass current position quantity from the order router.
10. Treat missing marks for open positions as degraded risk for new BUY orders.

## Validation

- `uv run pytest tests/unit/test_deploy_guards.py -q`
- `uv run pytest tests/unit/test_deploy_steps.py -q`
- `uv run pytest tests/unit/test_broker_auth.py -q`
- `uv run pytest tests/unit/test_execution_state.py -q`
- `uv run pytest tests/unit/test_fill_sync.py -q`
- `uv run pytest tests/unit/test_risk_gates.py -q`
- `uv run pytest tests/unit/test_security_workflow_hardening.py -q`
- `uv run pytest -q`
- `uv run ruff check src tests`
- `git diff --check`
- `uv run python scripts/check_handoff_facts.py`
- `uv run python scripts/agent_harness_probe.py --strict`

## Rollback

Revert the feature PR. This restores the previous workflow behavior, canary gate, lock, cache, and order-risk behavior. Production secret rotation and server key cleanup are intentionally operator-side and are not performed by this PR.
