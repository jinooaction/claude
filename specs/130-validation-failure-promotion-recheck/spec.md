# Feature Specification: Validation Failure Promotion Recheck Contract

**Feature Branch**: `codex/validation-failure-promotion-recheck-contract`
**Created**: 2026-08-12
**Status**: Draft
**Input**: User description: "좋아 다음 후보도 목표 스킬로 완수해줘." Current autonomous-work selected `candidate-broad-validation-failure-promotion-recheck-contract`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 억제된 실패 후보를 근거 있게 유지한다 (Priority: P1)

운영자는 learning ledger가 폐기한 후보가 현재도 같은 실패 지문을 갖는지 알고 싶다.

**Why this priority**: 실패 후보를 무작정 다시 열면 같은 검증 실패가 반복되고, 반대로 이유 없이 영구 폐기하면 엣지가 회복되어도 다시 볼 수 없다.

**Independent Test**: 현재 learning ledger, autonomous-promotion, candidate-result 모양의 fixture에서 `candidate-1ed634d8bf6d`와 `candidate-cc96b35062da`가 모두 `SUPPRESSION_ACTIVE`이고, 각 후보의 실패 지문과 유지 조건이 기계 판독 JSON에 남는지 확인한다.

**Acceptance Scenarios**:

1. **Given** learning ledger의 최신 결정이 `rejected`이고 candidate-result가 계속 `fail`임, **When** 재검토 계약을 만들면, **Then** 후보는 `SUPPRESSION_ACTIVE`로 남고 같은 실패 지문에서는 자동 재활성화되지 않는다.
2. **Given** 후보별 package id, package kind, 검증 단계 상태, metric 요약이 있음, **When** 계약을 만들면, **Then** 재검토 기준은 후보와 패키지 단위로 추적 가능해야 한다.

---

### User Story 2 - 새 증거가 생기면 다시 열 조건을 명확히 한다 (Priority: P2)

운영자는 어떤 변화가 있어야 억제된 후보를 다시 검토할 수 있는지 명확히 보고 싶다.

**Why this priority**: 기존 상태는 "재검토 조건이 없다"로 막혀 있어서, 실패 원인이 개선되어도 자동 루프가 후보를 닫은 채 둘 수 있다.

**Independent Test**: candidate-result 상태가 `pass`로 바뀐 fixture에서 해당 후보가 `RECHECK_ALLOWED`가 되고, 다른 후보는 같은 실패 지문이면 계속 억제되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** candidate-result가 더 이상 `fail`/`blocked`가 아님, **When** 계약을 만들면, **Then** 후보는 재검토 허용 상태가 된다.
2. **Given** autonomous-promotion이 더 이상 `DISCARD`가 아니거나 learning ledger 최신 항목에 명시적 재검토 조건이 있음, **When** 계약을 만들면, **Then** 후보는 재검토 후보로 되살릴 수 있는 상태로 기록된다.
3. **Given** 결과·승격·장부 증거가 그대로임, **When** 계약을 만들면, **Then** 후보는 현재 실패 지문을 기준으로 억제 유지 조건을 남긴다.

---

### User Story 3 - 검증 실패 child 묶음을 닫고 반복 선택을 막는다 (Priority: P3)

운영자는 이 마지막 child 후보가 완료되면 autonomous-work가 같은 promotion-recheck 후보를 다시 고르지 않길 원한다.

**Why this priority**: released-work가 마지막 child를 소비하지 못하면 자동 루프는 같은 후보를 반복해서 고르고, 실제 돈 경로 진전과 무관한 재작업이 생긴다.

**Independent Test**: 스펙 산출물에 `completed_candidate_id: candidate-broad-validation-failure-promotion-recheck-contract`가 있고, autonomous-work 테스트가 이 후보 released 뒤 같은 후보를 다시 선택하지 않는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 재검토 계약이 완료됨, **When** released-work가 스펙을 스캔하면, **Then** `candidate-broad-validation-failure-promotion-recheck-contract`가 released로 기록된다.
2. **Given** 검증 실패 child 후보 네 개가 모두 released임, **When** autonomous-work가 같은 검증 실패 evidence를 읽으면, **Then** promotion-recheck 후보를 다시 선택하지 않는다.

### Edge Cases

- learning ledger가 없으면 재검토 조건을 지어내지 않고 입력 누락을 보고한다.
- autonomous-promotion 요약이 없으면 후보의 현재 억제 이유를 확정하지 않는다.
- candidate-result가 없으면 실패 지문을 만들지 않고 증거 대기로 둔다.
- 같은 후보에 여러 ledger 항목이 있으면 최신 항목을 기준으로 판단하되, 과거 재검토 조건도 보조 증거로 보존한다.
- promotion run id가 새로 생겼다는 이유만으로 재검토를 허용하지 않는다. 후보별 실패 지문이나 결정 상태가 바뀌어야 한다.
- deep walk-forward 출력 힌트는 참고 증거일 뿐, current candidate-result fail 상태를 자동 승격으로 뒤집지 않는다.
- 이 기능은 검증 명령, 브로커 호출, 주문, 자본 배분, live 재무장을 실행하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST build a machine-readable promotion recheck contract from learning ledger, autonomous-promotion, and candidate-result evidence.
- **FR-002**: Each candidate rule MUST include candidate id, ledger decision, ledger entry id, promotion stage, result status, package id, package kind, failure fingerprint, decision status, and source refs.
- **FR-003**: System MUST identify the latest learning-ledger decision per candidate and retain historical recheck conditions as context.
- **FR-004**: System MUST keep candidates suppressed when the latest ledger decision is rejected, autonomous-promotion remains discard, and candidate-result remains failed or blocked.
- **FR-005**: System MUST mark recheck allowed when candidate-result is no longer failed/blocked, autonomous-promotion is no longer discard, or the latest ledger entry supplies an explicit recheck condition.
- **FR-006**: System MUST include deterministic future recheck conditions describing which fingerprint changes would reopen a candidate.
- **FR-007**: System MUST derive failure fingerprints from stable candidate-result and promotion evidence, not from wall-clock time.
- **FR-008**: System MUST provide Markdown and JSON outputs.
- **FR-009**: System MUST expose a probe that can print consumed sidecar manifest entries.
- **FR-010**: System MUST mark this work's completed candidate as `candidate-broad-validation-failure-promotion-recheck-contract`.
- **FR-011**: System MUST make autonomous-work not select `candidate-broad-validation-failure-promotion-recheck-contract` again after this candidate is released.
- **FR-012**: System MUST include safety invariants that explicitly say no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no external paid service, and no command execution.
- **FR-013**: System MUST NOT modify constitution, kernel manifest, order routing, capital ladder, live config, broker integration, secrets, whitelist/caps, or deploy guard behavior.

### Key Entities *(include if feature involves data)*

- **Promotion Recheck Contract**: Report-level object that records candidate rules, current suppression decisions, allowed recheck count, missing inputs, safety invariants, and completed candidate id.
- **Candidate Recheck Rule**: One suppressed or recheckable candidate with ledger, promotion, result, fingerprint, and next-action evidence.
- **Recheck Condition**: A deterministic condition such as result status no longer failing, promotion no longer discarding, explicit ledger recheck condition, or changed failure fingerprint.
- **Failure Fingerprint**: A stable digest of package id, package kind, promotion diagnostics, result status, validation layer statuses, metric highlights, and execution digests.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-broad-validation-failure-promotion-recheck-contract`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Focused promotion-recheck tests pass and prove the current two rejected candidates remain `SUPPRESSION_ACTIVE`.
- **SC-002**: Focused tests prove result evidence changing to pass allows recheck for that candidate only.
- **SC-003**: Focused tests prove missing ledger, promotion, or result evidence produces `WAITING_FOR_EVIDENCE` without false recheck.
- **SC-004**: Probe replay against current sidecars produces `CONTRACT_READY`, candidate count 2, suppressed count 2, allowed recheck count 0, and completed candidate id for this work.
- **SC-005**: Autonomous-work tests prove promotion-recheck released does not select the same candidate again.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- Current sidecars still contain two rejected validation candidates: `candidate-1ed634d8bf6d` and `candidate-cc96b35062da`.
- The latest learning ledger rejection for both candidates has no `next_recheck_condition`.
- Current candidate-results still report `fail` across historical, recent OOS, and walk-forward layers.
- This is risk grade 2 because it changes operating contracts and released-work closure, while leaving all money-path and safety perimeter controls unchanged.
