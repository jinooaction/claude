# Feature Specification: Validation Failure Package-Kind Expansion Contract

**Feature Branch**: `codex/validation-failure-package-kind-expansion-contract`
**Created**: 2026-08-12
**Status**: Draft
**Input**: User description: "좋아 그럼 목표 스킬 사용해서 이어서 진행해줘." Current autonomous-work selected `candidate-broad-validation-failure-package-kind-expansion-contract`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 전략 실패와 포트폴리오 실패를 분리한다 (Priority: P1)

운영자는 같은 `execution_failed`로 묶인 두 검증 패키지가 실제로는 전략 후보 실패인지, 포트폴리오 구성 실패인지 바로 구분하고 싶다.

**Why this priority**: 데이터 준비도는 이미 통과했다. 이제 두 실패를 같은 원인으로 다루면 전략군, 포트폴리오 구성, 보유 기간을 넓히는 순서가 다시 흐려진다.

**Independent Test**: 현재 candidate-packages와 candidate-results 모양의 fixture에서 `strategy_backtest`와 `portfolio_backtest`가 서로 다른 package-kind bucket으로 나오고, 각 bucket이 서로 다른 검토 축과 다음 no-live 후보 축을 갖는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `strategy_backtest`와 `portfolio_backtest` 패키지가 모두 `execution_failed`임, **When** 패키지 종류별 계약을 만들면, **Then** 두 패키지는 같은 진단 코드 안에서도 서로 다른 package-kind bucket으로 분리된다.
2. **Given** 한 package kind에 여러 실행 명령과 여러 metric이 있음, **When** 계약을 만들면, **Then** 해당 package kind의 실패 이유와 다음 실험 축은 개별 명령을 잃지 않고 요약된다.

---

### User Story 2 - 다음 no-live 실험 축을 넓게 재정렬한다 (Priority: P2)

운영자는 실패를 단순 재시도하지 않고, 전략군, 포트폴리오 설계, 보유 기간, 산출 증거 기준으로 다음 안전 후보 축을 보고 싶다.

**Why this priority**: 지금 목표는 돈 경로를 억지로 여는 것이 아니라, 엣지 신뢰도를 높일 후보 탐색 폭을 넓히는 것이다.

**Independent Test**: 실패 metric과 stdout/stderr 요약을 넣으면 계약이 `strategy_family`, `portfolio_design`, `holding_period`, `evidence_output` 축을 만들고, 실주문이나 live 재무장을 제안하지 않는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 포트폴리오 패키지가 구간 과반 실패와 벤치마크 열세를 보고함, **When** 계약을 만들면, **Then** 다음 후보 축은 포트폴리오 조합, 자산군 방어성, 비용 견고성 검토로 정리된다.
2. **Given** 전략 패키지가 포트폴리오 walk-forward 실패와 깊은 장기 walk-forward 힌트를 함께 가짐, **When** 계약을 만들면, **Then** 다음 후보 축은 신호군과 보유 기간을 나누고, 장기 힌트를 즉시 승격 증거로 오해하지 않는다.

---

### User Story 3 - 다음 child 후보로 전진할 수 있게 완료 표식을 남긴다 (Priority: P3)

운영자는 이 후보가 완료되면 자동 작업 루프가 마지막 child인 승격 재검토 조건 후보로 넘어가길 원한다.

**Why this priority**: released-work가 package-kind 후보를 닫지 않으면 autonomous-work는 같은 후보를 반복해서 고른다.

**Independent Test**: 스펙 산출물에 `completed_candidate_id: candidate-broad-validation-failure-package-kind-expansion-contract`가 있고, autonomous-work 테스트가 이 후보 released 뒤 promotion recheck 후보로 전진하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 패키지 종류별 계약이 완료됨, **When** released-work가 스펙을 스캔하면, **Then** `candidate-broad-validation-failure-package-kind-expansion-contract`가 released로 기록된다.
2. **Given** package-kind 후보가 released-work에 있음, **When** autonomous-work가 같은 검증 실패 evidence를 읽으면, **Then** 다음 후보는 `candidate-broad-validation-failure-promotion-recheck-contract`다.

### Edge Cases

- candidate-packages가 없으면 계약을 완료로 속이지 않고 입력 누락을 보고한다.
- candidate-results가 없으면 실패 구조를 지어내지 않고 증거 대기로 둔다.
- 알 수 없는 package kind는 실행하지 않고 별도 unknown bucket으로 남긴다.
- 같은 package kind가 여러 패키지를 포함하면 후보와 패키지 참조를 모두 보존한다.
- stdout JSON이 없으면 metric을 지어내지 않고 제한 출력 요약만 남긴다.
- deep walk-forward 출력이 일부 힌트를 주더라도 현재 package fail 상태를 자동 승격으로 뒤집지 않는다.
- 이 기능은 명령을 실행하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST build a machine-readable package-kind expansion contract from candidate package and candidate result evidence.
- **FR-002**: Each package-kind bucket MUST include package kind, candidate ids, package ids, domain keys, failure codes, retryable count, command count, execution evidence count, and source refs.
- **FR-003**: System MUST preserve package-level traceability for every failed package, including candidate id, package id, package kind, diagnostics, next safe actions, and result status.
- **FR-004**: System MUST derive separate review axes for strategy backtest and portfolio backtest failures.
- **FR-005**: System MUST summarize available metric evidence without inventing missing metrics.
- **FR-006**: System MUST produce deterministic next no-live experiment axes for strategy family, portfolio design, holding period, and evidence output.
- **FR-007**: System MUST provide Markdown and JSON outputs.
- **FR-008**: System MUST include safety invariants that explicitly say no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no external paid service, and no command execution.
- **FR-009**: System MUST expose a probe that can print consumed sidecar manifest entries.
- **FR-010**: System MUST mark this work's completed candidate as `candidate-broad-validation-failure-package-kind-expansion-contract`.
- **FR-011**: System MUST make autonomous-work advance to `candidate-broad-validation-failure-promotion-recheck-contract` after this candidate is released.
- **FR-012**: System MUST NOT modify constitution, kernel manifest, order routing, capital ladder, live config, broker integration, secrets, whitelist/caps, or deploy guard behavior.

### Key Entities *(include if feature involves data)*

- **Package-Kind Expansion Contract**: Report-level object that records package-kind buckets, package refs, counts, next no-live axes, missing inputs, safety invariants, and completed candidate id.
- **Package-Kind Bucket**: One package kind such as `strategy_backtest` or `portfolio_backtest`, with its failure metrics, package refs, review axes, and next experiment axes.
- **Package Failure Ref**: One candidate validation package with candidate id, package id, diagnostics, commands, result status, execution count, and safe next actions.
- **Experiment Axis**: One deterministic no-live follow-up dimension such as strategy family, portfolio design, holding period, or evidence output.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-broad-validation-failure-package-kind-expansion-contract`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Focused package-kind tests pass and prove the current two failed packages produce two package-kind buckets.
- **SC-002**: Focused tests prove strategy and portfolio failures get different review axes and next no-live experiment axes.
- **SC-003**: Focused tests prove missing result evidence produces `WAITING_FOR_EVIDENCE` without false completion.
- **SC-004**: Probe replay against current sidecars produces `CONTRACT_READY`, package count 2, bucket count 2, and completed candidate id for this work.
- **SC-005**: Autonomous-work tests prove package-kind released advances to promotion recheck.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- Current sidecars still contain two retryable validation failure packages: `pkg-8aae8cb99874` and `pkg-c9a284fa4235`.
- Data readiness is already complete for the current two packages, so this work treats the remaining failure as package-kind and experiment-axis diagnosis.
- Deep walk-forward output can inform future strategy axes but does not override the current candidate-result fail status.
- This is risk grade 2 because it adds an operating contract and next-candidate closure marker, while leaving all money-path and safety perimeter controls unchanged.
