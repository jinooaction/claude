# Feature Specification: Operator Report Liveness Contract

**Feature Branch**: `codex/118-operator-report-liveness-contract`  
**Created**: 2026-07-15  
**Status**: Draft  
**Input**: Autonomous-work selected candidate `candidate-operator-report-liveness-contract`.

## Goal

Final Codex reports must be machine-checkable for operator readability before the work is treated as complete. The system needs a read-only PASS/WAIT/FAIL contract that verifies the reporting rules in `AGENTS.md`, `.codex/quality-gate.md`, `.github/pull_request_template.md`, `QUALITY-006`, `HANDOFF.md`, released-work evidence, and supplied final-report text so the operator can understand what changed, what it means for money/safety/automation/handoff, how it was verified, and what risk remains.

## Non-Goals

- Do not call GitHub, broker APIs, SSH, local desktop apps, or external paid services.
- Do not place, cancel, modify, or retry any order.
- Do not arm live sentinels, change capital, widen whitelists, or alter position caps.
- Do not modify the constitution or kernel manifest.
- Do not replace the existing PR quality gate or strict agent harness; consume their evidence instead.
- Do not make subjective language scoring with an LLM.

## Risk Grade

Grade 2: operating-system change. This adds a new read-only completion-report contract and autonomous-work completion marker. It changes next-session and final-report operating behavior, but it does not touch trading safety boundaries or the money path.

## User Stories

### User Story 1 - Report rules are alive and traceable (P1)

As the operator, I need the repository to prove that the reporting rules I rely on still exist in the actual operating surfaces.

**Acceptance Criteria**

- The report reads `AGENTS.md`, `.codex/quality-gate.md`, `.github/pull_request_template.md`, `.codex/harness/quality_tasks.toml`, and `HANDOFF.md`.
- The report classifies the rule surface as `PASS` only when the required reporting obligations are present: first sentence conclusion, created/fixed summary, money/safety/automation/handoff meaning, verification evidence, remaining risk, and grade 2 removed/retained functionality.
- Missing or malformed rule surfaces produce `BLOCKED`, not a false pass.

### User Story 2 - Supplied final report is classified without guessing (P1)

As the next session, I need a supplied final report to be checked for the minimum structure that prevents "그래서 뭘 했다는 거야?" follow-up questions.

**Acceptance Criteria**

- A final report with operator-state conclusion, changed work, meaning, verification, and remaining risk is classified `PASS`.
- Missing final-report text is classified `OBSERVATION_WAIT`.
- A report that only lists PR numbers, hashes, or test names without meaning is classified `BLOCKED`.
- The checker does not require a fixed template, but it must require the semantic evidence categories.

### User Story 3 - Completion advances the autonomous queue cleanly (P2)

As a future Codex session, I need released-work to consume this candidate so the same operating-system task is not selected again.

**Acceptance Criteria**

- The report exposes `completed_candidate_id: candidate-operator-report-liveness-contract`.
- When released-work contains that candidate, autonomous-work marks `operator_report_liveness` as released.
- If no other executable candidate exists, autonomous-work does not re-emit the same candidate as open work.

## Requirements

- **FR-118-01**: System MUST expose a deterministic operator report liveness report with `overall_status`, `completed_candidate_id`, `next_candidate_id`, evidence surfaces, rule surface summary, final report summary, quality gates, released-work summary, and safety invariants.
- **FR-118-02**: System MUST read only local files and supplied evidence text.
- **FR-118-03**: System MUST verify `AGENTS.md` contains the final-report obligations for conclusion-first reporting, meaning, verification, remaining risk, and removed/retained functionality for grade 2+ work.
- **FR-118-04**: System MUST verify `.codex/quality-gate.md` contains the operator-readable report gate.
- **FR-118-05**: System MUST verify `.github/pull_request_template.md` preserves problem definition, verification, harness evidence, safety boundary, handoff, and automatic-merge readiness sections.
- **FR-118-06**: System MUST verify `QUALITY-006` exists and includes honest reporting, operator readability, problem definition, safety boundary, and handoff awareness.
- **FR-118-07**: System MUST verify `HANDOFF.md` points future sessions to live truth and records operator-readable reporting expectations.
- **FR-118-08**: System MUST classify supplied final-report text as `PASS`, `WAIT`, or `FAIL` using deterministic text checks for conclusion, work summary, meaning, verification, remaining risk, and evidence/meaning separation.
- **FR-118-09**: System MUST classify released-work evidence as `PASS` when it has released this candidate, `WAIT` when absent or not yet consumed, and `FAIL` when malformed.
- **FR-118-10**: System MUST provide a CLI probe that can write JSON and Markdown reports.
- **FR-118-11**: System MUST NOT mutate repository files, call networks, read secrets, or execute broker/order/capital paths from the report module.
- **FR-118-12**: System MUST update autonomous-work behavior so released `candidate-operator-report-liveness-contract` no longer appears as an open selected work item.

## Key Entities

- **Rule Surface**: Repository document or task suite that states what an operator-readable report must contain.
- **Final Report Observation**: Supplied final answer text from a completed Codex task.
- **Report Requirement Gate**: Deterministic PASS/WAIT/FAIL check for one required meaning category.
- **Released Completion Marker**: `completed_candidate_id` field consumed by released-work after all tasks are checked.

## Success Criteria

- **SC-118-01**: Focused unit tests show all rule surfaces and a complete final report produce `CONTRACT_READY`.
- **SC-118-02**: Missing final report produces `OBSERVATION_WAIT`, not `BLOCKED`.
- **SC-118-03**: Hash/PR-only final report produces `BLOCKED`.
- **SC-118-04**: Broken `QUALITY-006` or missing report rules produce `BLOCKED`.
- **SC-118-05**: Probe integration test writes matching JSON and Markdown artifacts.
- **SC-118-06**: Autonomous-work focused test proves released `candidate-operator-report-liveness-contract` is consumed and not selected again.
- **SC-118-07**: `uv run pytest -q`, `uv run ruff check src tests`, `git diff --check`, `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`, and the PR quality gate pass before merge.

## Assumptions

- The supplied final report is captured by workflow, PR body, or manual probe input; this feature does not scrape chat history.
- Deterministic text checks are sufficient for a minimum completion contract. Human-quality style review remains outside scope.
- Existing PR quality and harness gates remain the source of truth for merge readiness; this feature checks the operator-facing meaning layer.

## Release Ledger

completed_candidate_id: candidate-operator-report-liveness-contract  
next_candidate_id: none

## Out of Scope Remaining After This Spec

- Automatic capture of final assistant messages from the chat system.
- Scoring tone, polish, or translation quality beyond the required meaning categories.
- Real server, KIS account, GitHub Environment, or secret-protection verification.
