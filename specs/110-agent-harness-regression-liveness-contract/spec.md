# Feature Specification: Agent Harness Regression Liveness Contract

**Feature Branch**: `Codex/110-agent-harness-regression-liveness-contract`
**Created**: 2026-07-10
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-agent-harness-regression-liveness-contract`을 목표 스킬로 꼼꼼하게 수행"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 하네스 회귀 방어가 살아 있는지 한 번에 본다 (Priority: P1)

운영자는 `.codex/harness/evaluation_tasks.toml`, `quality_tasks.toml`, `redteam_tasks.toml`, `scripts/agent_harness_probe.py`가 서로 맞물려 strict 하네스 기준을 계속 만족하는지 하나의 읽기 전용 보고서에서 확인한다.

**Why this priority**: 이 저장소의 운영 품질은 세션 시작 사실 확인, 동시 작업 방어, SDD 포인터, PR 품질 관문, 첫 판단 품질, 레드팀 과제가 함께 살아 있을 때만 유지된다. 하나가 빠져도 다음 세션은 같은 실수를 반복한다.

**Independent Test**: 현재 저장소 fixture를 읽으면 보고서가 세 하네스 묶음과 probe source를 `PASS`로 분류한다.

**Acceptance Scenarios**:

1. **Given** 세 TOML 하네스 묶음이 필수 위험 등급, 통제 범주, 첫 판단 품질 범주, 레드팀 공격 유형을 모두 포함함, **When** 보고서를 생성하면, **Then** suite coverage 게이트는 `PASS`다.
2. **Given** `scripts/agent_harness_probe.py`가 세 묶음 평가 함수를 제공함, **When** 보고서를 생성하면, **Then** probe source 게이트는 `PASS`다.
3. **Given** 필수 파일이 없거나 TOML 구조가 깨짐, **When** 보고서를 생성하면, **Then** 전체 판정은 `BLOCKED`다.

---

### User Story 2 - strict 실행 증거를 WAIT와 FAIL로 분리한다 (Priority: P2)

운영자는 strict 하네스 실행 결과가 아직 제공되지 않은 상태와 실제 실패 상태를 구분한다.

**Why this priority**: strict 하네스는 등급 2 이상 운영 변경의 마지막 안전 확인이다. 실행 증거가 없으면 관찰 대기이고, 실패 출력이 있으면 머지 중단 사유다. 둘을 섞으면 완료 보고가 거짓이 된다.

**Independent Test**: supplied strict output fixture가 `종합 판정: OK`면 `PASS`, 없으면 `WAIT`, `DEGRADED`면 `FAIL`이다.

**Acceptance Scenarios**:

1. **Given** strict output에 `종합 판정: OK (14/14)`가 있음, **When** 보고서를 생성하면, **Then** strict observation 게이트는 `PASS`다.
2. **Given** strict output이 제공되지 않음, **When** 보고서를 생성하면, **Then** 전체 판정은 `OBSERVATION_WAIT`다.
3. **Given** strict output이 `DEGRADED` 또는 점수 미달을 나타냄, **When** 보고서를 생성하면, **Then** 전체 판정은 `BLOCKED`다.

---

### User Story 3 - 완료 뒤 다음 운영 보고 후보로 전진한다 (Priority: P3)

운영자는 `candidate-agent-harness-regression-liveness-contract`가 완료 처리된 뒤 자율 루프가 빈 `OBSERVATION_WAIT`에 머물지 않고 다음 운영 체계 후보로 넘어간다.

**Why this priority**: 구현 전 재현에서 agent harness 후보까지 released로 닫으면 selected_work가 없어지고 전체 상태가 `OBSERVATION_WAIT`가 된다. 그러면 운영자가 다시 "다음엔 뭐 해야 돼?"를 물어야 한다.

**Independent Test**: released-work에 agent harness 후보까지 모두 넣으면 selected_work가 새 `candidate-operator-report-liveness-contract`로 전진한다.

**Acceptance Scenarios**:

1. **Given** released-work가 HANDOFF 사실성, PR/머지 증거, worktree 동시 작업, agent harness 회귀 후보를 모두 released로 기록함, **When** autonomous-work 보고서를 생성하면, **Then** selected_work는 새 운영자 이해 가능 보고 생존성 후보다.
2. **Given** 이번 계약 보고서가 생성됨, **When** 보고서 JSON을 확인하면, **Then** `completed_candidate_id`와 `next_candidate_id`가 명시된다.

### Edge Cases

- 하네스 TOML 파일은 존재하지만 필수 범주가 하나라도 빠지면 `BLOCKED`다.
- strict output은 사람이 읽는 텍스트와 JSON 출력 모두 허용한다.
- released-work JSON이 malformed이면 `BLOCKED`, parseable이지만 완료 후보가 없으면 `WAIT`다.
- 이 보고서는 읽기 전용이며 하네스를 실행하지 않는다. 실행 결과는 supplied observation으로만 소비한다.
- 이 보고서는 브로커 호출, 주문, 자본 배분, 비밀값 접근, 헌법/커널 변경, 외부 유료 서비스를 하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a deterministic agent harness regression liveness report with `overall_status`, `completed_candidate_id`, `next_candidate_id`, evidence surfaces, quality gates, harness suite summary, strict observation summary, released-work summary, and safety invariants.
- **FR-002**: System MUST verify that `scripts/agent_harness_probe.py` exists and exposes evaluation, quality, and redteam suite checks.
- **FR-003**: System MUST evaluate `.codex/harness/evaluation_tasks.toml` through the existing harness evaluator and preserve required risk grades and control categories.
- **FR-004**: System MUST evaluate `.codex/harness/quality_tasks.toml` through the existing harness evaluator and preserve required first-response categories.
- **FR-005**: System MUST evaluate `.codex/harness/redteam_tasks.toml` through the existing harness evaluator and preserve required attack types.
- **FR-006**: System MUST classify supplied strict harness output as PASS, WAIT, or FAIL without executing external services.
- **FR-007**: System MUST classify released-work evidence for `candidate-agent-harness-regression-liveness-contract` as PASS, WAIT, or FAIL.
- **FR-008**: System MUST provide a CLI probe that prints JSON or Markdown and can write `--json-out` and `--summary-out`.
- **FR-009**: System MUST include `.codex/harness/evaluation_tasks.toml`, `.codex/harness/quality_tasks.toml`, `.codex/harness/redteam_tasks.toml`, `scripts/agent_harness_probe.py`, `scripts/check_handoff_facts.py`, `.codex/quality-gate.md`, `.github/pull_request_template.md`, `.github/workflows/pr-quality-gate.yml`, `AGENTS.md`, `HANDOFF.md`, released-work, and autonomous-work as evidence references.
- **FR-010**: System MUST mark this work's completed candidate as `candidate-agent-harness-regression-liveness-contract`.
- **FR-011**: System MUST mark the next autonomous candidate as `candidate-operator-report-liveness-contract`.
- **FR-012**: System MUST prove that released-work completion of this candidate advances autonomous-work to the next operating-system candidate.
- **FR-013**: System MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.

### Key Entities *(include if feature involves data)*

- **Agent Harness Regression Liveness Report**: The read-only contract result for harness source, suite coverage, strict execution observation, completed candidate, next candidate, and safety boundary.
- **Evidence Surface**: A repository file, sidecar reference, or supplied strict output consumed by the report.
- **Quality Gate**: A PASS, WAIT, or FAIL decision that explains whether a required harness protection is alive, pending, or broken.
- **Harness Suite Summary**: Counts, categories, risk grades, and attack types returned by the existing harness evaluator.
- **Strict Observation Summary**: The supplied `agent_harness_probe.py --strict` result normalized into PASS, WAIT, or FAIL.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-agent-harness-regression-liveness-contract`.
- **Next Candidate Marker**: The autonomous-work value `next_candidate_id: candidate-operator-report-liveness-contract`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Unit tests cover all-pass `CONTRACT_READY`, missing strict output `OBSERVATION_WAIT`, degraded strict output `BLOCKED`, malformed released-work `BLOCKED`, broken suite `BLOCKED`, and missing static surface `BLOCKED`.
- **SC-002**: Probe JSON and Markdown contain completed candidate, next candidate, evidence surfaces, quality gates, harness suite summary, strict observation summary, released-work summary, and safety invariants.
- **SC-003**: Autonomous-work focused test proves released `candidate-agent-harness-regression-liveness-contract` advances to `candidate-operator-report-liveness-contract`.
- **SC-004**: Local quickstart replay confirms the probe and autonomous-work transition.
- **SC-005**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- The correct runtime surface is a read-only analytics module plus probe script. It consumes strict harness output but does not run fresh external collection or mutate repository state.
- `scripts/agent_harness_probe.py` remains the source of truth for suite semantics. The new report imports its evaluator functions instead of duplicating TOML validation rules.
- `candidate-operator-report-liveness-contract` is the next operating-system candidate because the rules for operator-readable completion reports exist, but their own candidate-level liveness contract is not yet released.
- The change is risk grade 2 because it changes operating-system observability and autonomous next-work completion, but it does not touch safety boundaries or money paths.

completed_candidate_id: candidate-agent-harness-regression-liveness-contract
next_candidate_id: candidate-operator-report-liveness-contract
