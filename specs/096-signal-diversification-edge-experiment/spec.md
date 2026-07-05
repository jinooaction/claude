# Feature Specification: Signal Diversification Edge Experiment

**Feature Branch**: `Codex/096-signal-diversification-edge-experiment`
**Created**: 2026-07-05
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-signal-diversification-edge-experiment`를 목표 스킬로 꼼꼼하게 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 신호 다양성 실험 계약을 한 곳에서 본다 (Priority: P1)

운영자는 `candidate-signal-diversification-edge-experiment`가 선택된 뒤 사람이 forward 리더보드, 돈 경로, 완료 장부, 학습 장부, 파이프라인 생존 상태를 손으로 조합하지 않아도, 현재 forward 후보군이 어떤 신호군에 치우쳤는지와 다음 no-live 실험 후보가 무엇인지 JSON과 Markdown으로 받는다.

**Why this priority**: 이번 후보의 핵심은 주문이나 전략 교체가 아니라, 투자 엣지 탐색 폭이 특정 신호군에 갇히지 않도록 신호 다양성 계약을 기계 판독으로 고정하는 것이다.

**Independent Test**: 현재 sidecar 형태의 입력을 주면 보고서가 안정적인 `experiment_id`, required input, 신호군 분류, 겹침 지표, 안전 경계, 검증 게이트를 발행하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** forward, money-path, released-work, learning ledger, pipeline-liveness 입력이 모두 존재함, **When** 신호 다변화 보고서를 생성하면, **Then** 보고서는 현재 forward track을 신호군별로 분류하고 no-live 실험 계약을 JSON과 Markdown에 발행한다.
2. **Given** 현재 forward 후보군이 대부분 추세·자산배분 변형에 몰려 있음, **When** 보고서를 생성하면, **Then** 계약은 신호 다양성 상태와 다음 후보군을 분리해 표시한다.

---

### User Story 2 - 신호 겹침과 관측 부족을 정직하게 분리한다 (Priority: P2)

운영자는 "새 신호가 부족하다", "관측이 아직 비교 전이다", "pipeline이 깨졌다", "돈 경로가 미리보기다"를 섞어 보지 않고 각각의 상태를 분리해서 본다.

**Why this priority**: 현재 forward 리더보드는 관측 16/20 근처라 아직 비교 전이다. 관측 부족을 엣지 실패나 신호 다양성 성공으로 오판하면 다음 후보가 잘못 전진한다.

**Independent Test**: forward 관측이 최소값보다 작으면 보고서가 신호 계약은 유지하되 observation gate를 대기 상태로 표시하고, 핵심 evidence가 없으면 blocked로 낮추는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 모든 forward 트랙이 `INSUFFICIENT_DATA`이고 관측 수가 최소값보다 작음, **When** 보고서를 생성하면, **Then** 신호 다양성 계약과 next observation gate가 함께 표시된다.
2. **Given** forward sidecar나 pipeline-liveness가 missing 또는 malformed임, **When** 보고서를 생성하면, **Then** 보고서는 자동 실행 가능처럼 보이지 않고 실패 gate를 표시한다.

---

### User Story 3 - 후보 완료 뒤 비용 차감 엣지 후보로 전진한다 (Priority: P3)

운영자는 이번 신호 다변화 후보가 released-work에 닫힌 뒤 같은 후보를 다시 받지 않고, 투자 엣지 지도 안의 다음 no-live 후보인 비용 차감 엣지 실험으로 이동한다.

**Why this priority**: 완료 후보를 명시적으로 닫아야 자율 성장 루프가 같은 계약 작성 후보를 반복하지 않는다.

**Independent Test**: released-work 로컬 재현에 `candidate-signal-diversification-edge-experiment`가 나타나고, autonomous-work 로컬 재현이 다음 투자 엣지 후보를 선택하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 스펙 096이 완료된 상태, **When** released-work가 스펙을 스캔하면, **Then** `candidate-signal-diversification-edge-experiment`가 released 후보로 기록된다.
2. **Given** `candidate-signal-diversification-edge-experiment`가 released됨, **When** autonomous-work 보고서를 생성하면, **Then** 다음 미완료 투자 엣지 후보 `candidate-cost-adjusted-edge-experiment`가 선택된다.

### Edge Cases

- forward sidecar의 리더보드 결정 JSON이 없으면 track 판정 블록으로 재구성을 시도하고, 둘 다 실패하면 보고서를 `BLOCKED`로 표시한다.
- 일부 track의 universe가 없거나 비어 있으면 해당 track의 overlap은 unknown으로 두되 전체 보고서는 가능한 다른 track 근거로 계속 만든다.
- money-path가 `PREVIEW_ONLY`가 아니더라도 이 보고서는 주문이나 자본 변경을 하지 않으며 no-live safety gate를 별도 표시한다.
- learning ledger가 비어 있거나 현재 후보 기억이 없으면 보고서는 만들되, 중복 방지 증거가 약하다고 표시한다.
- released-work sidecar가 lagging인 경우 probe는 현재 checkout의 스펙 완료 마커를 스캔해 closure gate를 재현할 수 있어야 한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a deterministic signal-diversification-edge experiment report with JSON and Markdown outputs.
- **FR-002**: System MUST consume these required inputs: `automation/rebalance-paper-forward-last-run:LAST_RUN.md`, `automation/money-path-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, `automation/autonomous-evolution-last-run:learning_ledger.json`, and `automation/pipeline-liveness-last-run:LAST_RUN.md`.
- **FR-003**: System MUST preserve the no-live safety boundary in the report: no broker API calls, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel change, and no paid external services.
- **FR-004**: System MUST classify forward tracks into stable signal families such as trend timing, risk-managed beta, multi-asset allocation, global diversification, fixed-weight allocation, and wide-universe allocation.
- **FR-005**: System MUST compute signal diversity metrics including family count, concentration in the largest family, incumbent-vs-candidate universe overlap, and count of proposed new signal candidates.
- **FR-006**: System MUST classify the report as `CONTRACT_READY` when required evidence is present and at least one low-overlap signal candidate can be proposed without live-money action.
- **FR-007**: System MUST classify the report as `OBSERVATION_WAIT` when evidence is present but forward track observations are not yet comparable.
- **FR-008**: System MUST classify the report as `BLOCKED` when critical evidence is missing, malformed, or pipeline liveness reports a critical failure.
- **FR-009**: System MUST include validation gates for input evidence, pipeline liveness, no-live safety, forward observation readiness, signal diversity, incumbent overlap, learning-ledger duplication, and released-work closure.
- **FR-010**: System MUST mark this work's completed candidate as `candidate-signal-diversification-edge-experiment`.
- **FR-011**: System MUST NOT modify constitution, kernel, order routing, capital ladder, auto-reassign gates, live config, broker integrations, secrets, whitelist/caps, or deployment guard behavior.

### Key Entities *(include if feature involves data)*

- **Signal Diversification Edge Experiment Report**: Top-level JSON/Markdown artifact that records status, contract, evidence, signal families, proposed candidates, gates, and safety boundary.
- **Evidence Surface**: One consumed sidecar with parse status, source ref, and extracted summary.
- **Signal Family Snapshot**: Grouping of forward tracks by signal type with track count, incumbent presence, representative tracks, and observation readiness.
- **Signal Candidate**: A no-live candidate proposed to widen signal search, with family, rationale, source refs, and safety boundary.
- **Overlap Metric**: Incumbent-vs-candidate universe overlap and family concentration indicators that show whether candidates are genuinely different.
- **Validation Gate**: A named pass/wait/fail item that explains whether the no-live experiment can be evaluated yet.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-signal-diversification-edge-experiment`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Probe manifest lists all five required sidecars with stable keys and refs.
- **SC-002**: With current-style sidecars, JSON output includes `experiment_id`, `overall_status`, `signal_families`, `proposed_signal_candidates`, `diversification_metrics`, `validation_gates`, `money_state`, and `safety_boundary`.
- **SC-003**: Current forward observation shortage is visible as an observation gate, but the no-live signal diversification contract does not claim live readiness or place orders.
- **SC-004**: Focused unit and integration tests for the new report and probe pass.
- **SC-005**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.
- **SC-006**: After completion marker is scanned, autonomous-work local replay advances to `candidate-cost-adjusted-edge-experiment`.

## Assumptions

- The latest forward sidecar remains the authoritative no-live tournament evidence surface.
- Signal family classification can start from current forward track metadata and universe overlap; deeper factor attribution is a later experiment, not this contract's implementation.
- The current money path remains `PREVIEW_ONLY`, and this feature must stay useful if that state changes by flagging no-live safety rather than placing orders.
- This feature is risk grade 2 because it changes operating reporting and candidate closure, while leaving the money path and safety perimeter unchanged.
