# Implementation Plan: Research Canary Evidence Parity

**Branch**: `Codex/161-research-canary-evidence-parity` | **Date**: 2026-08-25 | **Spec**: [spec.md](spec.md)
**Input**: Production factory run on commit `7cca336` and autoarm run on commit `c74e947`.

## Summary

Replace the stale `64/64` research-canary consumer constant with a versioned, fail-closed completeness validator. Reuse that validator in the zero-capital assignment workflow, capital ladder CLI, and first-live-entry revalidation. Amend constitution X.4 to describe the current minimum-16 complete-family and cumulative-audit contract. Do not lower producer statistical gates or any capital threshold.

## Technical Context

**Language/Version**: Python 3.11, Bash, GitHub Actions YAML
**Primary Dependencies**: existing Typer CLI, portfolio fingerprinting, strategy factory JSON sidecars
**Storage**: read-only JSON sidecars and existing sentinel file
**Testing**: pytest, ruff, Ruby YAML parser, bash syntax, strict agent harness
**Target Platform**: GitHub Actions and Linux production worker
**Project Type**: CLI trading automation and evidence workflows
**Performance Goals**: evidence validation under 100 ms; no added network call
**Constraints**: fail closed; no direct orders; no threshold reduction; all three consumers must agree
**Scale/Scope**: one shared validator, three consumers, one workflow, constitution X.4, focused contracts and tests

## Constitution Check

- Grade 4 safety-perimeter change; full SDD and explicit forensic commit marker are required.
- Rung 0 remains zero capital unless the complete factory, fresh hardening, exact fingerprint, account NAV, and existing safety gates pass.
- The maximum newly reachable exposure remains rung 1 at 10% of account NAV.
- The 20% exploration and 25%/50%/100% gates remain unchanged and cannot be skipped.
- Missing counts, missing gates, failed blocking gates, missing config, stale evidence, or fingerprint mismatch fail closed.
- Backtest workflows cannot order. Existing sentinel PR and market-schedule separation remains.
- K1 caps, K2 whitelist, append-only audit, secrets, reconciliation, halt, and drawdown budget are unchanged.

Post-design check: PASS, conditional on the constitution and all consumers landing atomically.

## Project Structure

```text
src/auto_invest/portfolio/factory_evidence.py
src/auto_invest/portfolio/live_entry_revalidation.py
src/auto_invest/portfolio/capital_ladder.py
src/auto_invest/cli.py
scripts/factory_evidence_gate.py
.github/workflows/forward-edge-autoarm.yml
.specify/memory/constitution.md
tests/unit/test_factory_evidence.py
tests/unit/test_ladder_decide_cli.py
tests/unit/test_live_entry_revalidation.py
tests/integration/test_factory_evidence_gate.py
specs/161-research-canary-evidence-parity/
```

**Structure Decision**: Add one pure evidence validator and one thin workflow probe. Keep strategy producers and order execution unchanged.

## Complexity Tracking

| Change | Why Needed | Simpler Alternative Rejected Because |
|--------|------------|---------------------------------------|
| Shared versioned validator | Three consumers have drifted | Three constant edits would drift again |
| Constitution major update | X.4 currently mandates 64 | Silent implementation divergence violates the safety perimeter |
