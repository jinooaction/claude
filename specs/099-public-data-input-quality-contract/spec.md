# Feature Specification: Public Data Input Quality Contract

**Feature Branch**: `Codex/099-public-data-input-quality-contract`
**Created**: 2026-07-06
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-public-data-input-quality-contract`를 목표 스킬로 꼼꼼하게 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 공개 데이터 입력 품질을 한눈에 판정한다 (Priority: P1)

운영자는 public-data, regime summary, regime timeline, regime-stratify, pipeline-liveness를 따로 조합하지 않고도 공개 데이터 입력이 다음 투자 후보의 연구 입력으로 쓸 수 있는지 기계 판독 보고서로 본다.

**Why this priority**: 스펙 098은 공개 데이터 입력 품질 후보를 열었지만, 아직 실제 public-data 산출물의 발행 수, 교차검증, 레짐 지표, 타임라인 커버리지, 생존성 상태를 하나의 계약으로 닫지 않았다.

**Independent Test**: 최신 sidecar 스냅샷을 입력으로 보고서를 만들면 공개 데이터 입력 품질 판정, 각 입력 증거의 파싱 상태, 검증 게이트가 JSON과 Markdown에 함께 나온다.

**Acceptance Scenarios**:

1. **Given** public-data summary가 전체 OK이고 모든 발행 항목이 존재하며 교차검증이 통과한 상태, **When** 입력 품질 보고서를 생성하면, **Then** 보고서는 발행·교차검증 게이트를 PASS로 표시한다.
2. **Given** regime summary와 regime timeline이 존재하고 최소 커버리지 조건을 만족하는 상태, **When** 보고서를 생성하면, **Then** 보고서는 레짐 입력 커버리지를 PASS 또는 관측 대기 상태로 분리해 표시한다.

---

### User Story 2 - 입력 품질 부족을 WAIT/BLOCKED로 분리한다 (Priority: P2)

운영자는 공개 데이터가 완전히 깨졌는지, 아니면 일부 관측·신선도·교차검증만 기다리면 되는지 구분할 수 있다.

**Why this priority**: 데이터 품질 문제를 모두 같은 장애로 보면 다음 투자 후보가 막힌 이유를 재현하기 어렵고, 정상적인 연구 입력 대기를 장애로 오판할 수 있다.

**Independent Test**: summary 누락, 교차검증 실패, timeline 부족, regime-stratify 누락, pipeline-liveness 저하 입력을 각각 넣어도 보고서가 주문·자본 변경 없이 PASS/WAIT/FAIL을 분리한다.

**Acceptance Scenarios**:

1. **Given** public-data summary가 누락되거나 malformed인 상태, **When** 보고서를 생성하면, **Then** overall status는 BLOCKED이고 어떤 입력이 깨졌는지 evidence surface에 남는다.
2. **Given** 핵심 public-data는 정상이지만 pipeline-liveness가 collect-public-data 또는 regime-stratify를 지연으로 표시한 상태, **When** 보고서를 생성하면, **Then** overall status는 WAIT이고 생존성 게이트만 대기로 남는다.

---

### User Story 3 - 완료 후보를 닫고 다음 데이터 후보로 전진한다 (Priority: P3)

운영자는 `candidate-public-data-input-quality-contract`가 완료된 뒤 같은 후보를 반복해서 받지 않고, 데이터 증거 frontier의 다음 미완료 후보로 이동하는 것을 확인한다.

**Why this priority**: 후보 계약을 만들고도 released-work 완료 마커가 없으면 자율 작업 루프가 같은 후보를 반복 선택한다.

**Independent Test**: released-work 로컬 재현에서 `candidate-public-data-input-quality-contract`가 released로 잡히고, autonomous-work 로컬 재현에서 다음 데이터 증거 후보로 전진하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 이번 스펙의 완료 마커가 scan 대상에 있음, **When** released-work를 생성하면, **Then** `candidate-public-data-input-quality-contract`가 released로 기록된다.
2. **Given** released-work가 이번 후보를 완료 처리한 상태, **When** autonomous-work 보고서를 생성하면, **Then** selected_work는 다음 unreleased 데이터 증거 후보로 전진한다.

### Edge Cases

- public-data `LAST_RUN.md`는 존재하지만 `summary.json`이 없거나 malformed인 경우.
- summary의 `overall_ok`는 true지만 일부 item의 `ok`가 false이거나 published 파일 수가 total보다 작은 경우.
- 교차검증 overlap이 부족하거나 status가 PASS가 아닌 경우.
- regime summary의 전체 지표 수가 부족하거나 timeline 행이 거의 없는 경우.
- regime-stratify는 존재하지만 `total_return_days`가 최소 관측 기준보다 낮은 경우.
- pipeline-liveness 전체는 OK지만 collect-public-data 또는 regime-stratify 개별 check가 WAIT/FAIL인 경우.
- capital-path-readiness 또는 money-path는 BLOCKED여도 이번 보고서는 돈 경로 변경 없이 참고 상태만 남긴다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST produce a deterministic public-data input-quality report from existing sidecar snapshots.
- **FR-002**: System MUST consume `automation/public-data:LAST_RUN.md`, `automation/public-data:summary.json`, `automation/public-data:regime.json`, `automation/public-data:regime_timeline.csv`, `automation/regime-stratify-last-run:LAST_RUN.md`, `automation/pipeline-liveness-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, and `automation/capital-path-readiness-last-run:capital_path_readiness.json`.
- **FR-003**: System MUST expose evidence surfaces with parse status, source ref, and Korean summary for each required input.
- **FR-004**: System MUST evaluate at least four gates: public-data publication completeness, cross-check quality, regime timeline coverage, and sidecar liveness.
- **FR-005**: System MUST distinguish `CONTRACT_READY`, `OBSERVATION_WAIT`, and `BLOCKED` overall statuses.
- **FR-006**: System MUST include the stable completed candidate marker `candidate-public-data-input-quality-contract`.
- **FR-007**: System MUST allow released-work to mark `candidate-public-data-input-quality-contract` as released when this spec is complete.
- **FR-008**: System MUST allow autonomous-work to advance to the next unreleased data evidence candidate after this candidate is released.
- **FR-009**: System MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.

### Key Entities *(include if feature involves data)*

- **Public Data Input Quality Report**: Top-level report containing overall status, required inputs, evidence surfaces, quality gates, data summaries, liveness status, released-work status, and safety boundary.
- **Evidence Surface**: One sidecar input with source ref, parse status, presence, and human-readable summary.
- **Quality Gate**: A PASS/WAIT/FAIL decision that explains whether an input quality condition is satisfied.
- **Public Data Summary**: Publication and cross-check facts derived from public-data summary.
- **Regime Coverage Summary**: Regime indicator and timeline coverage facts derived from regime and regime timeline inputs.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-public-data-input-quality-contract`.

completed_candidate_id: candidate-public-data-input-quality-contract

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With current sidecar snapshots, the report returns `CONTRACT_READY` or `OBSERVATION_WAIT` without any broker, order, capital, live-strategy, or external collection side effects.
- **SC-002**: The report JSON contains all required evidence refs and at least four validation gates.
- **SC-003**: Missing or malformed public-data summary produces `BLOCKED` with a failing evidence surface.
- **SC-004**: Liveness degradation for collect-public-data or regime-stratify produces `OBSERVATION_WAIT` unless another gate is blocking.
- **SC-005**: released-work local replay records `candidate-public-data-input-quality-contract` as released after this spec is complete.
- **SC-006**: autonomous-work local replay advances from `candidate-public-data-input-quality-contract` to the next unreleased data evidence candidate.
- **SC-007**: Full `uv run pytest`, `uv run ruff check src tests`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- Existing sidecar branch names remain the source of truth for this contract.
- The contract is a read-only report and does not refresh public data itself.
- Minimum useful regime-stratify evidence is at least 20 joined return days, matching the existing regime observation convention.
- Public-data publication completeness means `published == total_items` and all items have `ok=true`.
- Any safety-impact or money-path work remains outside this feature.
