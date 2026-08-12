# Feature Specification: Validation Failure Data Readiness Contract

**Feature Branch**: `codex/validation-failure-data-readiness-contract`  
**Created**: 2026-08-12  
**Status**: Draft  
**Input**: User description: "좋다 다음 작업도 이어서 목표 스킬로 진행해줘." Current autonomous-work selected `candidate-broad-validation-failure-data-readiness-contract`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 검증 실패가 데이터 문제인지 분리한다 (Priority: P1)

운영자는 막힌 검증 패키지가 "데이터가 없어서 실패"했는지, 아니면 "데이터는 준비됐지만 엣지가 약해서 실패"했는지 바로 보고 싶다.

**Why this priority**: 돈 경로를 빠르게 개선하려면 같은 실패 명령을 반복 실행하기보다, 데이터 준비 문제와 전략 엣지 문제를 먼저 나눠야 한다.

**Independent Test**: 현재 candidate-packages와 candidate-results 모양의 fixture에서 패키지 2개가 데이터 준비도 행으로 나오고, 각 행이 `PASS_DATA_READY`, `WAITING_FOR_EVIDENCE`, `BLOCKED_DATA_INPUT` 중 하나로 판정되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** portfolio TOML, history root, 실행 stdout JSON이 모두 맞음, **When** 데이터 준비도 계약을 만들면, **Then** 해당 검증 패키지는 `PASS_DATA_READY`로 표시된다.
2. **Given** history root가 manifest와 다르거나 portfolio TOML이 없음, **When** 계약을 만들면, **Then** 해당 검증 패키지는 `BLOCKED_DATA_INPUT`과 원인 코드를 낸다.

---

### User Story 2 - 관측 기간과 sidecar 한계를 함께 남긴다 (Priority: P2)

운영자는 각 패키지가 어떤 관측 기간을 보고 실패했는지, public-data와 regime-stratify 증거가 있었는지 함께 보고 싶다.

**Why this priority**: "검증 실패"라는 라벨만으로는 데이터 신선도, 평가 기간, 레짐 근거가 충분했는지 재현할 수 없다.

**Independent Test**: stdout JSON의 `data_newest_session`, `data_age_days`, `data_staleness`, `eval_window`, `n_segments`가 계약 JSON에 안정적으로 기록되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** portfolio-walk-forward 실행 결과가 있음, **When** 계약을 만들면, **Then** 최신 관측일, 데이터 나이, 평가 시작/종료일, 구간 수가 기록된다.
2. **Given** public-data가 일부 연구 항목 실패를 보고하지만 패키지 직접 입력은 준비됨, **When** 계약을 만들면, **Then** 패키지를 데이터 결측으로 막지 않고 public-data 한계를 별도 관찰값으로 기록한다.

---

### User Story 3 - 다음 child 후보로 전진할 수 있게 완료 표식을 남긴다 (Priority: P3)

운영자는 이 후보가 완료되면 자동 작업 루프가 다음 child인 package-kind 확장 후보로 전진하길 원한다.

**Why this priority**: released-work가 이 후보를 닫지 않으면 autonomous-work는 같은 데이터 준비도 후보를 반복해서 고른다.

**Independent Test**: 스펙 산출물에 `completed_candidate_id: candidate-broad-validation-failure-data-readiness-contract`가 있고, autonomous-work 테스트가 이 후보 released 뒤 package-kind 후보로 전진하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 데이터 준비도 계약이 완료됨, **When** released-work가 스펙을 스캔하면, **Then** `candidate-broad-validation-failure-data-readiness-contract`가 released로 기록된다.
2. **Given** 데이터 준비도 후보가 released-work에 있음, **When** autonomous-work가 같은 검증 실패 evidence를 읽으면, **Then** 다음 후보는 `candidate-broad-validation-failure-package-kind-expansion-contract`다.

### Edge Cases

- candidate-packages가 없으면 계약을 완료로 속이지 않고 입력 누락을 보고한다.
- candidate-results가 없으면 실행 증거 대기 상태로 둔다.
- portfolio 명령에 `--portfolio` 또는 `--history-root`가 없으면 데이터 표면을 만들지 않고 원인을 기록한다.
- history root가 candidate history support manifest와 다르면 데이터 입력 문제로 막는다.
- portfolio TOML이 저장소에 없으면 데이터 입력 문제로 막는다.
- stdout JSON이 없으면 관측 기간을 지어내지 않고 증거 대기 상태로 둔다.
- public-data의 연구용 일부 항목 실패는 패키지 직접 입력 실패와 구분한다.
- candidate-results가 `fail`로 바뀌고 retryable 정보가 candidate-packages의 `promotion_patch` 아래에만 있어도 broad validation failure child 순서는 끊기지 않는다.
- 이 기능은 명령을 실행하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST build a machine-readable `data_readiness_contract` from candidate package, result, history manifest, public-data, and regime-stratify evidence.
- **FR-002**: Each package row MUST include candidate id, package id, package kind, portfolio paths, history roots, manifest match status, portfolio TOML existence, execution evidence count, observation window, and readiness status.
- **FR-003**: System MUST classify each package as `PASS_DATA_READY`, `WAITING_FOR_EVIDENCE`, or `BLOCKED_DATA_INPUT`.
- **FR-004**: System MUST record data missing or blocking causes as stable machine-readable codes.
- **FR-005**: System MUST parse portfolio-walk-forward stdout JSON when present and MUST NOT invent missing metrics.
- **FR-006**: System MUST include public-data and regime-stratify evidence summaries without letting unrelated research-only partial public-data failures falsely block package readiness.
- **FR-007**: System MUST provide Markdown and JSON outputs.
- **FR-008**: System MUST include safety invariants that explicitly say no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, and no command execution.
- **FR-009**: System MUST expose a probe that can print consumed sidecar manifest entries.
- **FR-010**: System MUST mark this work's completed candidate as `candidate-broad-validation-failure-data-readiness-contract`.
- **FR-011**: System MUST NOT modify constitution, kernel manifest, order routing, capital ladder, live config, broker integration, secrets, whitelist/caps, or deploy guard behavior.

### Key Entities *(include if feature involves data)*

- **Data Readiness Contract**: Report-level object that records package rows, counts, missing inputs, public/regime evidence summaries, safety invariants, and completed candidate id.
- **Data Readiness Row**: One validation package with package identity, portfolio data surfaces, history manifest checks, observation metrics, readiness status, and next action.
- **Data Surface**: One portfolio command's portfolio TOML, expected history root, observed history root, and execution metrics.
- **History Manifest**: Candidate history support mapping from portfolio TOML to read-only exported history roots.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-broad-validation-failure-data-readiness-contract`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Focused data readiness tests pass and prove the current two blocked packages produce two package rows and three portfolio data surfaces.
- **SC-002**: Focused tests prove root mismatch or missing TOML produces `BLOCKED_DATA_INPUT`.
- **SC-003**: Focused tests prove missing result evidence produces `WAITING_FOR_EVIDENCE`.
- **SC-004**: Probe replay against current sidecars produces `CONTRACT_READY`, package count 2, surface count 3, and data-ready count 2.
- **SC-005**: Autonomous-work tests prove data-readiness released advances to package-kind expansion.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- Current sidecars still contain two retryable validation failure packages: `pkg-8aae8cb99874` and `pkg-c9a284fa4235`.
- Candidate-result-executor now contains execution evidence for the package commands, including portfolio-walk-forward stdout JSON.
- Public-data may be partially failed for research-only CPI, but the current validation package history roots are driven by candidate history support and portfolio TOMLs.
- This is risk grade 2 because it adds an operating contract and next-candidate closure marker, while leaving all money-path and safety perimeter controls unchanged.
