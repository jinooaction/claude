# Feature Specification: Autonomous Sidecar Handoff Liveness Closure

**Feature Branch**: `Codex/086-autonomous-sidecar-liveness`  
**Created**: 2026-07-03  
**Status**: Draft  
**Input**: User description: "다음 자율 후보 `candidate-88a7e7f07361`를 진행한다. 후보명은 자율 루프 sidecar와 handoff 생존성이며, 목표는 이미 충족된 agent_ops 보정이 반복 후보로 남지 않게 완료 판정과 인계를 닫는 것이다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 완료된 agent_ops 후보 반복 발행 차단 (Priority: P1)

운영자는 다음 자율 후보를 시작할 때 이미 구현된 `autonomous-evolution` 생존 감시 보정을 다시 구현하지 않고, 자율 성장 루프가 현재 증거를 읽어 이 후보를 완료 또는 억제 상태로 낮추기를 원한다.

**Why this priority**: 이 후보가 계속 `new`로 남으면 다음 세션이 이미 완료된 `pipeline-liveness` 등록과 HANDOFF 진입점 검증을 반복한다.

**Independent Test**: 최신 `pipeline-liveness` 증거가 `autonomous-evolution=OK`이고 HANDOFF가 세션 시작 진입점과 `/sync` 규칙을 담고 있을 때, 자율 성장 스캔 결과에서 `candidate-88a7e7f07361`가 안전 착수 후보 목록에서 빠지는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `pipeline-liveness`가 `autonomous-evolution` sidecar를 OK로 보고하고 HANDOFF가 단일 진입점을 제공함, **When** 자율 성장 루프가 후보를 생성함, **Then** `candidate-88a7e7f07361`는 새 작업 후보가 아니라 완료된 운영 보정으로 표시된다.
2. **Given** `pipeline-liveness`가 `autonomous-evolution`을 감시하지 않거나 HANDOFF 진입점이 빠짐, **When** 자율 성장 루프가 후보를 생성함, **Then** 동일 후보는 여전히 실행 가능한 agent_ops 후보로 남아 누락을 드러낸다.

---

### User Story 2 - 완료 후보 장부가 후보 소비를 재현 (Priority: P2)

운영자는 이 작업이 merge된 뒤 `released-work` 장부가 명시적 완료 마커를 읽어 `candidate-88a7e7f07361`를 반복 선택에서 제외하기를 원한다.

**Why this priority**: 자율 성장 루프 보정만으로는 이전 sidecar 잔향이 남을 수 있으므로, 완료된 Speckit 산출물에도 후보 소비 근거가 있어야 한다.

**Independent Test**: 모든 작업 체크박스를 완료하고 계약 문서에 `completed_candidate_id`를 남긴 뒤 `released_work_probe.py --repo-root .`를 실행하면 후보가 `released`로 나온다.

**Acceptance Scenarios**:

1. **Given** 스펙 086 작업표가 모두 완료되고 계약 문서에 명시적 완료 후보가 있음, **When** released-work probe가 저장소를 스캔함, **Then** `candidate-88a7e7f07361`가 `released` 목록에 포함된다.

---

### User Story 3 - 안전 경계와 인계 의미가 명확함 (Priority: P3)

운영자는 이 보정이 돈 경로, 주문, live 설정, 비밀값, 커널을 건드리지 않는 읽기 전용 운영 품질 보정임을 다음 세션이 즉시 이해하기를 원한다.

**Why this priority**: agent_ops 보정은 운영 체계에 닿으므로 의미와 비목표를 남겨야 하며, 안전 경계를 흐리면 다음 세션이 불필요한 확인을 반복한다.

**Independent Test**: 스펙, 계약, PR 본문, HANDOFF가 변경 범위와 안전 경계를 같은 방식으로 설명하고, strict harness와 HANDOFF 사실 검증이 통과한다.

**Acceptance Scenarios**:

1. **Given** 변경이 merge 준비됨, **When** 검증과 PR 본문 품질 관문을 확인함, **Then** 등급 2 운영 보정, 검증, 하네스, HANDOFF 의미가 모두 기록되어 있다.

---

### Edge Cases

- `pipeline-liveness`가 오래된 실행이라 `autonomous-evolution` OK를 담지 못하면 후보를 완료로 낮추지 않는다.
- HANDOFF가 읽히지만 세션 시작 진입점이나 `/sync` 규칙을 담지 않으면 후보를 완료로 낮추지 않는다.
- 후보를 완료로 낮춰도 `pipeline-liveness` 자체가 CRITICAL이면 자율 작업 실행 루프의 기존 복구 후보가 우선해야 한다.
- push-to-main workflow가 동시에 실행되어 promotion/factory/result executor가 직전 sidecar를 먼저 읽어도, 현재 체크아웃의 released-work 장부로 완료 후보를 다시 버려야 한다.
- 이 작업은 새 sidecar 브랜치, 새 주문 경로, 새 배포 채널을 만들지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect when the agent_ops candidate's requested conditions are already satisfied: `pipeline-liveness` includes a healthy `autonomous-evolution` check and HANDOFF provides the session entrypoint and `/sync` route.
- **FR-002**: System MUST mark `candidate-88a7e7f07361` as non-actionable when FR-001 is satisfied so it does not appear in `safe_high_leverage_work`.
- **FR-003**: System MUST leave the candidate actionable when either the liveness registration or the HANDOFF entrypoint evidence is missing.
- **FR-004**: System MUST keep all safety boundaries unchanged: no broker API, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, and no external paid service.
- **FR-005**: System MUST publish a Speckit contract with an explicit completed-candidate marker for `candidate-88a7e7f07361` after implementation tasks are complete.
- **FR-006**: System MUST update the active feature pointer for the current worktree so future sessions locate this spec before acting on stale prose.
- **FR-007**: System MUST verify focused unit behavior, released-work reproduction, full tests, lint, HANDOFF fact check, strict harness, and PR quality gate before merge.
- **FR-008**: Promotion, candidate-factory, and candidate-result-executor workflows MUST generate current-checkout released-work evidence before scanning stale automation sidecars, so completed candidates are not re-promoted, re-packaged, or re-executed during simultaneous post-merge workflow runs.

### Key Entities *(include if feature involves data)*

- **Agent Ops Candidate**: The stable autonomous-growth candidate `candidate-88a7e7f07361`, generated from domain `agent_ops`.
- **Liveness Satisfaction Evidence**: The machine-readable or textual proof that `pipeline-liveness` monitors `autonomous-evolution` and reports it as OK.
- **Handoff Entry Evidence**: The HANDOFF text proving that new sessions start from local git truth and `/sync` before trusting stale prose.
- **Released Work Marker**: A Speckit contract marker that lets released-work consume this candidate after tasks are complete.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With satisfied liveness and handoff evidence, `candidate-88a7e7f07361` is not present in `safe_high_leverage_work`.
- **SC-002**: With missing liveness or handoff evidence, `candidate-88a7e7f07361` remains actionable, preserving failure visibility.
- **SC-003**: `released_work_probe.py --repo-root .` includes `candidate-88a7e7f07361` after tasks are checked complete and the explicit contract marker is present.
- **SC-004**: Focused evolution-loop tests, released-work reproduction, full pytest, ruff, HANDOFF fact check, strict harness, and PR quality gate pass.
- **SC-005**: No changed file belongs to broker order submission, capital ladder authority, whitelist/caps, live strategy switching, secrets, constitution, or kernel manifest.
- **SC-006**: With stale promotion/factory/result sidecars from the previous run plus current released-work evidence, `candidate-88a7e7f07361` is `DISCARD` in promotion, absent from factory package outputs, and absent from fresh result-executor outputs.

## Assumptions

- The current `pipeline-liveness` sidecar is the authoritative liveness surface for automation sidecar freshness.
- `HANDOFF.md` remains the single main-branch session entrypoint, while milestone `HANDOFF-NNN` files provide history.
- A completed Speckit contract marker is the correct way to teach `released-work` that an autonomous candidate has been handled.
- This is a grade 2 operating-system change because it affects autonomous candidate selection and handoff behavior, but it does not change the money path.
