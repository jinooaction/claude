# Feature Specification: Broad NO_EDGE Multi-Horizon Signal

**Feature Branch**: `codex/broad-no-edge-multi-horizon-signal`  
**Created**: 2026-08-12  
**Status**: Draft  
**Input**: User description: "다음 작업 후보 `candidate-broad-no-edge-multi-horizon-signal-experiment`를 목표 스킬로 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 보유 기간과 신호군 후보를 한 곳에서 본다 (Priority: P1)

운영자는 `NO_EDGE_YET`가 이어질 때, 단기·중기·장기 보유 기간과 trend·carry·quality·volatility 신호군을 분리한 no-live 실험 후보를 JSON과 Markdown 보고서로 받는다.

**Why this priority**: 이번 후보의 핵심은 같은 momentum 계열을 같은 기간으로 반복하지 않고, 엣지 탐색 폭을 신호군과 보유 기간 축으로 넓히는 것이다.

**Independent Test**: 현재 스타일의 sidecar 입력을 주면 보고서가 안정적인 `experiment_id`, 필수 입력, 현재 forward 신호 노출, 제안 후보, 제외 기준, 안전 경계를 발행하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** forward, money-path, edge-autoarm, public-data, regime-stratify, released-work, learning ledger, pipeline-liveness 입력이 모두 존재함, **When** 다중 보유 기간 신호군 보고서를 생성하면, **Then** 보고서는 현재 시험된 신호/기간 범위와 새 no-live 후보군을 JSON과 Markdown에 발행한다.
2. **Given** 기존 forward track이 모두 `NO_EDGE`임, **When** 보고서를 생성하면, **Then** 단일 momentum 재시도는 제외하고 서로 다른 보유 기간과 신호군 조합만 제안한다.

---

### User Story 2 - 돈 경계와 실험 설계를 분리한다 (Priority: P2)

운영자는 `PREVIEW_ONLY`, `NO_EDGE_YET`, `WAIT_EDGE`를 실주문 허가로 오해하지 않고, 이 보고서가 읽기 전용 실험 설계임을 확인한다.

**Why this priority**: 이 후보는 돈 경로를 여는 작업이 아니다. 보고서가 live readiness처럼 보이면 안전 경계를 깨고, 반대로 차단 상태만 반복하면 다음 안전 후보 발굴이 멈춘다.

**Independent Test**: money-path와 edge-autoarm이 실주문 불가 상태여도 보고서는 후보 계약을 만들고, 실제 주문·자본 배분·live 변경 금지를 safety gate에 남기는지 확인한다.

**Acceptance Scenarios**:

1. **Given** money-path가 `PREVIEW_ONLY`이고 edge-autoarm이 `WAIT_EDGE`임, **When** 보고서를 생성하면, **Then** no-live 후보 설계는 계속 가능하지만 실주문 가능 상태로 표시하지 않는다.
2. **Given** 핵심 sidecar가 없거나 malformed임, **When** 보고서를 생성하면, **Then** 보고서는 `BLOCKED`와 실패 gate를 표시한다.

---

### User Story 3 - 후보 완료 뒤 다음 broad no-edge 후보로 전진한다 (Priority: P3)

운영자는 이번 다중 보유 기간 신호군 후보가 완료된 뒤 같은 broad 후보를 다시 받지 않고, broad no-edge frontier 안에서 다음 후보인 레짐·비용 견고성 실험이 열린 상태로 이동한다. 단, 전체 autonomous-work 선택은 다른 더 높은 우선순위의 복구·검증 후보가 있으면 그 후보를 먼저 고를 수 있다.

**Why this priority**: 완료 후보를 released-work가 읽을 수 있게 닫아야 자율 작업 루프가 같은 후보를 반복하지 않는다.

**Independent Test**: released-work 로컬 재현에 `candidate-broad-no-edge-multi-horizon-signal-experiment`가 나타나고, autonomous-work 로컬 재현의 `broad_no_edge_frontier_map`에서 이 후보의 `coverage_status`가 `released`, `candidate-broad-no-edge-regime-cost-robustness-experiment`의 `coverage_status`가 `open`인지 확인한다.

**Acceptance Scenarios**:

1. **Given** 스펙 131이 완료된 상태, **When** released-work가 스펙을 스캔하면, **Then** `candidate-broad-no-edge-multi-horizon-signal-experiment`가 released 후보로 기록된다.
2. **Given** 이 후보가 released됨, **When** autonomous-work 보고서를 생성하면, **Then** broad no-edge frontier의 다음 열린 후보는 `candidate-broad-no-edge-regime-cost-robustness-experiment`다.

### Edge Cases

- forward sidecar의 리더보드 결정 JSON이 없으면 현재 신호 노출을 재구성하지 않고 `BLOCKED`로 둔다.
- forward row에 holding period나 signal family가 직접 없으면 track key, label, universe, incumbent 여부에서 보수적으로 추론하고 `inferred=true`를 남긴다.
- public-data가 `overall_ok=false`여도 금리와 VIX 핵심 입력이 있으면 carry/volatility 후보 설계는 계속하고 warning으로 남긴다.
- regime-stratify가 없으면 regime-aware 후보는 `WAIT`로 두되 trend/quality 후보는 만들 수 있다.
- learning ledger가 현재 후보를 억제했다면 중복 또는 실패 기억으로 보고서를 `BLOCKED` 처리한다.
- released-work sidecar가 뒤처진 경우 probe는 현재 checkout의 completion marker를 스캔해 closure gate를 재현할 수 있어야 한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a deterministic broad no-edge multi-horizon signal report with JSON and Markdown outputs.
- **FR-002**: System MUST consume these required inputs: `automation/rebalance-paper-forward-last-run:LAST_RUN.md`, `automation/money-path-last-run:LAST_RUN.md`, `automation/edge-autoarm-last-run:LAST_RUN.md`, `automation/public-data:LAST_RUN.md`, `automation/regime-stratify-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, `automation/autonomous-evolution-last-run:learning_ledger.json`, and `automation/pipeline-liveness-last-run:LAST_RUN.md`.
- **FR-003**: System MUST preserve the no-live safety boundary in the report: no broker API calls, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel change, and no paid external services.
- **FR-004**: System MUST summarize current forward track signal exposure and holding-period exposure with deterministic inference and explicit unknowns.
- **FR-005**: System MUST compute multi-horizon metrics including track count, inferred signal family count, inferred holding period count, proposed count, waiting count, and excluded count.
- **FR-006**: System MUST propose no-live signal candidates that cover at least short, medium, and long horizon roles across trend, carry, quality, and volatility families when evidence allows.
- **FR-007**: System MUST include exclusion criteria explaining why single-horizon momentum repetition and live rearm/order submission are not valid next experiments.
- **FR-008**: System MUST classify the report as `CONTRACT_READY` when required evidence is present, pipeline liveness is healthy, no-live safety is preserved, and at least two separated no-live candidates can be proposed.
- **FR-009**: System MUST classify the report as `BLOCKED` when critical evidence is missing, malformed, pipeline liveness reports a critical failure, or learning ledger suppresses this candidate.
- **FR-010**: System MUST include validation gates for input evidence, pipeline liveness, no-live safety, money gate alignment, forward signal coverage, public-data support, regime support, candidate separation, learning-ledger duplication, and released-work closure.
- **FR-011**: System MUST mark this work's completed candidate as `candidate-broad-no-edge-multi-horizon-signal-experiment`.
- **FR-012**: System MUST NOT modify constitution, kernel, order routing, capital ladder, auto-reassign gates, live config, broker integrations, secrets, whitelist/caps, or deployment guard behavior.

### Key Entities *(include if feature involves data)*

- **Multi-Horizon Signal Report**: Top-level JSON/Markdown artifact that records status, evidence, current signal and horizon coverage, proposed candidates, excluded candidates, gates, and safety boundary.
- **Evidence Surface**: One consumed sidecar with parse status, source ref, and extracted summary.
- **Forward Signal Snapshot**: One forward tournament row with track key, label, verdict, observation readiness, universe, inferred signal families, inferred holding periods, and inference notes.
- **Signal Horizon Metrics**: Aggregated counts and sets for current signal families, holding periods, proposed candidates, waiting candidates, and exclusions.
- **Signal Experiment Candidate**: A no-live candidate idea with signal families, holding periods, rationale, separation reason, required evidence, and status.
- **Exclusion Criterion**: A deterministic reason why a tempting candidate is already covered or unsafe.
- **Validation Gate**: A named pass/wait/fail item that explains whether the no-live contract is usable.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-broad-no-edge-multi-horizon-signal-experiment`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Probe manifest lists all eight required sidecars with stable keys and refs.
- **SC-002**: With current-style sidecars, JSON output includes `experiment_id`, `overall_status`, `forward_signal_snapshots`, `signal_horizon_metrics`, `proposed_signal_candidates`, `exclusion_criteria`, `validation_gates`, `money_state`, `edge_autoarm_state`, `public_data_support`, `regime_support`, and `safety_boundary`.
- **SC-003**: The report proposes at least two separated no-live candidates and covers at least three holding-period roles plus four signal families across proposed or waiting candidates.
- **SC-004**: Missing or malformed critical evidence produces `BLOCKED` and a failing validation gate.
- **SC-005**: Focused unit and integration tests for the new report and probe pass.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.
- **SC-007**: After completion marker is scanned, autonomous-work local replay marks this candidate `coverage_status=released` in `broad_no_edge_frontier_map` and exposes `candidate-broad-no-edge-regime-cost-robustness-experiment` as the next `coverage_status=open` broad no-edge candidate.

## Assumptions

- The latest forward sidecar is the authoritative no-live tournament evidence surface for current tested tracks.
- Signal family and holding-period inference can start from track keys, labels, universes, and incumbent status; deeper strategy metadata is a later experiment.
- `public-data` and `regime-stratify` are research-only inputs and must not become live trading signals in this feature.
- The current money path remains `PREVIEW_ONLY` / `NO_EDGE_YET`, and this feature must stay useful by separating no-live design from live readiness.
- This feature is risk grade 2 because it changes operating reporting and candidate closure, while leaving the money path and safety perimeter unchanged.
