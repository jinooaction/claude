# Feature Specification: Forward Regime Edge Experiment

**Feature Branch**: `Codex/095-forward-regime-edge-experiment`
**Created**: 2026-07-04
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-forward-regime-edge-experiment`를 목표 스킬로 꼼꼼하게 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - no-live 실험 계약을 한 곳에서 본다 (Priority: P1)

운영자는 `candidate-forward-regime-edge-experiment`가 선택된 뒤 사람이 sidecar를 손으로 조합하지 않아도, forward 토너먼트·돈 경로·완료 장부·학습 장부·파이프라인 생존 상태를 함께 읽은 실험 계약을 JSON과 Markdown으로 받는다.

**Why this priority**: 다음 자율 후보의 본질은 새 주문이 아니라 "레짐별 forward edge를 어떤 증거와 기준으로 판정할지"를 고정하는 것이다. 계약이 기계 판독 가능해야 다음 세션이 같은 판단을 반복하지 않는다.

**Independent Test**: 최신 sidecar와 같은 입력을 주면 보고서가 안정적인 `experiment_id`, required input, safety boundary, validation gates, forward track snapshot을 발행하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** forward, money-path, released-work, learning ledger, pipeline-liveness 입력이 모두 존재함, **When** 실험 보고서를 생성하면, **Then** 보고서는 `forward_regime_edge_experiment` 계약과 검증 게이트를 JSON과 Markdown에 발행한다.
2. **Given** forward 토너먼트가 아직 관측 부족임, **When** 보고서를 생성하면, **Then** 계약은 유지하되 전체 상태는 관측 대기로 표시하고 챔피언이나 라이브 전환을 선언하지 않는다.

---

### User Story 2 - 레짐과 forward 관측 부족을 정직하게 분리한다 (Priority: P2)

운영자는 "엣지가 없다", "관측이 부족하다", "파이프라인이 죽었다", "돈 경로가 미리보기다"를 섞어 보지 않고 각각의 상태를 분리해서 본다.

**Why this priority**: 현재 forward 관측은 대부분 16/20 근처라 비교 전 상태다. 관측 부족을 실패나 성공으로 오판하면 자율 루프가 잘못된 다음 작업을 고른다.

**Independent Test**: forward 관측이 최소값보다 작으면 보고서가 `OBSERVATION_WAIT`를 내고, pipeline-liveness가 핵심 실패면 `BLOCKED`를 내는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 모든 forward 트랙이 `INSUFFICIENT_DATA`이고 관측 수가 최소값보다 작음, **When** 보고서를 생성하면, **Then** next observation gate가 남은 관측 수와 기준을 표시한다.
2. **Given** 핵심 sidecar가 stale 또는 missing임, **When** 보고서를 생성하면, **Then** 실험 계약은 자동 착수 가능으로 보이지 않고 blocker가 표시된다.

---

### User Story 3 - 후보 완료 뒤 다음 투자 엣지 후보로 전진한다 (Priority: P3)

운영자는 이번 실험 계약 후보가 released-work에 닫힌 뒤 같은 후보를 다시 받지 않고, 투자 엣지 지도 안의 다음 no-live 후보로 이동한다.

**Why this priority**: 완료 후보를 명시적으로 닫아야 자율 성장 루프가 같은 계약 작성 후보를 반복하지 않는다.

**Independent Test**: released-work 로컬 재현에 `candidate-forward-regime-edge-experiment`가 나타나고, autonomous-work 로컬 재현이 다음 투자 엣지 후보를 선택하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 스펙 095가 완료된 상태, **When** released-work가 스펙을 스캔하면, **Then** `candidate-forward-regime-edge-experiment`가 released 후보로 기록된다.
2. **Given** `candidate-forward-regime-edge-experiment`가 released됨, **When** autonomous-work 보고서를 생성하면, **Then** 다음 미완료 투자 엣지 후보가 선택된다.

### Edge Cases

- forward sidecar의 일부 트랙 판정 JSON이 없으면 해당 트랙은 `UNKNOWN`으로 남기고, incumbent가 unknown이면 실험 상태를 blocked로 낮춘다.
- money-path가 `PREVIEW_ONLY`가 아니더라도 이 보고서는 주문이나 자본 변경을 하지 않으며, no-live 안전 검증 실패를 별도 표시한다.
- released-work sidecar가 lagging인 경우 probe는 현재 checkout의 스펙 스캔 결과로 완료 마커를 재현할 수 있어야 한다.
- learning ledger가 비어 있거나 최신 후보를 모르면 실험 계약은 만들되, 학습 중복 방지 증거가 약하다고 표시한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a deterministic forward-regime-edge experiment report with JSON and Markdown outputs.
- **FR-002**: System MUST consume these required inputs: `automation/rebalance-paper-forward-last-run:LAST_RUN.md`, `automation/money-path-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, `automation/autonomous-evolution-last-run:learning_ledger.json`, and `automation/pipeline-liveness-last-run:LAST_RUN.md`.
- **FR-003**: System MUST preserve the no-live safety boundary in the report: no broker API calls, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, and no paid external services.
- **FR-004**: System MUST classify the report as `OBSERVATION_WAIT` when forward tracks are present but not yet comparable.
- **FR-005**: System MUST classify the report as `BLOCKED` when critical evidence is missing, malformed, or pipeline liveness reports a critical failure.
- **FR-006**: System MUST include validation gates for comparable forward window, incumbent-vs-challenger fairness, multiplicity correction, regime brittleness review, no-live safety, and released-work closure.
- **FR-007**: System MUST mark this work's completed candidate as `candidate-forward-regime-edge-experiment`.
- **FR-008**: System MUST NOT modify constitution, kernel, order routing, capital ladder, auto-reassign gates, live config, broker integrations, secrets, whitelist/caps, or deployment guard behavior.

### Key Entities *(include if feature involves data)*

- **Forward Regime Edge Experiment Report**: Top-level JSON/Markdown artifact that records status, contract, evidence, gates, and next observation requirements.
- **Evidence Surface**: One consumed sidecar with parse status, source ref, and extracted summary.
- **Forward Track Snapshot**: One forward tournament track with verdict, observation count, comparability, rank, drawdown, and incumbent flag.
- **Regime Context**: Current regime-related evidence extracted from the forward sidecar's strategy monitor when available.
- **Validation Gate**: A named pass/wait/fail item that explains whether the no-live experiment can be evaluated yet.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-forward-regime-edge-experiment`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Probe manifest lists all five required sidecars with stable keys and refs.
- **SC-002**: With current-style sidecars, JSON output includes `experiment_id`, `overall_status`, `validation_gates`, `forward_tracks`, `money_state`, and `safety_boundary`.
- **SC-003**: Current forward observation shortage produces `OBSERVATION_WAIT`, not `EXECUTION_READY`, `EDGE_CONFIRMED`, or live-change language.
- **SC-004**: Focused unit and integration tests for the new report and probe pass.
- **SC-005**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.
- **SC-006**: After completion marker is scanned, autonomous-work local replay advances to the next unreleased investment-edge no-live candidate.

## Assumptions

- The latest forward sidecar remains the authoritative no-live tournament evidence surface.
- Regime context for this first contract can be derived from existing forward sidecar monitor blocks and track metadata; deeper per-regime NAV attribution is a later experiment, not this contract's implementation.
- The current money path remains `PREVIEW_ONLY`, and this feature must stay useful even if that state changes by flagging no-live safety rather than placing orders.
- This feature is risk grade 2 because it changes operating reporting and candidate closure, while leaving the money path and safety perimeter unchanged.
