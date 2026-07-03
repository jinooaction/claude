# Feature Specification: Autonomous Growth Objective Calibration

**Feature Branch**: `Codex/091-autonomous-growth-objective-calibration`  
**Created**: 2026-07-03  
**Status**: Draft  
**Input**: User description: "다음 자율 후보 `candidate-autonomous-growth-objective-calibration`을 목표 스킬과 SDD 기준으로 꼼꼼하게 완수한다. 후보 공간 확장 뒤 성장률, 검증 비용, 안전 경계를 함께 보는 목적 함수와 탐색 예산을 측정 가능한 계약으로 고정한다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 후보 선택 근거를 측정 가능한 목적 함수로 남기기 (Priority: P1)

운영자는 자율 작업 실행 루프가 다음 후보를 고를 때 단순 점수만 보이지 않고, 성장 기여도, 증거 준비도, 검증 비용, 안전 여유, 학습 가치가 어떻게 결합됐는지 같은 입력으로 다시 계산 가능한 형태를 원한다.

**Why this priority**: 스펙 088~090은 닫힌 일반 후보 큐 뒤 거시 후보를 발굴하고 다음 후보로 전진시키는 흐름을 만들었다. 이제 후보 공간이 넓어졌으므로 다음 세션은 "왜 이 후보가 최상위인가"를 다시 조사하지 않고, 목적 함수 구성요소와 총점을 보고 같은 판단을 재현해야 한다.

**Independent Test**: 동일 sidecar 입력으로 자율 작업 실행 보고서를 두 번 만들면 `objective_calibration`의 선택 후보, 구성요소 점수, 총점, 탐색 예산이 동일하다.

**Acceptance Scenarios**:

1. **Given** 실행 가능한 후보가 하나 이상 있음, **When** 자율 작업 실행 루프가 보고서를 발행함, **Then** `objective_calibration.selected_candidate_id`가 `selected_work.candidate_id`와 같고 후보별 구성요소 점수가 포함된다.
2. **Given** 같은 입력 sidecar를 다시 넣음, **When** 보고서를 재생성함, **Then** 목적 함수 보정 블록이 byte-for-byte 동일하다.

---

### User Story 2 - 탐색 예산과 중단 조건을 출력 계약으로 고정하기 (Priority: P2)

운영자는 후보 탐색이 무한히 넓어지지 않도록 한 번에 착수할 후보 수, 순위 후보 수, 검증 시간 예산, 중단 조건이 보고서에 명시되기를 원한다.

**Why this priority**: 자율 성장 루프는 자동 후보 발굴과 자동 실행 후보 선택을 결합한다. 탐색 예산과 중단 조건이 출력에 없으면 다음 세션이 실행 범위와 위험 경계를 매번 새로 해석해야 한다.

**Independent Test**: JSON과 Markdown 보고서에 탐색 예산, 중단 조건, 반복 학습 지표가 모두 표시된다.

**Acceptance Scenarios**:

1. **Given** 안전한 등급 2 후보가 선택됨, **When** 보고서를 읽음, **Then** `max_parallel_candidates=1`과 `max_ranked_candidates=10`이 표시되고 Codex가 한 후보만 끝까지 닫아야 한다는 계약이 보인다.
2. **Given** 안전 표면이 있는 후보가 선택됨, **When** 목적 함수 점수를 확인함, **Then** 안전 여유 구성요소가 낮아지고 중단 조건에 운영자 명시 승인 필요가 표시된다.

---

### User Story 3 - 안전 경계와 완료 장부를 보존하기 (Priority: P3)

운영자는 목적 함수 보정이 자율 실행 판단을 더 투명하게 만들되, 실거래 권한이나 안전 경계를 넓히지 않고 완료 후보 장부가 이 후보를 다시 선택하지 않게 하기를 원한다.

**Why this priority**: 이번 변경은 다음 세션 행동과 자동화 sidecar 출력을 바꾸는 등급 2 운영 체계 변경이다. 돈 경로, 주문, 자본, 허용 종목, 헌법, 커널, 비밀값은 그대로 남아야 한다.

**Independent Test**: released-work가 `candidate-autonomous-growth-objective-calibration` 완료 마커를 읽고, 자율 작업 실행 보고서와 PR 본문이 위험 등급 2 및 안전 경계 불변을 기록한다.

**Acceptance Scenarios**:

1. **Given** 스펙 091 tasks가 완료됨, **When** released-work 장부가 저장소를 스캔함, **Then** `candidate-autonomous-growth-objective-calibration`을 완료 후보로 기록한다.
2. **Given** PR 검증을 수행함, **When** 전체 테스트와 하네스를 확인함, **Then** 주문·브로커·자본·live 전략·허용 종목·비밀값·외부 유료 서비스 변경이 없음을 보고한다.

### Edge Cases

- 실행 가능한 후보가 없고 억제 후보만 있을 때도 선택 후보와 목적 함수 보정 블록이 일관되게 남아야 한다.
- 모든 evidence sidecar가 없으면 liveness 복구 후보가 기존처럼 우선되며, 목적 함수 보정은 그 복구 후보를 설명해야 한다.
- 안전 표면이 있는 후보는 목적 함수 총점이 높아도 자동 착수 후보가 아니라 `OPERATOR_APPROVAL_REQUIRED`로 남아야 한다.
- 목적 함수 보정은 sidecar 출력 계약과 회귀 테스트를 추가할 뿐, ranking 핵심 순서를 은밀히 바꾸지 않는다.
- 탐색 예산은 Codex 작업 범위 예산이며 돈 경로 손실 예산이나 포지션 한도 예산이 아니다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST emit an `objective_calibration` block in the autonomous work execution JSON report.
- **FR-002**: The objective calibration block MUST include `objective_version`, `selected_candidate_id`, `exploration_budget`, `stop_conditions`, `learning_metrics`, and per-candidate score entries.
- **FR-003**: Each score entry MUST include component scores for `growth_leverage`, `evidence_readiness`, `validation_cost_fit`, `safety_margin`, and `learning_value`.
- **FR-004**: The total objective score MUST be deterministic for the same input sidecars and must not depend on wall-clock time beyond the report timestamp.
- **FR-005**: System MUST expose the objective calibration summary in Markdown so operators can inspect it without parsing JSON.
- **FR-006**: System MUST penalize candidates with safety impact or higher risk through the safety margin component, while preserving the existing operator-approval gate.
- **FR-007**: System MUST publish a completed candidate marker for `candidate-autonomous-growth-objective-calibration` only after the Speckit tasks are complete.
- **FR-008**: System MUST preserve the existing safety boundary: no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel change, and no external paid service.
- **FR-009**: System MUST verify focused behavior, probe output, released-work reproduction, full tests, lint, HANDOFF fact check, strict harness, and PR quality gate before merge.

### Key Entities *(include if feature involves data)*

- **ObjectiveCalibration**: The report-level contract that explains candidate scoring, exploration budget, stop conditions, and learning metrics.
- **ObjectiveCandidateScore**: One candidate's deterministic component scores and total objective score.
- **ExplorationBudget**: The Codex work-scope budget for ranked candidates, parallel starts, validation time, and required closure gates.
- **StopCondition**: A condition that prevents autonomous continuation, such as operator approval required, missing evidence, strict harness failure, or full validation failure.
- **Completed Candidate Marker**: Explicit Speckit contract field consumed by released-work to close this candidate after implementation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `build_autonomous_work_execution(...).to_dict()` contains `objective_calibration.selected_candidate_id` matching `selected_work.candidate_id`.
- **SC-002**: A focused unit test proves deterministic objective calibration output for identical inputs.
- **SC-003**: A focused unit test proves safety-impact candidates receive lower safety margin and remain operator-approval gated.
- **SC-004**: `autonomous_work_execution_probe.py --json` emits the objective calibration block and `LAST_RUN.md` includes the Markdown section.
- **SC-005**: `released_work_probe.py --repo-root .` includes `candidate-autonomous-growth-objective-calibration` after tasks are complete.
- **SC-006**: Focused tests, full pytest, ruff, diff check, HANDOFF fact check, strict harness, and PR quality gate pass.
- **SC-007**: Final handoff records that this is a grade 2 operating automation calibration, not a money-path or safety-perimeter change.

## Assumptions

- The latest autonomous-work sidecar already selects `candidate-autonomous-growth-objective-calibration` after spec 090 closure.
- The safest first implementation is to make the purpose function explicit and testable in output, while preserving the existing deterministic candidate ordering.
- Exploration budget values govern Codex work execution discipline, not live trading risk or capital allocation.
