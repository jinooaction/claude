# Feature Specification: Broad No-Edge Vol-Target Drawdown

**Feature Branch**: `codex/broad-no-edge-vol-target-drawdown`
**Created**: 2026-08-16
**Status**: Draft
**Input**: User description: "그럼 이어서 진행해" after autonomous-work selected `candidate-broad-no-edge-vol-target-drawdown-experiment`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 변동성 목표 후보 축을 계약으로 고정한다 (Priority: P1)

운영자는 broad no-edge 후보들이 평균 수익률 기준으로 엣지를 확정하지 못할 때, 같은 신호를 더 낮은 변동성과 낙폭 예산으로 다시 검증할 후보 축을 기계 판독 계약으로 받고 싶다.

**Why this priority**: 현재 병목은 주문 권한이 아니라 PSR 신뢰도 미달이다. 새 진입 신호만 반복하지 말고 변동성 목표와 낙폭 제어가 우연 구분 능력을 올리는지 분리해야 한다.

**Independent Test**: 현재 스타일 sidecar 입력으로 계약 빌더를 실행해 `CONTRACT_READY`, `completed_candidate_id`, `drawdown_lanes`를 확인한다.

**Acceptance Scenarios**:

1. **Given** forward 리더보드가 여러 `NO_EDGE` 트랙과 PSR 0.95 미달 값을 포함함, **When** 계약을 생성하면, **Then** `volatility_target_scaling`과 `psr_sensitivity_hurdle` 후보 축이 제안된다.
2. **Given** forward 트랙 또는 레짐 증거가 물질적 낙폭을 포함함, **When** 계약을 생성하면, **Then** `drawdown_deleveraging_overlay` 후보 축이 제안된다.

---

### User Story 2 - live drawdown과 자본 사다리 제외 조건을 같이 본다 (Priority: P2)

운영자는 변동성 목표 후보가 live drawdown, 자본 사다리 rung, 체결 품질 증거를 무시한 낙관적 후보로 남지 않기를 원한다.

**Why this priority**: 현재 money-path는 단0, `PREVIEW_ONLY`, `NO_EDGE_YET`이고 edge-autoarm은 `WAIT_EDGE`다. 변동성 목표 후보는 실거래 지시가 아니라 자본 사다리로 올릴 수 없는 조건까지 명시해야 한다.

**Independent Test**: money-path와 edge-autoarm 입력이 no-live 상태이면 money gate가 `PASS`이고, live 가능 상태로 바뀌면 `OBSERVATION_WAIT`가 된다.

**Acceptance Scenarios**:

1. **Given** money-path가 `PREVIEW_ONLY`이고 edge-autoarm이 `WAIT_EDGE`임, **When** 계약을 생성하면, **Then** money gate가 `PASS`다.
2. **Given** money-path가 실주문 가능 상태로 보임, **When** 계약을 생성하면, **Then** money gate는 `WAIT`이고 실주문은 허용되지 않는다.

---

### User Story 3 - 후보를 완료 처리하고 반복을 막는다 (Priority: P3)

운영자는 이번 후보가 완료되면 released-work 장부에 소비되고, 같은 broad no-edge 후보가 반복 발행되지 않기를 원한다.

**Why this priority**: completed candidate 소비가 없으면 다음 세션이 같은 후보를 다시 구현한다. 완료 마커와 repo-root released-work override가 있어야 자동 루프가 같은 결론을 재현한다.

**Independent Test**: repo-root override로 released-work를 스캔하면 `candidate-broad-no-edge-vol-target-drawdown-experiment`가 released로 잡히고 계약은 `CONTRACT_READY`가 된다.

**Acceptance Scenarios**:

1. **Given** 이번 스펙의 완료 마커가 repo에 있음, **When** released-work가 스캔되면, **Then** 이번 후보가 released로 기록된다.
2. **Given** released-work에 완료 후보가 아직 없음, **When** 계약을 생성하면, **Then** 계약은 `OBSERVATION_WAIT`로 남는다.

### Edge Cases

- 필수 sidecar가 없거나 구조화 JSON을 읽을 수 없으면 `BLOCKED`다.
- forward 낙폭 증거가 물질적이지 않으면 계약은 `OBSERVATION_WAIT`다.
- PSR 미달 값이 없으면 변동성 목표 후보로 완료하지 않는다.
- money-path가 실주문 가능 상태로 보이면 이 no-live 계약은 대기한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a deterministic vol-target drawdown report with schema version, run id, commit, completed candidate id, next candidate id, status, gates, and safety boundary.
- **FR-002**: System MUST consume `rebalance-paper-forward`, `regime-stratify`, `execution-quality`, `money-path`, `edge-autoarm`, `released-work`, and `pipeline-liveness` evidence.
- **FR-003**: System MUST classify candidate lanes for `volatility_target_scaling`, `drawdown_deleveraging_overlay`, `psr_sensitivity_hurdle`, `live_drawdown_exclusion`, and `broad_no_edge_vol_target_context`.
- **FR-004**: System MUST mark required evidence parse failures as `BLOCKED`.
- **FR-005**: System MUST keep live-capable money-path input in `OBSERVATION_WAIT`.
- **FR-006**: System MUST include safety boundary entries forbidding broker API calls, orders, capital allocation, live strategy changes, whitelist/caps changes, secrets, paid external services, and constitution/kernel changes.
- **FR-007**: System MUST provide a probe with manifest, JSON output, Markdown output, deterministic timestamp, run id, commit, and repo-root released-work override.
- **FR-008**: System MUST mark this work's completed candidate as `candidate-broad-no-edge-vol-target-drawdown-experiment`.
- **FR-009**: System MUST expose next candidate `wait-for-fresh-evidence` after this final second-wave broad no-edge candidate is completed.

### Key Entities

- **DrawdownLane**: Candidate lane with status, rule, required inputs, and wait reason.
- **ForwardTrack**: Forward verdict row with PSR, Calmar, drawdown, observation count, and verdict.
- **MoneyState**: money-path-derived live status, rung, demote/halt drawdown budget, and real-order capability.
- **EdgeAutoarmState**: edge-autoarm-derived action, live drawdown, rung, and forward verdict.
- **ValidationGate**: PASS/WAIT/FAIL check over input evidence, no-edge context, PSR sensitivity, drawdown risk, lane coverage, money gate, liveness, and released-work closure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Contract unit tests cover ready, missing evidence, missing drawdown context, missing released-work marker, and live-capable money path cases.
- **SC-002**: Probe integration tests cover manifest and JSON/Markdown output.
- **SC-003**: Local probe with current sidecars and repo-root reports `CONTRACT_READY`.
- **SC-004**: Existing autonomous-work broad no-edge advancement tests continue to pass.
- **SC-005**: Full test and lint gates pass before merge.

## Assumptions

- Existing sidecars are the authority; no fresh broker call or paid market data collection is required.
- Vol-target and drawdown-control candidates are no-live experiment axes, not live portfolio instructions.
- This feature does not alter any capital ladder, live strategy, broker setting, whitelist, cap, secret, constitution, or kernel manifest.

completed_candidate_id: candidate-broad-no-edge-vol-target-drawdown-experiment
