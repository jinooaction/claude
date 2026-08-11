# Feature Specification: Validation Failure Command Replay Contract

**Feature Branch**: `codex/validation-failure-command-replay-contract`  
**Created**: 2026-08-11  
**Status**: Draft  
**Input**: User description: "남은 다음 후보도 목표 스킬 활용해서 완수해." Current autonomous-work selected `candidate-broad-validation-failure-command-replay-contract`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 실패 명령을 기계 판독 계약으로 고정한다 (Priority: P1)

운영자는 검증 실패 패키지 2개가 어떤 후보, 어떤 패키지, 어떤 검증 명령 때문에 막혔는지 한 번에 보고 싶다. 명령을 다시 실행하기 전에, 각 명령이 no-live 재현 표면인지와 기존 실행 증거가 있는지를 먼저 알아야 한다.

**Why this priority**: 다음 후보 탐색의 병목은 "실패했다"라는 큰 라벨이 아니라, 실패 명령과 실행 증거가 분리되지 않은 점이다.

**Independent Test**: 현재 candidate-packages와 candidate-results 모양의 fixture에서 명령 4개가 `command_replay_contract` 행으로 나오고, 각 행에 package id, command digest, replay safety, exit evidence status, diagnostic code가 포함되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** retryable `execution_failed` 패키지 2개가 있음, **When** 명령 재현 계약을 만들면, **Then** 각 패키지의 검증 명령이 안정적인 순서의 계약 행으로 나온다.
2. **Given** candidate-results에 execution 기록이 없음, **When** 계약을 만들면, **Then** 종료 코드를 지어내지 않고 `missing_execution_evidence`로 표시한다.

---

### User Story 2 - 안전 재현 범위를 명령별로 판정한다 (Priority: P2)

운영자는 "재현 가능"과 "실행해도 안전"을 구분해 보고 싶다. 명령에 live 주문, 브로커, 자본, secret, whitelist/caps 표면이 있으면 계약은 즉시 막아야 한다.

**Why this priority**: 검토 범위를 넓히더라도 안전 경계가 명령 단위에서 깨지면 안 된다.

**Independent Test**: allowlisted no-live 명령은 `safe_to_replay=true`, live 주문 조각을 포함한 명령은 `safe_to_replay=false`와 사유를 내는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `portfolio-walk-forward`와 `deep_walk_forward_probe.py` 명령, **When** 계약을 만들면, **Then** 명령은 no-live 검증 재현 범위로 표시된다.
2. **Given** `--mode live` 또는 `--confirm-live`가 들어간 명령, **When** 계약을 만들면, **Then** 전체 보고서는 unsafe 상태가 되고 실제 실행은 하지 않는다.

---

### User Story 3 - 다음 child 후보로 전진할 수 있게 완료 표식을 남긴다 (Priority: P3)

운영자는 이 후보가 완료되면 자동 작업 루프가 다음 child인 데이터 준비도 후보로 전진하길 원한다.

**Why this priority**: 이 작업이 released-work에서 닫히지 않으면 자동 루프는 같은 command replay 후보를 반복해서 고른다.

**Independent Test**: 스펙 산출물에 `completed_candidate_id: candidate-broad-validation-failure-command-replay-contract`가 있고, 기존 autonomous-work 테스트가 이 후보 released 뒤 data-readiness 후보로 전진하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** command replay 계약이 완료됨, **When** released-work가 스펙을 스캔하면, **Then** `candidate-broad-validation-failure-command-replay-contract`가 released로 기록된다.
2. **Given** command replay 후보가 released-work에 있음, **When** autonomous-work가 같은 검증 실패 evidence를 읽으면, **Then** 다음 후보는 `candidate-broad-validation-failure-data-readiness-contract`다.

### Edge Cases

- candidate-packages가 없으면 계약을 완료로 속이지 않고 입력 누락을 보고한다.
- candidate-results가 없으면 계약을 완료로 속이지 않고 입력 누락을 보고한다.
- result execution이 비어 있으면 종료 코드와 출력을 만들지 않고 누락 증거로 표시한다.
- result execution이 있으면 command token 기준으로 package command와 연결한다.
- 안전하지 않은 명령 조각이 있으면 no-live 계약도 unsafe로 표시한다.
- 이 기능은 명령을 실행하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST build a machine-readable `command_replay_contract` from candidate package and result evidence.
- **FR-002**: Each contract row MUST include candidate id, package id, package kind, command index, command text, command digest, replay safety, exit evidence status, diagnostic codes, retryable flag, and next action.
- **FR-003**: System MUST mark missing execution evidence explicitly instead of inventing exit codes or output summaries.
- **FR-004**: System MUST join execution evidence to package commands by command tokens when executions are present.
- **FR-005**: System MUST reuse the candidate-result no-live command safety rules for replay-safety classification.
- **FR-006**: System MUST emit an unsafe status if any target command contains live, broker, capital, secret, whitelist/caps, sentinel, SSH, or unsupported command surfaces.
- **FR-007**: System MUST provide Markdown and JSON outputs.
- **FR-008**: System MUST include safety invariants that explicitly say no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no command execution.
- **FR-009**: System MUST expose a probe that can print consumed sidecar manifest entries.
- **FR-010**: System MUST mark this work's completed candidate as `candidate-broad-validation-failure-command-replay-contract`.
- **FR-011**: System MUST NOT modify constitution, kernel manifest, order routing, capital ladder, live config, broker integration, secrets, whitelist/caps, or deploy guard behavior.

### Key Entities *(include if feature involves data)*

- **Command Replay Contract**: Report-level object that records all command rows, counts, missing inputs, safety invariants, and completed candidate id.
- **Command Replay Row**: One validation command with package identity, safety classification, exit/output evidence status, diagnostic codes, and next action.
- **Package Evidence**: Existing candidate implementation package plan with candidate id, package id, package kind, commands, and promotion diagnostics.
- **Result Evidence**: Existing candidate result evidence with status, executions, diagnostics, retryable flag, and next actions.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-broad-validation-failure-command-replay-contract`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Focused command replay tests pass and prove the current two blocked packages produce four safe replay rows.
- **SC-002**: Focused tests prove missing execution evidence is explicit and deterministic.
- **SC-003**: Focused tests prove unsafe live command fragments block the contract without execution.
- **SC-004**: Probe replay against current sidecar JSON produces `CONTRACT_READY`, package count 2, command count 4, and missing execution count 4.
- **SC-005**: Existing autonomous-work tests still prove command replay released advances to data-readiness.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- Current sidecars still contain two retryable blocked packages: `pkg-8aae8cb99874` and `pkg-c9a284fa4235`.
- Current candidate-results may not contain execution rows; this is evidence that must be surfaced, not guessed away.
- This is risk grade 2 because it adds an operating contract and next-candidate closure marker, while leaving all money-path and safety perimeter controls unchanged.
