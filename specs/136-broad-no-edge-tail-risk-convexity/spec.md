# Feature Specification: Broad No-Edge Tail-Risk Convexity

**Feature Branch**: `codex/broad-no-edge-tail-risk-convexity`  
**Created**: 2026-08-15  
**Status**: Draft  
**Input**: User description: "그럼 목표 스킬로 검증된 신규 투자 엣지를 끝까지 찾아내" after autonomous-work selected `candidate-broad-no-edge-tail-risk-convexity-experiment`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 꼬리위험 방어 후보 축을 계약으로 고정한다 (Priority: P1)

운영자는 기존 broad no-edge 후보들이 평균 수익률 기준으로 엣지를 확정하지 못할 때, 큰 하락장에서 손실을 줄이는 후보 축을 기계 판독 계약으로 받고 싶다.

**Why this priority**: 현재 돈 경로 병목은 주문 권한이 아니라 검증된 엣지 부재다. 평균 수익률 후보만 반복하면 `NO_EDGE_YET`가 반복되므로 하방 방어와 볼록성 후보를 분리해야 한다.

**Independent Test**: 현재 스타일 sidecar 입력으로 계약 빌더를 실행해 `CONTRACT_READY`, `completed_candidate_id`, `convexity_lanes`를 확인한다.

**Acceptance Scenarios**:

1. **Given** forward 리더보드가 여러 `NO_EDGE` 트랙을 포함함, **When** 계약을 생성하면, **Then** broad no-edge tail context가 후보 축으로 제안된다.
2. **Given** regime-stratify가 RISK_OFF/CAUTION/RISK_ON 손실 구간을 포함함, **When** 계약을 생성하면, **Then** risk-off convexity, caution drawdown overlay, shock-day loss cap 후보 축이 제안된다.

---

### User Story 2 - 비용 부담과 체결 품질을 같이 본다 (Priority: P2)

운영자는 볼록성 proxy가 보호 비용과 체결 거부 비용을 무시한 낙관적 후보로 남지 않기를 원한다.

**Why this priority**: 옵션성 방어는 평균적으로 비용을 먹는다. 현재 execution-quality는 `INTENT_LOSS`와 거부 주문 증거를 제공하므로 비용 부담을 후보 계약에 포함해야 한다.

**Independent Test**: execution-quality 입력이 있으면 `cost_drag_exclusion` lane과 `execution-cost-awareness` gate가 PASS인지 확인한다.

**Acceptance Scenarios**:

1. **Given** execution-quality sidecar가 존재함, **When** 계약을 생성하면, **Then** 비용 부담 제외 규칙이 후보 축에 포함된다.
2. **Given** execution-quality가 없거나 파싱되지 않음, **When** 계약을 생성하면, **Then** 계약은 실패하거나 대기 상태가 되어 비용 없는 후보로 완료되지 않는다.

---

### User Story 3 - no-live 안전 경계를 유지하고 다음 후보로 전진한다 (Priority: P3)

운영자는 이 후보가 실주문이나 live 재무장으로 오해되지 않고, 완료 뒤 다음 broad no-edge 후보로 넘어가기를 원한다.

**Why this priority**: money-path는 `PREVIEW_ONLY`/`NO_EDGE_YET`이고 edge-autoarm은 `WAIT_EDGE`다. 이 경계를 깨면 검증되지 않은 돈 이동이 된다.

**Independent Test**: money-path가 live 가능 상태로 바뀐 입력에서는 계약이 `OBSERVATION_WAIT`로 남고, released-work가 완료 마커를 읽으면 후보가 released로 기록된다.

**Acceptance Scenarios**:

1. **Given** money-path가 `PREVIEW_ONLY`이고 edge-autoarm이 `WAIT_EDGE`임, **When** 계약을 생성하면, **Then** money gate가 `PASS`다.
2. **Given** money-path가 실주문 가능 상태로 보임, **When** 계약을 생성하면, **Then** money gate는 `WAIT`이고 실주문은 허용되지 않는다.
3. **Given** 이번 스펙의 완료 마커가 repo에 있음, **When** released-work가 스캔되면, **Then** 이번 후보가 released로 기록된다.

### Edge Cases

- 필수 sidecar가 없거나 구조화 JSON을 읽을 수 없으면 `BLOCKED`다.
- 꼬리위험 레짐 라벨이 없으면 계약은 `OBSERVATION_WAIT`다.
- 실행 품질 증거가 없으면 비용 없는 볼록성 후보로 완료하지 않는다.
- money-path가 실주문 가능 상태로 보이면 이 no-live 계약은 대기한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a deterministic tail-risk convexity report with schema version, run id, commit, completed candidate id, next candidate id, status, gates, and safety boundary.
- **FR-002**: System MUST consume `rebalance-paper-forward`, `regime-stratify`, `execution-quality`, `money-path`, `edge-autoarm`, `released-work`, and `pipeline-liveness` evidence.
- **FR-003**: System MUST classify candidate lanes for risk-off convexity proxy, caution drawdown overlay, shock-day loss cap, cost-drag exclusion, and broad no-edge tail context.
- **FR-004**: System MUST mark required evidence parse failures as `BLOCKED`.
- **FR-005**: System MUST keep live-capable money-path input in `OBSERVATION_WAIT`.
- **FR-006**: System MUST include safety boundary entries forbidding broker API calls, orders, capital allocation, live strategy changes, whitelist/caps changes, secrets, paid external services, and constitution/kernel changes.
- **FR-007**: System MUST provide a probe with manifest, JSON output, Markdown output, deterministic timestamp, run id, commit, and repo-root released-work override.
- **FR-008**: System MUST mark this work's completed candidate as `candidate-broad-no-edge-tail-risk-convexity-experiment`.
- **FR-009**: System MUST expose next candidate `candidate-broad-no-edge-vol-target-drawdown-experiment`.

### Key Entities

- **ConvexityLane**: Candidate lane with status, rule, required inputs, and wait reason.
- **RegimeTailProfile**: Regime-stratify-derived tail labels, worst day, and drawdown evidence.
- **ExecutionCostProfile**: Execution-quality-derived cost and broker readiness evidence.
- **ValidationGate**: PASS/WAIT/FAIL check over input evidence, no-edge context, tail regimes, lane coverage, execution costs, money gate, liveness, and released-work closure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Contract unit tests cover ready, missing evidence, missing tail regime, missing released-work marker, and live-capable money path cases.
- **SC-002**: Probe integration tests cover manifest and JSON/Markdown output.
- **SC-003**: Local probe with current sidecars and repo-root reports `CONTRACT_READY`.
- **SC-004**: Existing autonomous-work broad no-edge advancement tests continue to pass.
- **SC-005**: Full test and lint gates pass before merge.

## Assumptions

- Existing sidecars are the authority; no fresh broker call or paid market data collection is required.
- Tail-risk candidates are no-live experiment axes, not live portfolio instructions.
- This feature does not create a tradable options strategy; it creates the evidence contract needed before such a strategy can be validated.

completed_candidate_id: candidate-broad-no-edge-tail-risk-convexity-experiment
