# Implementation Plan: Live Entrypoint Containment

**Branch**: `Codex/111-live-entrypoint-containment` | **Date**: 2026-07-13 | **Spec**: `specs/111-live-entrypoint-containment/spec.md`  
**Input**: Feature specification from `/specs/111-live-entrypoint-containment/spec.md`

## Summary

Convert the legacy `operator-design` path from a live-capable automation into a proposal-only design tool. Remove the scheduled trigger and automatic confirmation, make dynamic verification fail closed, transport intent as opaque data, downgrade the executable command policy, and add tests that prove no design path can start a live worker or submit an order.

This is the first slice of the execution safety stabilization program documented in `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md`.

## Technical Context

**Language/Version**: Python 3.11, Bash, GitHub Actions YAML  
**Primary Dependencies**: Typer CLI, Pydantic, existing design modules, existing backtest/paper validation APIs where actually available  
**Storage**: Candidate TOML and structured verification evidence; no live state mutation  
**Testing**: pytest, ruff, workflow source tests, shell transport tests, static no-live-path scan, handoff fact checker, strict agent harness  
**Target Platform**: Local macOS/Linux checkout, GitHub Actions runner, existing Linux operator host  
**Project Type**: Single Python package plus scripts and GitHub workflows  
**Performance Goals**: Proposal generation remains interactive; tests do not use network or paid services  
**Constraints**: No live activation, no real orders, no sentinel changes, no caps/whitelist/loss-budget changes, no secrets exposure  
**Scale/Scope**: One legacy live entrypoint, one shell helper, one verification module, one CLI command path, one command-policy entry, focused tests, documentation

## Risk Classification

- **Implementation risk grade**: 4 — money-path capability change
- **Direction of change**: authority contraction only
- **External effect allowed**: none
- **Operator authorization**: code/test/doc/workflow changes authorized; live activation and orders not authorized
- **Kernel expectation**: no K1/K2/K4/K5/K6/K-meta changes expected
- **Money-path expectation**: design-to-live edge removed; active sentinels unchanged

## Constitution Check

- Principle I, position limits: unchanged.
- Principle II, deny-by-default whitelist: unchanged.
- Principle III, bounded LLM judgment: design LLM use remains bounded; scheduled unnecessary calls are removed.
- Principle IV, append-only audit: event schema and audit writer unchanged. Existing design audit events may still record candidate generation.
- Principle V, secret isolation: preserved; intent transport must not expose secrets.
- Principle VI, staged rollout: strengthened by removing proposal → direct-live bypass.
- Principle VII, external API robustness: no new API path; tests mock all external calls.
- Principle VIII.A, no live deploys during market hours: unchanged.
- Principle IX/X autonomy: autonomous proposal generation can remain, but live execution requires the established evidence path. A6 safety boundary is not widened.

## Ground-Truth Paths to Inspect Before Editing

```text
.github/workflows/operator-design.yml
scripts/operator_design.sh
src/auto_invest/cli.py
src/auto_invest/design/verifier.py
src/auto_invest/design/deploy.py
src/auto_invest/design/validator.py
src/auto_invest/safety/autonomy.py
src/auto_invest/safety/command_registry.py
tests/integration/test_design_cli.py
tests/unit/test_design_deploy.py
tests/unit/test_design_validator.py
tests/unit/test_safety_command_registry.py
```

Codex must search all call sites before deleting or changing public helpers:

```bash
rg -n "operator-design|AUTO_OK|auto_ok|prompt_operator_ok|start_live_worker|verify_rules|RULE_DESIGN_DEPLOYED" .
```

## Target Architecture

```text
Operator intent
    │ opaque payload, no shell evaluation
    ▼
Design command
    │
    ├─ generate candidate rules
    ├─ static validation
    ├─ actual backtest evidence, if available
    ├─ actual paper/simulation evidence, if available
    └─ persist proposal + verification report
            │
            ▼
      existing candidate / promotion path
            │
            └─ no direct live worker startup
```

The design command may read account context if that remains necessary for sizing, but it cannot write broker state or launch a process that can write broker state.

## Project Structure

```text
.github/workflows/
└── operator-design.yml                     # remove schedule and live confirmation semantics
scripts/
└── operator_design.sh                      # proposal-only, safe stdin/file intent transport
src/auto_invest/design/
├── verifier.py                             # fail-closed actual evidence contract
└── deploy.py                               # remove/quarantine direct live worker startup
src/auto_invest/
└── cli.py                                  # design command emits proposal, never starts live
src/auto_invest/safety/
└── command_registry.py                     # design -> PROPOSAL, no live/order flags
tests/unit/
├── test_design_verifier.py                 # new fail-closed verification tests
├── test_design_deploy.py                   # update/remove live startup expectations
├── test_operator_design_workflow.py        # new workflow source and input transport tests
└── test_safety_command_registry.py         # authority classification
tests/integration/
└── test_design_cli.py                      # proposal-only end-to-end command behavior
specs/111-live-entrypoint-containment/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── design-execution-boundary.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

The exact test file names may be adjusted after inspecting existing conventions, but coverage responsibilities must remain.

## Phase 0 — Baseline Reproduction

Before changing code, establish current behavior with read-only inspection and tests.

1. Confirm workflow has `schedule` and auto-live defaults.
2. Confirm shell helper injects `OK` under `AUTO_OK=1`.
3. Confirm verifier returns success without actually invoking both dynamic validators.
4. Confirm the CLI call chain can reach `start_live_worker`.
5. Confirm command registry marks `design` as live-capable.
6. Record all call sites and existing tests that depend on direct live startup.

Do not run the real design command with real secrets. Use source inspection and test doubles only.

## Phase 1 — Tests First

Add failing tests for the desired boundary before implementation.

### Workflow contract tests

- No `schedule` trigger.
- No `auto_ok` default true.
- No `AUTO_OK=1` conversion.
- No raw intent interpolation into an SSH command.
- Workflow result states design completion is proposal-only.

### Shell helper tests

- No `echo "OK" |` or equivalent automatic confirmation.
- Intent may be accepted from stdin or a file.
- Quotes, shell metacharacters, Unicode, and multiline input are preserved.
- Helper does not call a live subcommand.

### Verification tests

- Static failure -> aggregate failure.
- Backtest unavailable -> aggregate failure.
- Backtest exception -> aggregate failure.
- Backtest skipped/stubbed -> aggregate failure.
- Paper/simulation unavailable -> aggregate failure.
- Paper/simulation exception -> aggregate failure.
- Stale evidence -> aggregate failure.
- Candidate fingerprint mismatch -> aggregate failure.
- All actual stages pass -> aggregate success.

### CLI tests

- Candidate generation succeeds without live startup.
- `start_live_worker` is never invoked.
- Broker order functions are never invoked.
- Output contains `PROPOSAL_ONLY` or equivalent explicit wording.
- Existing live sentinels are untouched.

### Command registry tests

- `design` level is `A2` proposal.
- All live/order/capital/reassignment flags are false.

## Phase 2 — Remove Workflow-Level Live Authority

1. Remove the weekly `schedule` trigger from `.github/workflows/operator-design.yml`.
2. Remove `auto_ok` or change the input into a non-live compatibility field that cannot activate live behavior.
3. Change workflow language from “라이브 즉시 시작” to “후보 생성 및 검증 보고”.
4. Pass intent via stdin, a temporary file, or encoded payload.
5. Preserve secret validation and SSH transport only if design must still execute on the operator host.
6. Propagate remote exit codes accurately.

Preferred approach:

- Write intent to a temporary file on the runner.
- Pipe the file as stdin to the remote script, or Base64-encode and decode without `eval`.
- Pass only fixed command arguments through the SSH command string.

Rejected approach:

- Escaping a growing list of shell characters while retaining direct interpolation.

## Phase 3 — Make the Shell Helper Proposal-Only

1. Remove `AUTO_OK` behavior and automatic `OK` input.
2. Invoke `auto-invest design` in proposal-only mode.
3. If the CLI lacks an explicit proposal-only switch, change the CLI default so proposal-only is the only supported design behavior.
4. Print generated candidate path and verification state.
5. Do not start, stop, or restart the live worker.
6. Do not edit `.env` live-mode values.

Secret setup behavior must be reviewed. The helper may validate required secrets, but a proposal-only design path should not require broker write authority. Avoid expanding this PR into a full secret architecture change.

## Phase 4 — Fail-Closed Verification

Refactor `VerifyResult` so success has evidence, not booleans inferred from import availability.

Minimum result fields:

- candidate fingerprint
- aggregate status
- static stage result
- backtest stage result
- paper/simulation stage result
- failure reason
- evidence references

Implementation options:

1. Inject callable validators into `verify_rules` for deterministic tests.
2. Reuse existing backtest/paper APIs if their contracts can produce candidate-bound evidence.
3. If actual integration is too large for this PR, return `ok=False` with `WAIT_DYNAMIC_VALIDATION` while retaining candidate generation. Do not fake success.

The safe intermediate state is a proposal that cannot be promoted, not a simulated pass.

## Phase 5 — Remove Direct CLI Live Startup

1. Find every `start_live_worker` call.
2. Remove the call from the `design` command.
3. Decide after call-site inspection whether to:
   - delete `start_live_worker`,
   - move it behind a separate internal module with no CLI/workflow caller, or
   - leave a deprecated function that raises a clear boundary error.
4. Update or remove tests that expected design-driven live startup.
5. Preserve historical audit event parsing, but stop emitting a misleading `RULE_DESIGN_DEPLOYED` event from design completion.

Preferred result: no production caller remains.

## Phase 6 — Align Executable Authority Metadata

Update `src/auto_invest/safety/command_registry.py`:

```text
design.level = PROPOSAL
design.can_place_order = False
design.can_change_live_config = False
design.can_scale_capital = False
design.can_reassign_strategy = False
```

`uses_broker` may remain true only if the command reads account context. The description must state read-only account context and candidate generation.

Add a regression test that command-policy metadata matches observed call paths.

## Phase 7 — Documentation and Handoff

Update only current authoritative documentation needed to avoid the old path being rediscovered.

Required:

- operator-design workflow comments and summary
- relevant operator design guide
- active spec artifacts
- `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md` with actual implementation result
- final root `HANDOFF.md` refresh after merge, following repository practice

Do not rewrite the full repository history in this PR.

## Verification Strategy

### Focused tests

```bash
uv run pytest \
  tests/unit/test_design_verifier.py \
  tests/unit/test_design_deploy.py \
  tests/integration/test_design_cli.py \
  tests/unit/test_safety_command_registry.py
```

Include the actual workflow test path selected during implementation.

### Full repository gates

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
python3 scripts/check_pr_quality_gate.py /tmp/pr-body-111.md
```

### Static boundary proof

```bash
rg -n "AUTO_OK|auto_ok|start_live_worker|echo .*OK|schedule:" \
  .github/workflows/operator-design.yml \
  scripts/operator_design.sh \
  src/auto_invest/design \
  src/auto_invest/cli.py
```

Every remaining hit must be explained as a test, historical note, or deliberately unreachable compatibility guard.

### Diff safety proof

```bash
git diff --name-only origin/main...HEAD
```

The list must not contain:

```text
automation/rebalance-live.request
automation/rebalance-micro-gtaa.request
automation/go-live-canary.request
.specify/memory/constitution.md
.specify/memory/kernel.toml
src/auto_invest/config/caps.py
src/auto_invest/config/whitelist.py
```

## Rollback Strategy

The feature only contracts authority. Rollback must not blindly restore the unsafe path.

If candidate generation breaks:

1. Keep schedule and live startup removed.
2. Revert only the proposal-generation regression.
3. Restore a manual proposal-only command or script.
4. Do not restore automatic `OK` or direct live startup as a rollback shortcut.

If dynamic validation integration is incomplete:

- Return a fail-closed proposal result.
- Record the missing integration as follow-up work.
- Do not mark validation as passed.

## Complexity Tracking

This feature intentionally spans workflow, shell, CLI, verifier, and policy metadata because the unsafe authority chain crosses all five surfaces. It does not include broker retry, ledger atomicity, exposure reservation, or final execution-authority consolidation.

The PR should remain reviewable by organizing commits around:

1. failing boundary tests,
2. workflow and shell contraction,
3. verifier and CLI contraction,
4. policy alignment and docs,
5. verification evidence.
