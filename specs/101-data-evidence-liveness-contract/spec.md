# Feature Specification: Data Evidence Liveness Contract

**Feature Branch**: `Codex/101-data-evidence-liveness-contract`
**Created**: 2026-07-07
**Status**: Draft
**Input**: User description: "새 자율 후보 `candidate-data-evidence-liveness-contract`를 목표 스킬로 꼼꼼하게 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 데이터 증거 생존성을 PASS/WAIT/FAIL로 분리한다 (Priority: P1)

운영자는 `pipeline-liveness` 전체 보고서를 직접 해석하지 않고도 데이터 품질 후보에 필요한 `collect-public-data`와 `regime-stratify` 생존 상태가 통과, 관측 대기, 복구 필요 중 어디인지 한 보고서에서 본다.

**Why this priority**: 데이터 증거 frontier의 앞선 두 후보는 입력 품질과 타임라인 커버리지를 닫았지만, 데이터 sidecar가 살아 있는지에 대한 대기·복구 기준은 아직 별도 계약으로 분리되지 않았다.

**Independent Test**: `pipeline-liveness`에 두 데이터 check가 `OK`이면 계약 게이트가 PASS가 되고, `LATE`, `STALE`, `MISSING`, `PENDING` 중 하나이면 `OBSERVATION_WAIT`로 떨어진다.

**Acceptance Scenarios**:

1. **Given** `pipeline-liveness`가 `collect-public-data`와 `regime-stratify` check를 모두 포함하고 두 상태가 `OK`인 상태, **When** 보고서를 생성하면, **Then** data liveness gate는 PASS이고 각 check의 상태, 나이, 한계 시간이 JSON에 남는다.
2. **Given** 두 데이터 check 중 하나가 `STALE` 또는 `MISSING`인 상태, **When** 보고서를 생성하면, **Then** 전체 계약은 `OBSERVATION_WAIT`이고 어떤 check가 대기 원인인지 기록된다.

---

### User Story 2 - pipeline-liveness가 실제 source sidecar와 맞는지 검증한다 (Priority: P2)

운영자는 pipeline-liveness의 요약만 믿지 않고, 실제 `public-data`와 `regime-stratify` LAST_RUN 시각이 그 요약을 감사 가능하게 뒷받침하는지 확인한다.

**Why this priority**: 생존성 감시는 summary가 오래되었거나 다른 source를 가리키면 거짓 안심을 줄 수 있다. 데이터 품질 후보는 check 상태뿐 아니라 check가 참조한 원천 시각도 같이 고정해야 한다.

**Independent Test**: source sidecar timestamp가 없거나 pipeline check timestamp와 불일치하면 계약은 `BLOCKED`가 되고, source timestamp가 pipeline check와 일치하면 source consistency gate가 PASS가 된다.

**Acceptance Scenarios**:

1. **Given** `public-data/LAST_RUN.md`와 `regime-stratify-last-run/LAST_RUN.md`가 각각 pipeline check의 `timestamp_utc` 또는 `last_success_utc`와 같은 시각을 제공하는 상태, **When** 보고서를 생성하면, **Then** source consistency gate는 PASS가 된다.
2. **Given** pipeline check는 `OK`이지만 source sidecar에서 보고서 시각을 파싱할 수 없는 상태, **When** 보고서를 생성하면, **Then** 전체 계약은 `BLOCKED`이고 source 증거가 audit 불가라고 표시된다.

---

### User Story 3 - 완료 후보를 닫고 다음 거시 후보로 전진한다 (Priority: P3)

운영자는 데이터 증거 frontier의 마지막 후보인 `candidate-data-evidence-liveness-contract`가 완료된 뒤 같은 데이터 후보가 반복되지 않고, 다음 거시 영역인 체결 품질 후보로 이동하는 것을 확인한다.

**Why this priority**: 완료 후보가 닫혀도 자율 작업 선택이 전진하지 않으면 다음 세션이 같은 후보를 다시 조사한다. 이 작업의 완료 기준에는 다음 후보 전환 증거가 필요하다.

**Independent Test**: released-work 로컬 재현에 데이터 증거 frontier 세 후보가 모두 released로 들어가면 autonomous-work 선택 결과가 `candidate-execution-quality-frontier-map`으로 전진한다.

**Acceptance Scenarios**:

1. **Given** 이번 스펙의 완료 마커가 scan 대상에 있음, **When** released-work를 생성하면, **Then** `candidate-data-evidence-liveness-contract`가 released로 기록될 수 있다.
2. **Given** released-work가 data-evidence frontier, public-data input-quality, regime timeline coverage, data evidence liveness 후보를 모두 완료 처리한 상태, **When** autonomous-work 보고서를 생성하면, **Then** selected_work는 `candidate-execution-quality-frontier-map`이 된다.

### Edge Cases

- `pipeline-liveness` LAST_RUN이 없거나 결정 JSON을 파싱할 수 없는 경우.
- `pipeline-liveness`에 `collect-public-data` 또는 `regime-stratify` check가 누락된 경우.
- 데이터 check status가 `OK`가 아닌 경우.
- pipeline check가 `OK`인데 `timestamp_utc` 또는 `last_success_utc`가 없는 경우.
- source LAST_RUN은 있지만 보고서 자체 timestamp를 파싱할 수 없는 경우.
- source timestamp와 pipeline timestamp가 서로 다른 경우.
- source sidecar가 `LATE` 또는 `STALE`인 관측 대기 상태에서 source timestamp가 오래되었지만 파싱 가능한 경우.
- released-work가 아직 이번 후보를 released로 보지 못한 상태.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST produce a deterministic data evidence liveness report from existing sidecar snapshots only.
- **FR-002**: System MUST consume `automation/public-data:LAST_RUN.md`, `automation/public-data:summary.json`, `automation/public-data:regime.json`, `automation/public-data:regime_timeline.csv`, `automation/regime-stratify-last-run:LAST_RUN.md`, `automation/pipeline-liveness-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, and `automation/capital-path-readiness-last-run:capital_path_readiness.json`.
- **FR-003**: System MUST expose evidence surfaces with parse status, source ref, and Korean summary for each required input.
- **FR-004**: System MUST evaluate pipeline report parseability, required data check registration, data check liveness status, source timestamp consistency, source freshness, and safety boundary gates.
- **FR-005**: System MUST distinguish `CONTRACT_READY`, `OBSERVATION_WAIT`, and `BLOCKED` overall statuses.
- **FR-006**: System MUST treat missing or malformed `pipeline-liveness` as `BLOCKED` because the liveness contract cannot be audited without the registry report.
- **FR-007**: System MUST treat missing required data checks in `pipeline-liveness` as `BLOCKED`.
- **FR-008**: System MUST treat non-OK data check statuses as `OBSERVATION_WAIT`, not as contract ready.
- **FR-009**: System MUST treat missing source timestamps for `OK` checks, missing `OK` check timestamps, and source/check timestamp mismatches as `BLOCKED`.
- **FR-010**: System MUST include the stable completed candidate marker `candidate-data-evidence-liveness-contract`.
- **FR-011**: System MUST allow autonomous-work to advance to `candidate-execution-quality-frontier-map` after all data evidence frontier candidates are released.
- **FR-012**: System MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.

### Key Entities *(include if feature involves data)*

- **Data Evidence Liveness Report**: Top-level report containing overall status, evidence surfaces, data liveness checks, source observations, validation gates, released-work status, next candidate, and safety boundary.
- **Data Liveness Check**: Parsed `pipeline-liveness` row for `collect-public-data` or `regime-stratify`, including status, critical flag, age hours, max age hours, pipeline timestamp, and wait/block reason.
- **Source Sidecar Observation**: Direct timestamp evidence from the source LAST_RUN file, linked back to the corresponding pipeline check.
- **Quality Gate**: A PASS/WAIT/FAIL decision with Korean explanation and evidence refs.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-data-evidence-liveness-contract`.

completed_candidate_id: candidate-data-evidence-liveness-contract

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With current data sidecar snapshots where both data checks are `OK` and source timestamps match, the report returns `CONTRACT_READY`.
- **SC-002**: The report JSON contains all eight required evidence refs and at least six validation gates.
- **SC-003**: Missing or malformed `pipeline-liveness` produces `BLOCKED`.
- **SC-004**: Missing `collect-public-data` or `regime-stratify` registration in `pipeline-liveness` produces `BLOCKED`.
- **SC-005**: `LATE`, `STALE`, `MISSING`, or `PENDING` data check statuses produce `OBSERVATION_WAIT`.
- **SC-006**: Missing source timestamps for `OK` checks or mismatched source/check timestamps produce `BLOCKED`.
- **SC-007**: autonomous-work local replay advances from completed data evidence liveness to `candidate-execution-quality-frontier-map`.
- **SC-008**: Full `uv run pytest`, `uv run ruff check src tests`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- Existing sidecar branch names remain the source of truth for this contract.
- This contract is read-only and does not refresh public data, regime stratification, pipeline-liveness, or released-work itself.
- `collect-public-data` and `regime-stratify` remain research/reporting sidecars; their staleness is observation wait unless the liveness registry itself becomes unauditable.
- A pipeline check may use either `timestamp_utc` or `last_success_utc` to identify the source observation time.
- Any safety-impact or money-path work remains outside this feature.
