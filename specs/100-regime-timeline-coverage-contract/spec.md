# Feature Specification: Regime Timeline Coverage Contract

**Feature Branch**: `Codex/100-regime-timeline-coverage-contract`
**Created**: 2026-07-06
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-regime-timeline-coverage-contract`를 목표 스킬로 꼼꼼하게 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 레짐 타임라인 라벨 커버리지를 판정한다 (Priority: P1)

운영자는 `regime_timeline.csv`를 직접 열어 행 수, 날짜 순서, 빈 라벨, 라벨 분포를 세지 않고도 레짐 타임라인이 downstream 레짐 층화 입력으로 쓸 수 있는지 기계 판독 보고서로 본다.

**Why this priority**: 스펙 099는 공개 데이터 입력 품질을 닫았지만, 레짐 타임라인 자체의 라벨 커버리지와 join-ready 상태는 아직 별도 계약으로 닫지 않았다.

**Independent Test**: 정상적인 timeline CSV를 입력하면 보고서가 행 수, 첫/마지막 날짜, 라벨별 행 수, 누락·중복·날짜 순서 문제를 JSON과 Markdown에 함께 표시한다.

**Acceptance Scenarios**:

1. **Given** `regime_timeline.csv`가 `date,label` 열을 포함하고 날짜가 오름차순이며 라벨이 비어 있지 않은 상태, **When** 보고서를 생성하면, **Then** timeline shape와 label coverage 게이트가 PASS 또는 관측 대기 상태로 분리된다.
2. **Given** timeline에 `RISK_ON`, `CAUTION`, `RISK_OFF` 라벨이 모두 존재하는 상태, **When** 보고서를 생성하면, **Then** 각 라벨의 행 수와 전체 행 수가 재현 가능한 JSON 필드에 남는다.

---

### User Story 2 - 레짐별 관측 수 부족을 정직하게 대기 상태로 분리한다 (Priority: P2)

운영자는 `regime-stratify` 결과가 총 관측 수는 충분하지만 일부 레짐의 관측 수가 아직 통계적으로 부족한 상태인지 구분할 수 있다.

**Why this priority**: 최신 sidecar는 총 751 return day를 갖지만 `RISK_OFF`는 7일뿐이다. 이것을 장애로 과장하거나 완전 준비로 과장하면 다음 투자 후보가 잘못된 자신감으로 진행된다.

**Independent Test**: `regime-stratify` 결과에 `RISK_OFF: 7`과 같은 sparse label을 넣으면 전체 상태는 `OBSERVATION_WAIT`가 되고, malformed JSON이나 total/count 불일치는 `BLOCKED`가 된다.

**Acceptance Scenarios**:

1. **Given** stratified 결과의 모든 전략 섹션이 forward join 규칙과 총 return day를 포함하는 상태, **When** 보고서를 생성하면, **Then** section별 total, label count, sparse label 목록이 기록된다.
2. **Given** 어떤 canonical label의 joined return day가 20일 미만인 상태, **When** 보고서를 생성하면, **Then** overall status는 `OBSERVATION_WAIT`이고 어떤 라벨이 부족한지 표시된다.

---

### User Story 3 - 전망적 조인 품질을 계약으로 고정한다 (Priority: P3)

운영자는 레짐 라벨과 성과 수익률이 d일 라벨 대 d+1 거래일 수익률로 결합됐는지, 그리고 조인 결과가 라벨별 합계와 전체 return day를 일관되게 설명하는지 확인한다.

**Why this priority**: 레짐 성과 분석은 미래 누출이 있으면 투자 판단의 근거가 무너진다. join_rule과 label count 합계는 현재 sidecar에서 가장 싸고 재현 가능한 누출 방지 증거다.

**Independent Test**: join_rule이 `d+1` 또는 미래 누출 차단 문구를 잃거나 label count 합계가 total_return_days와 다르면 forward join 게이트가 FAIL로 바뀐다.

**Acceptance Scenarios**:

1. **Given** `regime-stratify` JSON의 `join_rule`이 전망적 d+1 결합을 명시하는 상태, **When** 보고서를 생성하면, **Then** forward join gate는 PASS가 된다.
2. **Given** `by_label` 합계가 `total_return_days`와 맞지 않는 상태, **When** 보고서를 생성하면, **Then** overall status는 `BLOCKED`이고 mismatch가 section summary에 남는다.

---

### User Story 4 - 완료 후보를 닫고 다음 데이터 증거 후보로 전진한다 (Priority: P4)

운영자는 `candidate-regime-timeline-coverage-contract`가 완료된 뒤 같은 후보를 반복해서 받지 않고, 데이터 증거 frontier의 다음 미완료 후보로 이동하는 것을 확인한다.

**Why this priority**: 완료 마커와 전진 테스트가 없으면 자율 작업 루프가 이번 후보를 다음 세션에서 다시 발굴할 수 있다.

**Independent Test**: released-work 로컬 재현에서 `candidate-regime-timeline-coverage-contract`가 released로 잡히고, autonomous-work 로컬 재현에서 `candidate-data-evidence-liveness-contract`로 전진하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 이번 스펙의 완료 마커가 scan 대상에 있음, **When** released-work를 생성하면, **Then** `candidate-regime-timeline-coverage-contract`가 released로 기록된다.
2. **Given** released-work가 public-data input-quality와 regime timeline coverage 후보를 모두 완료 처리한 상태, **When** autonomous-work 보고서를 생성하면, **Then** selected_work는 `candidate-data-evidence-liveness-contract`로 전진한다.

### Edge Cases

- `regime_timeline.csv`가 없거나 `date,label` 열이 없는 경우.
- timeline 날짜가 중복되거나 오름차순이 아닌 경우.
- timeline 라벨이 비어 있거나 canonical label 중 하나가 전혀 없는 경우.
- `regime-stratify` LAST_RUN에 여러 전략 섹션이 있고 각 섹션의 JSON을 모두 파싱해야 하는 경우.
- stratified JSON의 `join_rule`이 비어 있거나 d+1 전망적 결합을 명시하지 않는 경우.
- label별 `n_days` 합계가 `total_return_days`와 불일치하는 경우.
- 총 return day는 충분하지만 특정 라벨 관측 수가 20일 미만인 경우.
- pipeline-liveness가 collect-public-data 또는 regime-stratify를 stale/wait로 표시하는 경우.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST produce a deterministic regime timeline coverage report from existing sidecar snapshots.
- **FR-002**: System MUST consume `automation/public-data:regime_timeline.csv`, `automation/regime-stratify-last-run:LAST_RUN.md`, `automation/pipeline-liveness-last-run:LAST_RUN.md`, and `automation/released-work-last-run:released_work.json`.
- **FR-003**: System MUST expose evidence surfaces with parse status, source ref, and Korean summary for each required input.
- **FR-004**: System MUST evaluate timeline shape, timeline label coverage, stratified observation floor, forward join quality, and data sidecar liveness gates.
- **FR-005**: System MUST distinguish `CONTRACT_READY`, `OBSERVATION_WAIT`, and `BLOCKED` overall statuses.
- **FR-006**: System MUST parse every stratified JSON block in the regime-stratify markdown instead of only the last block.
- **FR-007**: System MUST treat canonical label counts below 20 joined return days as `OBSERVATION_WAIT`, not as `CONTRACT_READY`.
- **FR-008**: System MUST treat malformed timeline CSV, missing stratified JSON, missing forward join rule, and total/count mismatch as `BLOCKED`.
- **FR-009**: System MUST include the stable completed candidate marker `candidate-regime-timeline-coverage-contract`.
- **FR-010**: System MUST allow autonomous-work to advance to `candidate-data-evidence-liveness-contract` after this candidate is released.
- **FR-011**: System MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.

### Key Entities *(include if feature involves data)*

- **Regime Timeline Coverage Report**: Top-level report containing overall status, evidence surfaces, timeline summary, stratified section summaries, validation gates, released-work status, next candidate, and safety boundary.
- **Timeline Summary**: Parsed facts from `regime_timeline.csv`, including row count, date range, label counts, missing labels, duplicate dates, invalid dates, and ordering health.
- **Stratified Section Summary**: One parsed `regime-stratify` strategy section with section title, total return days, join rule, by-label counts, sparse labels, missing labels, unknown labels, and count consistency.
- **Quality Gate**: A PASS/WAIT/FAIL decision with Korean explanation and evidence refs.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-regime-timeline-coverage-contract`.

completed_candidate_id: candidate-regime-timeline-coverage-contract

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With current sidecar snapshots, the report returns `OBSERVATION_WAIT` because `RISK_OFF` joined return days are below 20, while timeline shape and forward join quality pass.
- **SC-002**: The report JSON contains all required evidence refs and at least five validation gates.
- **SC-003**: Missing or malformed timeline CSV produces `BLOCKED` with a failing evidence surface or timeline gate.
- **SC-004**: Missing forward join rule or label count mismatch in any stratified section produces `BLOCKED`.
- **SC-005**: Liveness degradation for collect-public-data or regime-stratify produces `OBSERVATION_WAIT` unless another gate is blocking.
- **SC-006**: released-work local replay records `candidate-regime-timeline-coverage-contract` as released after tasks are complete.
- **SC-007**: autonomous-work local replay advances from `candidate-regime-timeline-coverage-contract` to `candidate-data-evidence-liveness-contract`.
- **SC-008**: Full `uv run pytest`, `uv run ruff check src tests`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- Existing sidecar branch names remain the source of truth for this contract.
- The contract is a read-only report and does not refresh public data or regime stratification itself.
- Canonical regime labels for useful coverage are `RISK_ON`, `CAUTION`, and `RISK_OFF`; `INSUFFICIENT` is allowed but does not replace one of the canonical labels.
- Minimum useful per-label joined return observations remain 20, matching the existing `regime_stratified.MIN_OBS_FOR_RATIOS` convention.
- Sparse but parseable rare-regime samples are observation wait, while malformed joins are blocking.
- Any safety-impact or money-path work remains outside this feature.
