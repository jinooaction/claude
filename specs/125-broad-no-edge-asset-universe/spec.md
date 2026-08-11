# Feature Specification: Broad NO_EDGE Asset Universe Rotation

**Feature Branch**: `codex/broad-no-edge-asset-universe`  
**Created**: 2026-08-11  
**Status**: Complete  
**Input**: User description: "다음 작업 후보 `candidate-broad-no-edge-asset-universe-rotation-experiment`를 목표 스킬로 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 자산군 방어 회전 후보를 한 곳에서 본다 (Priority: P1)

운영자는 `NO_EDGE_YET`가 계속될 때, 현재 forward 토너먼트가 이미 시험한 자산군과 아직 별도 no-live 후보로 분리해야 할 방어 자산군 후보를 JSON과 Markdown 보고서로 받는다.

**Why this priority**: 이번 후보의 핵심은 기존 주식·채권·금 중심 트랙을 반복하지 않고, 현금성·단기채·인플레 방어·통화 방어 같은 자산군 회전 후보를 안전하게 넓히는 것이다.

**Independent Test**: 현재 스타일의 sidecar 입력을 주면 보고서가 안정적인 `experiment_id`, 필수 입력, 기존 자산군 노출, 제안 후보, 제외 기준, 안전 경계를 발행하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** forward, money-path, edge-autoarm, public-data, released-work, learning ledger, pipeline-liveness 입력이 모두 존재함, **When** 자산군 회전 보고서를 생성하면, **Then** 보고서는 현재 시험된 자산군 범위와 새 no-live 후보군을 JSON과 Markdown에 발행한다.
2. **Given** 기존 `wide` 트랙이 이미 11슬리브 폭 확장을 시험했지만 `NO_EDGE`임, **When** 보고서를 생성하면, **Then** 단순 폭 확장은 제외하고 방어 역할이 다른 후보만 제안한다.

---

### User Story 2 - 돈 경로 차단과 후보 설계를 분리한다 (Priority: P2)

운영자는 `PREVIEW_ONLY`, `NO_EDGE_YET`, `WAIT_EDGE`를 실험 실패나 주문 허가와 혼동하지 않고, 후보 설계가 읽기 전용임을 확인한다.

**Why this priority**: 현재 돈 경로는 실주문이 금지된 상태다. 보고서가 live readiness처럼 보이면 안전 경계를 깨고, 반대로 차단 상태만 반복하면 다음 후보 발굴이 멈춘다.

**Independent Test**: money-path와 edge-autoarm이 실주문 불가 상태여도 보고서는 후보 계약을 만들고, 실제 주문·자본 배분·live 변경 금지를 safety gate에 남기는지 확인한다.

**Acceptance Scenarios**:

1. **Given** money-path가 `PREVIEW_ONLY`이고 edge-autoarm이 `WAIT_EDGE`임, **When** 보고서를 생성하면, **Then** no-live 후보 설계는 계속 가능하지만 실주문 가능 상태로 표시하지 않는다.
2. **Given** 핵심 sidecar가 없거나 malformed임, **When** 보고서를 생성하면, **Then** 보고서는 `BLOCKED`와 실패 gate를 표시한다.

---

### User Story 3 - 후보 완료 뒤 다음 broad no-edge 후보로 전진한다 (Priority: P3)

운영자는 이번 자산군 회전 후보가 완료된 뒤 같은 후보를 다시 받지 않고, broad no-edge frontier의 다음 후보인 다중 보유 기간·신호군 실험으로 이동한다.

**Why this priority**: 완료 후보를 released-work가 읽을 수 있게 닫아야 자율 작업 루프가 같은 후보를 반복하지 않는다.

**Independent Test**: released-work 로컬 재현에 `candidate-broad-no-edge-asset-universe-rotation-experiment`가 나타나고, autonomous-work 로컬 재현이 `candidate-broad-no-edge-multi-horizon-signal-experiment`를 선택하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 스펙 125가 완료된 상태, **When** released-work가 스펙을 스캔하면, **Then** `candidate-broad-no-edge-asset-universe-rotation-experiment`가 released 후보로 기록된다.
2. **Given** 이 후보가 released됨, **When** autonomous-work 보고서를 생성하면, **Then** 다음 broad no-edge 후보는 `candidate-broad-no-edge-multi-horizon-signal-experiment`다.

### Edge Cases

- forward sidecar의 리더보드 결정 JSON이 없으면 track 판정 블록 재구성은 이번 범위에서 하지 않고 `BLOCKED`로 둔다.
- 일부 track의 universe가 없으면 해당 track의 자산군은 `unknown`으로 남기되 다른 track 근거로 보고서를 계속 만든다.
- public-data가 `overall_ok=false`여도 금리·VIX·재무부 금리처럼 후보 설계에 필요한 핵심 입력이 충분하면 계약은 만들고 결측 항목을 warning으로 남긴다.
- learning ledger가 현재 후보를 억제했다면 중복 또는 실패 기억으로 보고서를 `BLOCKED` 처리한다.
- released-work sidecar가 뒤처진 경우 probe는 현재 checkout의 completion marker를 스캔해 closure gate를 재현할 수 있어야 한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a deterministic broad no-edge asset-universe rotation report with JSON and Markdown outputs.
- **FR-002**: System MUST consume these required inputs: `automation/rebalance-paper-forward-last-run:LAST_RUN.md`, `automation/money-path-last-run:LAST_RUN.md`, `automation/edge-autoarm-last-run:LAST_RUN.md`, `automation/public-data:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, `automation/autonomous-evolution-last-run:learning_ledger.json`, and `automation/pipeline-liveness-last-run:LAST_RUN.md`.
- **FR-003**: System MUST preserve the no-live safety boundary in the report: no broker API calls, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel change, and no paid external services.
- **FR-004**: System MUST classify current forward track universes into stable asset buckets such as equity, duration bond, credit, commodity, real estate, currency, cash proxy, and unknown.
- **FR-005**: System MUST compute asset-universe metrics including track count, tested bucket count, incumbent bucket set, wide-track status, candidate count, and excluded duplicate count.
- **FR-006**: System MUST propose no-live defensive rotation candidates only when they are separated from already-failed direct wide expansion.
- **FR-007**: System MUST include exclusion criteria explaining why simple repetition of the existing wide track is not enough.
- **FR-008**: System MUST classify the report as `CONTRACT_READY` when required evidence is present, pipeline liveness is healthy, and at least one separated no-live candidate can be proposed.
- **FR-009**: System MUST classify the report as `BLOCKED` when critical evidence is missing, malformed, pipeline liveness reports a critical failure, or learning ledger suppresses this candidate.
- **FR-010**: System MUST include validation gates for input evidence, pipeline liveness, no-live safety, money gate alignment, public data support, forward universe coverage, candidate separation, learning-ledger duplication, and released-work closure.
- **FR-011**: System MUST mark this work's completed candidate as `candidate-broad-no-edge-asset-universe-rotation-experiment`.
- **FR-012**: System MUST NOT modify constitution, kernel, order routing, capital ladder, auto-reassign gates, live config, broker integrations, secrets, whitelist/caps, or deployment guard behavior.

### Key Entities *(include if feature involves data)*

- **Asset Universe Rotation Report**: Top-level JSON/Markdown artifact that records status, evidence, current universe coverage, proposed candidates, excluded candidates, gates, and safety boundary.
- **Evidence Surface**: One consumed sidecar with parse status, source ref, and extracted summary.
- **Forward Universe Snapshot**: One forward tournament row with track key, label, verdict, observation readiness, universe, and derived asset buckets.
- **Asset Bucket Coverage**: Aggregated count of tested asset buckets and whether the incumbent/wide tracks cover them.
- **Defensive Rotation Candidate**: A no-live candidate idea with asset bucket, symbols, rationale, separation reason, required evidence, and status.
- **Exclusion Criterion**: A deterministic reason why a tempting candidate is already covered or not safe to promote as this slice's next experiment.
- **Validation Gate**: A named pass/wait/fail item that explains whether the no-live contract is usable.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-broad-no-edge-asset-universe-rotation-experiment`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Probe manifest lists all seven required sidecars with stable keys and refs.
- **SC-002**: With current-style sidecars, JSON output includes `experiment_id`, `overall_status`, `forward_universe_snapshots`, `asset_universe_metrics`, `proposed_rotation_candidates`, `exclusion_criteria`, `validation_gates`, `money_state`, `edge_autoarm_state`, and `safety_boundary`.
- **SC-003**: The report proposes at least two separated no-live defensive rotation candidates and excludes direct repetition of the already-failed wide-universe track.
- **SC-004**: Missing or malformed critical evidence produces `BLOCKED` and a failing validation gate.
- **SC-005**: Focused unit and integration tests for the new report and probe pass.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.
- **SC-007**: After completion marker is scanned, autonomous-work local replay advances to `candidate-broad-no-edge-multi-horizon-signal-experiment`.

## Assumptions

- The latest forward sidecar is the authoritative no-live tournament evidence surface for current tested universes.
- Asset bucket classification can start from ETF/ticker sets already present in forward rows; deeper market taxonomy is a later experiment.
- `public-data` is research-only and may support macro context, but it must not become a live trading signal in this feature.
- The current money path remains `PREVIEW_ONLY` / `NO_EDGE_YET`, and this feature must stay useful by separating no-live design from live readiness.
- This feature is risk grade 2 because it changes operating reporting and candidate closure, while leaving the money path and safety perimeter unchanged.
