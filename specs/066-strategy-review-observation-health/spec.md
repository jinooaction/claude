# Feature Specification: Strategy Review Observation Health

**Feature Branch**: `Codex/strategy-review-observation-repair`  
**Created**: 2026-06-27  
**Status**: Draft  
**Input**: User description: "돈 잃을 게 뻔한 micro GTAA 수행을 반복하지 말고, 자율 자동 시스템이 전략을 평가하고 고도화하는 루프를 제대로 돌게 조치해라."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 정상 관측 누적을 장애로 오판하지 않음 (Priority: P1)

운영자는 forward 토너먼트의 모든 후보 판정이 읽히고 아직 모두 최소 관측 전일 때, 새로 추가된 후보가 몇 회 늦게 시작했다는 이유만으로 전략 검토 루프가 `DEGRADED`라고 멈추지 않기를 원한다.

**Why this priority**: 현재 최신 reassign sidecar는 `globalfixed`가 3회 뒤처졌다는 이유로 후보 관측 품질을 `DEGRADED`로 표시한다. 하지만 모든 후보가 최소 20회 관측 전이면 아직 어떤 후보도 비교 가능하지 않으므로, 올바른 상태는 "정상 누적 중, 도전자 없음"이다.

**Independent Test**: 모든 트랙이 알려져 있고 최다 관측 12회, `globalfixed` 9회처럼 전부 최소 관측 전인 입력을 넣으면 `observation_health=OK`이고 `lagging_keys`는 참고 정보로 남는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 모든 후보 판정이 읽혔고 모든 후보가 `PREMATURE`일 때, **When** 한 후보의 관측 수가 최다 후보보다 2회 이상 적으면, **Then** 시스템은 `observation_health=OK`로 유지하고 관측 수 차이를 참고 정보로만 표시해야 한다.
2. **Given** 최신 전략 검토가 아직 최소 관측 전일 때, **When** 자율 재지정 루프가 리더보드를 읽으면, **Then** 재지정 보류 사유는 후보 품질 장애가 아니라 비교 가능한 도전자 부재여야 한다.

---

### User Story 2 - 비교 가능 구간에서 미달 후보는 계속 차단 (Priority: P1)

운영자는 일부 후보가 이미 최소 관측을 채워 비교 가능해졌는데 다른 알려진 후보가 아직 최소 관측 전이면, 그 비교가 불완전하다는 점이 계속 드러나기를 원한다.

**Why this priority**: 관측 품질 판정을 완화하더라도, 실제로 후보군 일부만 비교 가능한 상태에서 전략 교체를 허용하면 window-shopping 위험이 생긴다.

**Independent Test**: incumbent가 20회 이상 관측되어 `COMPARABLE`인데 다른 알려진 후보가 18회라면 `observation_health=DEGRADED`가 유지되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 하나 이상의 후보가 `COMPARABLE`이고 다른 알려진 후보가 최소 관측 미달일 때, **When** 리더보드를 만들면, **Then** 시스템은 `DEGRADED`로 표시하고 재지정 입력 품질 저하를 설명해야 한다.
2. **Given** 라이브 검증 트랙 판정이 없거나 불명일 때, **When** 리더보드를 만들면, **Then** 기존처럼 `BLOCKED`를 유지해야 한다.

---

### User Story 3 - 충분히 관측된 후보의 관측 수 차이는 설명만 함 (Priority: P2)

운영자는 모든 알려진 후보가 최소 관측을 채운 뒤에는 관측 수 차이가 있더라도 후보군 전체가 비교 가능하다는 사실을 유지하길 원한다.

**Why this priority**: 장기 운영에서는 신규 실행 타이밍이나 스케줄 차이로 관측 수가 완전히 같지 않을 수 있다. 최소 관측을 모두 충족하면 차이는 품질 차단이 아니라 포렌식 설명이다.

**Independent Test**: 모든 후보가 20회 이상 관측됐고 한 후보가 최다보다 3회 적어도 `observation_health=OK`이고 `lagging_keys`가 보존되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 모든 알려진 후보가 `COMPARABLE`일 때, **When** 관측 수 차이가 2회 이상 있으면, **Then** 시스템은 `OK`를 유지하고 뒤처진 키를 표시해야 한다.

### Edge Cases

- 어떤 후보 판정도 읽히지 않으면 기존처럼 `BLOCKED`여야 한다.
- 라이브 검증 트랙 판정을 읽지 못하면 기존처럼 `BLOCKED`여야 한다.
- 비-incumbent 후보 판정이 빠진 경우에는 기존처럼 `DEGRADED`여야 한다.
- `lagging_keys`는 상태가 `OK`여도 삭제하지 않는다. 운영자가 관측 누적 차이를 볼 수 있어야 한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST keep `observation_health=OK` when all known tracks are below their minimum observation requirement and all configured track verdicts are known.
- **FR-002**: System MUST retain `lagging_keys` and observation min/max fields even when the health status is `OK`.
- **FR-003**: System MUST mark observation health `DEGRADED` when at least one known track is comparable and at least one known track remains below its minimum observation requirement.
- **FR-004**: System MUST continue to mark observation health `DEGRADED` when any non-incumbent configured track verdict is unknown.
- **FR-005**: System MUST continue to mark observation health `BLOCKED` when no known verdict exists or the incumbent verdict is unknown.
- **FR-006**: System MUST NOT submit broker orders, change arming sentinels, increase capital, widen the symbol whitelist, or change strategy configuration as part of this feature.

### Key Entities

- **TrackResult**: Parsed forward-verdict evidence for one candidate track, including `n_obs`, `min_obs`, verdict, and comparability.
- **TournamentLeaderboard**: Read-only strategy review surface used by autonomous reassignment and operator reporting.
- **Observation Health**: The qualitative state that distinguishes usable tournament input from missing or incomplete candidate evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A current sidecar-like board with all 7 tracks known, max observations 12, and `globalfixed` at 9 reports `observation_health=OK`.
- **SC-002**: A board with at least one comparable track and another known track below minimum observations reports `observation_health=DEGRADED`.
- **SC-003**: Existing unknown and incumbent-missing blocking behavior remains covered by tests.
- **SC-004**: Focused and full `pytest` plus `ruff` gates pass before merge.

## Assumptions

- Minimum observation requirements are the comparability boundary; before any track reaches that boundary, observation-count skew is progress metadata, not a quality failure.
- This feature clarifies the autonomous strategy review loop. It does not assert that any strategy currently has profitable edge.
- Real-money re-arming remains blocked by the existing micro GTAA intent-loss gate unless separate evidence and operator-approved paths justify it.
