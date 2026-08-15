# Feature Specification: Broad No-Edge Cross-Asset Relative Value

**Feature Branch**: `codex/broad-no-edge-cross-asset-relative-value-isolated`  
**Created**: 2026-08-15  
**Status**: Draft  
**Input**: User description: "이어서 진행해줘" after autonomous-work selected `candidate-broad-no-edge-cross-asset-relative-value-experiment`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 상대가치 후보 축을 계약으로 고정한다 (Priority: P1)

운영자는 기존 forward 트랙이 모두 `NO_EDGE`일 때, 같은 절대 모멘텀 변형을 반복하지 않고 주식·채권·원자재·현금성 자산 간 상대가치 후보 축을 기계 판독 계약으로 받고 싶다.

**Why this priority**: 지금 돈 경로의 병목은 실거래 권한이 아니라 검증된 엣지 부재다. 상대가치 후보 축을 명시해야 다음 no-live 실험이 넓어진다.

**Independent Test**: 현재 스타일 sidecar 입력으로 계약 빌더를 실행해 `CONTRACT_READY`, `completed_candidate_id`, `relative_value_lanes`를 확인한다.

**Acceptance Scenarios**:

1. **Given** forward 리더보드가 여러 트랙의 `NO_EDGE`를 포함함, **When** 계약을 생성하면, **Then** 주식/채권, 채권/원자재, 위험자산/현금 proxy 후보 축이 `PROPOSED` 또는 `WAIT`로 분류된다.
2. **Given** 현금성 proxy 공개 데이터가 준비됨, **When** 계약을 생성하면, **Then** `cash_proxy_hurdle` 후보 축이 제안된다.

---

### User Story 2 - no-live 안전 경계를 유지한다 (Priority: P2)

운영자는 상대가치 후보가 실거래나 live 재무장으로 오해되지 않기를 원한다.

**Why this priority**: money-path는 `PREVIEW_ONLY`/`NO_EDGE_YET`이고 edge-autoarm은 `WAIT_EDGE`/`NO_EDGE`다. 이 경계를 깨면 검증되지 않은 돈 이동이 된다.

**Independent Test**: money-path가 live 가능 상태로 바뀐 입력에서는 계약이 `OBSERVATION_WAIT`로 남는지 확인한다.

**Acceptance Scenarios**:

1. **Given** money-path가 `PREVIEW_ONLY`이고 edge-autoarm이 `WAIT_EDGE`임, **When** 계약을 생성하면, **Then** money gate가 `PASS`다.
2. **Given** money-path가 `ARMED`이고 실주문 가능으로 보임, **When** 계약을 생성하면, **Then** money gate는 `WAIT`이고 실주문은 허용되지 않는다.

---

### User Story 3 - 완료 뒤 다음 broad no-edge 후보로 전진한다 (Priority: P3)

운영자는 이번 후보가 완료된 뒤 같은 후보를 반복하지 않고 다음 2차 후보인 tail-risk convexity로 넘어가기를 원한다.

**Why this priority**: 완료 마커가 없으면 autonomous-work가 같은 후보를 반복 선택할 수 있다.

**Independent Test**: released-work 로컬 재현이 `completed_candidate_id: candidate-broad-no-edge-cross-asset-relative-value-experiment`를 읽고 autonomous-work가 다음 broad no-edge 후보로 전진하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 이번 스펙의 완료 마커가 repo에 있음, **When** released-work가 스캔되면, **Then** 이번 후보가 released로 기록된다.
2. **Given** 이번 후보가 released-work에 있음, **When** autonomous-work 보고서를 생성하면, **Then** `candidate-broad-no-edge-tail-risk-convexity-experiment`가 다음 후보가 된다.

### Edge Cases

- 필수 sidecar가 없거나 구조화 JSON을 읽을 수 없으면 `BLOCKED`다.
- 현금성 proxy 데이터가 부족하면 계약은 실패가 아니라 `OBSERVATION_WAIT`다.
- forward 트랙 수가 부족하거나 모두 `NO_EDGE`가 아니면 상대가치 축은 성급하게 완료되지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a deterministic cross-asset relative-value report with schema version, run id, commit, completed candidate id, next candidate id, status, gates, and safety boundary.
- **FR-002**: System MUST consume `rebalance-paper-forward`, `public-data`, `regime-stratify`, `money-path`, `edge-autoarm`, `released-work`, and `pipeline-liveness` evidence.
- **FR-003**: System MUST classify relative-value lanes for equity/duration, duration/commodity, risk asset/cash proxy, and broad no-edge exclusion.
- **FR-004**: System MUST mark required evidence parse failures as `BLOCKED`.
- **FR-005**: System MUST keep live-capable money-path input in `OBSERVATION_WAIT`.
- **FR-006**: System MUST include safety boundary entries forbidding broker API calls, orders, capital allocation, live strategy changes, whitelist/caps changes, secrets, paid external services, and constitution/kernel changes.
- **FR-007**: System MUST provide a probe with manifest, JSON output, Markdown output, deterministic timestamp, run id, commit, and repo-root released-work override.
- **FR-008**: System MUST mark this work's completed candidate as `candidate-broad-no-edge-cross-asset-relative-value-experiment`.
- **FR-009**: System MUST expose next candidate `candidate-broad-no-edge-tail-risk-convexity-experiment`.

### Key Entities

- **RelativeValueLane**: Candidate lane with asset pair, status, rule, required inputs, and exclusion reason.
- **ForwardTrack**: Existing no-live paper track with verdict, rank, observations, metrics, universe, and inferred asset classes.
- **CashProxySnapshot**: Public-data-derived evidence that Treasury/FRED inputs can support cash hurdle comparison.
- **ValidationGate**: PASS/WAIT/FAIL check over input evidence, no-edge context, lane coverage, cash proxy, money gate, liveness, and released-work closure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Contract unit tests cover ready, missing evidence, missing cash proxy, missing released-work marker, and live-capable money path cases.
- **SC-002**: Probe integration tests cover manifest and JSON/Markdown output.
- **SC-003**: Local probe with current sidecars and repo-root reports `CONTRACT_READY`.
- **SC-004**: Existing autonomous-work broad no-edge advancement tests continue to pass.
- **SC-005**: Full test and lint gates pass before merge.

## Assumptions

- Existing sidecars are the authority; no fresh external market data collection is required.
- Symbol-to-asset-class inference can use the liquid ETF symbols already present in forward paper universes.
- This feature is no-live contract work only and does not create a tradable portfolio by itself.

completed_candidate_id: candidate-broad-no-edge-cross-asset-relative-value-experiment
