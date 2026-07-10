# Research: Agent Harness Regression Liveness Contract

## Decision 1: Reuse the existing harness evaluator

**Decision**: Import `scripts/agent_harness_probe.py` and call `evaluate_task_suite`, `evaluate_quality_suite`, and `evaluate_redteam_suite` from the new report module.

**Rationale**: The existing probe is already the source of truth for required risk grades, control categories, quality categories, and redteam attack types. Duplicating those rules would create two contracts that can drift.

**Alternatives considered**:

- Re-parse TOML directly in the new module. Rejected because it duplicates validation logic and can diverge from strict harness behavior.
- Run `agent_harness_probe.py --strict` from the report. Rejected because the report should be pure and deterministic; strict execution output is better supplied as evidence.

## Decision 2: Treat missing strict output as WAIT, not FAIL

**Decision**: Missing supplied strict output yields `OBSERVATION_WAIT`; degraded or score-mismatched output yields `BLOCKED`.

**Rationale**: Before merge, strict output must be provided. During local pre-release probe generation, the absence of a just-run output is an observation gap, not proof the harness is broken.

**Alternatives considered**:

- Fail on missing output. Rejected because pre-release sidecar-style probes often run before all external evidence exists.
- Pass on current source-only coverage. Rejected because the contract must prove the actual strict gate was observed.

## Decision 3: Add a next operating candidate

**Decision**: Add `candidate-operator-report-liveness-contract` after `candidate-agent-harness-regression-liveness-contract`.

**Rationale**: Local reproduction showed that when agent harness liveness is marked released, the current agent-ops frontier has no open next candidate and autonomous-work falls to `OBSERVATION_WAIT`. The next recurring operating risk is operator-readable completion reporting: rules and quality tasks exist, but no candidate-level PASS/WAIT/FAIL contract closes them.

**Alternatives considered**:

- Leave no next candidate. Rejected because it makes the operator ask for the next work again.
- Reuse PR/merge evidence liveness. Rejected because that candidate is already released and covers PR evidence, not the clarity of final operational reporting.

## Decision 4: Keep safety boundary read-only

**Decision**: The report reads local files and supplied evidence only. It does not call GitHub, SSH, broker APIs, paid services, or mutate repository state.

**Rationale**: This is an operating-system observability contract, not a new automation execution path. It must be safe to run in local and CI contexts.
