# Feature Specification: Agent Harness Evaluation

**Feature Branch**: `Codex/world-class-agent-harness`  
**Created**: 2026-06-20  
**Status**: Draft  
**Input**: User description: "목표 스킬 사용해서 세계 최고 수준 하네스 만들어줘"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 하네스 상태를 한 번에 판정한다 (Priority: P1)

운영자와 다음 Codex 세션은 현재 저장소의 에이전트 하네스가 세션 시작, 동시 작업 방어,
문제 정의, 위험 등급, 명세 주도 개발, 품질 관문, 안전 경계, 인계를 모두 갖췄는지 한
명령으로 확인할 수 있다.

**Why this priority**: 세계 최고 수준의 하네스는 규칙을 많이 적는 것이 아니라, 규칙이 실제
작업 표면에서 작동하는지 반복 확인할 수 있어야 한다.

**Independent Test**: `scripts/agent_harness_probe.py --json --strict`가 구조화된 판정과 0
종료 코드를 내면 이 이야기는 독립적으로 검증된다.

**Acceptance Scenarios**:

1. **Given** 저장소에 Codex 훅과 품질 관문 파일이 존재할 때, **When** 하네스 프로브를
   실행하면, **Then** 각 통제 항목의 통과 여부와 근거 파일이 JSON으로 출력된다.
2. **Given** 필수 통제 파일이 빠진 임시 저장소일 때, **When** 하네스 프로브를 strict 모드로
   실행하면, **Then** 실패 항목과 비정상 종료 코드가 나온다.

---

### User Story 2 - 하네스 회귀 과제 묶음을 유지한다 (Priority: P2)

운영자와 다음 세션은 반복되는 실패 유형을 실제 과제 묶음으로 관리하고, 하네스 변경 전후에
같은 과제를 기준으로 판단할 수 있다.

**Why this priority**: 긴 작업에서의 성능은 단일 답변이 아니라 다중 단계 작업 궤적에서
드러난다. 회귀 과제가 없으면 하네스 개선이 감각으로 바뀐다.

**Independent Test**: 평가 과제 파일이 필수 위험 등급과 통제 범위를 모두 덮는지 프로브가
검증하면 독립적으로 확인된다.

**Acceptance Scenarios**:

1. **Given** 평가 과제 파일에 위험 등급 0~4가 모두 들어 있을 때, **When** 프로브를 실행하면,
   **Then** 과제 묶음 검증이 통과한다.
2. **Given** 평가 과제 파일에서 안전 경계 과제가 빠졌을 때, **When** 프로브를 실행하면,
   **Then** 누락된 통제 범위가 실패 근거로 표시된다.

---

### User Story 3 - 등급 2 이상 변경은 하네스 검증 증거를 남긴다 (Priority: P3)

운영자는 운영 체계 변경 PR 본문에서 하네스 프로브 실행 여부와 결과를 확인할 수 있다.

**Why this priority**: 운영 문서·훅·품질 관문을 바꾸는 변경은 다음 세션 행동을 바꾸므로,
본문에 실제 하네스 검증 결과가 남아야 한다.

**Independent Test**: PR 본문 검사기가 등급 2 이상에서 하네스 검증 필드와 strict 실행
증거를 요구하면 독립적으로 검증된다.

**Acceptance Scenarios**:

1. **Given** 등급 2 PR 본문에 하네스 검증 증거가 없을 때, **When** PR 본문 검사기를
   실행하면, **Then** 실패한다.
2. **Given** 등급 1 PR 본문에 하네스 평가가 해당 없음으로 표시될 때, **When** PR 본문
   검사기를 실행하면, **Then** 다른 필수 항목이 채워져 있으면 통과한다.

### Edge Cases

- 평가 프로브는 네트워크, 브로커, 외부 API, 비밀값을 사용하지 않는다.
- 작업 과제 묶음은 실제 주문이나 실거래 전환을 실행하지 않고, 위험 등급 4는 "승인 없이는
  중단해야 하는지"를 평가하는 시나리오로만 표현한다.
- `.specify/feature.json`이 다른 기능을 가리키더라도 프로브는 해당 경로가 존재하는지만
  확인하고, 기능 번호의 최신성은 요구하지 않는다.
- PR 본문 검사기는 본문 문자열만 검사하므로 실제 명령 실행 여부를 완전히 증명하지 않는다.
  대신 등급 2 이상에서는 실행 명령과 결과를 본문에 남기게 해 감사 가능성을 높인다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a local, read-only harness probe that reports pass/fail
  status for core Codex operating controls.
- **FR-002**: System MUST validate that SessionStart runs local concurrency detection before
  git ground-truth context collection.
- **FR-003**: System MUST validate that PR quality-gate automation is wired to the PR body
  checker.
- **FR-004**: System MUST validate an agent evaluation task suite with unique task IDs,
  risk-grade coverage, and required control coverage.
- **FR-005**: System MUST emit both human-readable and JSON output for harness evaluation.
- **FR-006**: System MUST return non-zero in strict mode when any required harness control
  fails.
- **FR-007**: System MUST require PR bodies to include a harness verification section.
- **FR-008**: System MUST require grade 2 or higher PR bodies to mention the strict harness
  probe command and result.
- **FR-009**: System MUST document what the new harness removes, what it replaces, and how to
  revert it for grade 2 operating changes.
- **FR-010**: System MUST avoid changing trading safety boundaries, order limits, secret
  handling, deployment safety, or money-path behavior.

### Key Entities *(include if feature involves data)*

- **Harness Control**: A static operating safeguard checked by the probe, including its
  identifier, severity, status, and evidence.
- **Evaluation Task**: A representative agent-work scenario with an ID, risk grade, prompt,
  expected controls, and success criteria.
- **Harness Report**: The structured result of evaluating controls and the task suite.
- **PR Harness Evidence**: The PR body field that records whether strict harness evaluation was
  run for a change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single strict harness command exits 0 on the implemented repository and exits
  non-zero when a required control is missing in tests.
- **SC-002**: The evaluation task suite contains at least 12 scenarios and covers risk grades
  0, 1, 2, 3, and 4.
- **SC-003**: The evaluation task suite covers at least ten required control categories:
  context truth, concurrency, worktree isolation, SDD, PR quality, validation, safety boundary,
  handoff, rollback, and external-effect containment.
- **SC-004**: The PR body checker rejects a grade 2 body without strict harness evidence.
- **SC-005**: The default full test command and lint command continue to pass.

## Assumptions

- The first version is a static, local harness scorecard and regression task suite, not an
  automated multi-agent benchmark runner.
- The probe should run on developer laptops and CI without network or secrets.
- Existing `AGENTS.md`, `.codex/hooks.json`, `.codex/quality-gate.md`, and PR quality-gate
  workflow remain the primary operating surface.
- Future work can add trajectory capture and replay, but this slice establishes the baseline
  and PR enforcement needed to evolve safely.
