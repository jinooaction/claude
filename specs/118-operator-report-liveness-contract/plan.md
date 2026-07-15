# Implementation Plan: Operator Report Liveness Contract

## Summary

Add a read-only operator report liveness contract that proves the repository still enforces operator-understandable completion reports and classifies supplied final-report text as PASS/WAIT/FAIL. The report consumes local rule surfaces and released-work evidence, exposes a CLI probe, and ensures autonomous-work does not reselect this candidate after release.

## Technical Context

- Language: Python 3.11
- Storage: Repository Markdown/TOML/JSON files and supplied evidence text; no database changes
- Existing operating surfaces: `AGENTS.md`, `.codex/quality-gate.md`, `.github/pull_request_template.md`, `.codex/harness/quality_tasks.toml`, `HANDOFF.md`
- Existing autonomous queue: `src/auto_invest/analytics/autonomous_work_execution.py`
- Testing: pytest unit and probe integration tests

## Constitution and Safety

- Grade 2 operating-system change.
- Principles I, II, IV, V, VI, VII, VIII.A remain untouched: no order, capital, whitelist/caps, audit-log mutation, secret, staged-rollout, API robustness, or live deploy behavior changes.
- Principle IX/Kernal high-attention files are not modified.
- Principle X is supported by preventing operating-loop confusion after completion reports.

## Design

1. Add `src/auto_invest/analytics/operator_report_liveness.py`.
2. Read local rule surfaces and supplied evidence text.
3. Parse `QUALITY-006` from TOML and verify required categories.
4. Classify final report observations with deterministic category checks:
   - conclusion-first operating state
   - changed/fixed work
   - money/safety/automation/handoff meaning
   - verification evidence
   - remaining risk or next observation
   - evidence not used as the only conclusion
5. Expose JSON/Markdown through `scripts/operator_report_liveness_probe.py`.
6. Add unit and integration tests.
7. Add an autonomous-work focused test proving released operator-report candidate is consumed.
8. Mark SDD tasks complete after verification.

## Validation

- `uv run pytest tests/unit/test_operator_report_liveness.py -q`
- `uv run pytest tests/integration/test_operator_report_liveness_probe.py -q`
- `uv run pytest tests/unit/test_autonomous_work_execution.py -q`
- `uv run pytest -q`
- `uv run ruff check src tests`
- `git diff --check`
- `uv run python scripts/check_handoff_facts.py`
- `uv run python scripts/agent_harness_probe.py --strict`
- PR quality gate with the filled PR body
