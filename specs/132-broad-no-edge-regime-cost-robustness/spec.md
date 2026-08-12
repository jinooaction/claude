# Feature Specification: Broad NO_EDGE Regime Cost Robustness

**Feature Branch**: `codex/broad-no-edge-regime-cost-robustness`  
**Created**: 2026-08-12  
**Status**: Draft  
**Input**: User description: "다음 작업 후보 `candidate-broad-no-edge-regime-cost-robustness-experiment`를 목표 스킬로 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 레짐별 취약 구간을 한 곳에서 본다 (Priority: P1)

운영자는 `NO_EDGE_YET`가 이어질 때, 현재 forward paper 성과가 어떤 레짐 구간에서 약한지 JSON과 Markdown 보고서로 확인한다. 보고서는 `regime-stratify`의 레짐별 관측 수, 수익률, 샤프, 낙폭을 읽어 충분한 관측이 있는 구간과 더 기다려야 하는 구간을 나눈다.

**Why this priority**: 이번 후보의 핵심은 단순히 새 신호를 또 만드는 것이 아니라, 기존 paper 성과가 레짐 전환에 약한지 먼저 분리하는 것이다.

**Independent Test**: 현재 스타일의 `regime-stratify` sidecar 입력을 주면 보고서가 두 개 이상의 레짐 창을 읽고, 레짐별 관측 수와 약점 태그를 안정적으로 발행하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `regime-stratify` sidecar에 `GLOBAL-TREND`와 `GLOBAL-TREND-WIDE` stratified JSON이 있음, **When** 보고서를 생성하면, **Then** 각 전략의 레짐별 관측 수, 샤프, 낙폭, 취약 태그를 JSON과 Markdown에 발행한다.
2. **Given** 어떤 레짐의 관측 수가 20개 미만임, **When** 보고서를 생성하면, **Then** 해당 레짐은 통과/실패 단정이 아니라 `WAIT` 상태로 표시한다.

---

### User Story 2 - 비용 민감도를 실거래 허가와 분리한다 (Priority: P2)

운영자는 `execution-quality`와 `money-path`를 함께 보며, 비용과 브로커 오류가 paper 성과를 얼마나 깎을 수 있는지 no-live stress test 기준으로 확인한다.

**Why this priority**: paper 성과가 비용, 거부 주문, 슬리피지에 취약하면 실제 돈 경로로 올릴 수 없다. 하지만 이 보고서는 비용 기준을 낮춰 실거래를 허용하는 작업이 아니다.

**Independent Test**: `execution-quality`가 `OBSERVE`, broker rejection 2건, KIS smoke success이고 `money-path`가 `PREVIEW_ONLY`이면, 보고서는 비용 스트레스 후보를 만들되 live readiness를 열지 않는다.

**Acceptance Scenarios**:

1. **Given** execution-quality가 broker rejection과 smoke 상태를 제공함, **When** 보고서를 생성하면, **Then** 10/25/50bp 비용 스트레스와 브로커 오류 관측 요약을 발행한다.
2. **Given** money-path가 `PREVIEW_ONLY`이고 `NO_EDGE_YET`임, **When** 보고서를 생성하면, **Then** no-live 설계는 가능하나 실제 주문 가능 상태로 표시하지 않는다.

---

### User Story 3 - 후보 완료 뒤 다음 broad no-edge 후보로 전진한다 (Priority: P3)

운영자는 이번 레짐·비용 견고성 후보가 완료된 뒤 같은 후보를 다시 받지 않고, broad no-edge frontier 안에서 다음 후보인 데이터 결측 원인 감사가 열린 상태로 이동한다.

**Why this priority**: 완료 후보를 released-work가 읽을 수 있게 닫아야 자율 작업 루프가 같은 후보를 반복하지 않는다.

**Independent Test**: released-work 로컬 재현에 `candidate-broad-no-edge-regime-cost-robustness-experiment`가 나타나고, autonomous-work 로컬 재현의 `broad_no_edge_frontier_map`에서 이 후보의 `coverage_status`가 `released`, `candidate-broad-no-edge-data-gap-audit`의 `coverage_status`가 `open`인지 확인한다.

**Acceptance Scenarios**:

1. **Given** 스펙 132가 완료된 상태, **When** released-work가 스펙을 스캔하면, **Then** `candidate-broad-no-edge-regime-cost-robustness-experiment`가 released 후보로 기록된다.
2. **Given** 이 후보가 released됨, **When** autonomous-work 보고서를 생성하면, **Then** broad no-edge frontier의 다음 열린 후보는 `candidate-broad-no-edge-data-gap-audit`다.

### Edge Cases

- `regime-stratify`가 없거나 malformed이면 핵심 레짐 증거가 없으므로 `BLOCKED` 처리한다.
- `execution-quality`가 없거나 malformed이면 비용 스트레스 기준이 없으므로 `BLOCKED` 처리한다.
- `money-path`가 실주문 가능 상태처럼 보이면 이 보고서는 `OBSERVATION_WAIT`로 낮춰 안전 검토를 요구한다.
- `regime-stratify`에 여러 stratified JSON이 있으면 모두 읽고 섹션 제목을 보수적으로 track label로 사용한다.
- 레짐별 관측 수가 20개 미만이면 통계 판정을 하지 않고 대기 상태로 남긴다.
- released-work sidecar가 뒤처진 경우 probe는 현재 checkout의 completion marker를 스캔해 closure gate를 재현할 수 있어야 한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a deterministic broad no-edge regime-cost robustness report with JSON and Markdown outputs.
- **FR-002**: System MUST consume these required inputs: `automation/regime-stratify-last-run:LAST_RUN.md`, `automation/execution-quality-last-run:LAST_RUN.md`, `automation/money-path-last-run:LAST_RUN.md`, `automation/edge-autoarm-last-run:LAST_RUN.md`, `automation/rebalance-paper-forward-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, `automation/autonomous-evolution-last-run:learning_ledger.json`, and `automation/pipeline-liveness-last-run:LAST_RUN.md`.
- **FR-003**: System MUST preserve the no-live safety boundary in the report: no broker API calls, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel change, and no paid external services.
- **FR-004**: System MUST summarize every readable regime-stratified block with track label, total return days, join rule, regime labels, n_days, total_return_pct, sharpe, and max_drawdown_pct.
- **FR-005**: System MUST classify each regime label as `PASS`, `WAIT`, or `STRESS` using deterministic observation and drawdown/sharpe rules.
- **FR-006**: System MUST summarize execution-quality evidence including overall status, live gate verdict/signal, rejected order count, parsed broker error count, KIS message codes, smoke state, and smoke error rate.
- **FR-007**: System MUST generate cost stress rows for 10, 25, and 50 basis-point levels and show which forward tracks remain candidates only for no-live follow-up.
- **FR-008**: System MUST include exclusion criteria explaining why live rearm/order submission and cost-blind promotion are invalid next experiments.
- **FR-009**: System MUST classify the report as `CONTRACT_READY` when required evidence is present, pipeline liveness is healthy, no-live safety is preserved, at least one readable regime block exists, and cost stress rows are generated.
- **FR-010**: System MUST classify the report as `BLOCKED` when critical regime, execution-quality, money-path, forward, released-work, learning-ledger, or pipeline evidence is missing or malformed.
- **FR-011**: System MUST include validation gates for input evidence, pipeline liveness, no-live safety, money gate alignment, regime window coverage, execution cost observability, cost stress coverage, learning-ledger duplication, and released-work closure.
- **FR-012**: System MUST mark this work's completed candidate as `candidate-broad-no-edge-regime-cost-robustness-experiment`.
- **FR-013**: System MUST identify `candidate-broad-no-edge-data-gap-audit` as the next broad no-edge candidate after this work is released.
- **FR-014**: System MUST NOT modify constitution, kernel, order routing, capital ladder, auto-reassign gates, live config, broker integrations, secrets, whitelist/caps, or deployment guard behavior.

### Key Entities *(include if feature involves data)*

- **Regime Cost Robustness Report**: Top-level JSON/Markdown artifact that records status, evidence, regime windows, cost stress rows, gates, exclusions, and safety boundary.
- **Evidence Surface**: One consumed sidecar with parse status, source ref, and extracted summary.
- **Regime Window**: One stratified strategy section with track label, join rule, total days, and per-regime metrics.
- **Regime Label Assessment**: One label-level record with observation count, return, sharpe, drawdown, status, and reason.
- **Execution Cost Snapshot**: Parsed execution-quality evidence for broker rejection, smoke, and live gate context.
- **Cost Stress Row**: One deterministic stress level with basis points, cost note, affected tracks, and no-live status.
- **Exclusion Criterion**: A deterministic reason why a tempting next action is already unsafe or insufficient.
- **Validation Gate**: A named pass/wait/fail item that explains whether the no-live contract is usable.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-broad-no-edge-regime-cost-robustness-experiment`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Probe manifest lists all eight required sidecars with stable keys and refs.
- **SC-002**: With current-style sidecars, JSON output includes `experiment_id`, `overall_status`, `regime_windows`, `regime_metrics`, `execution_cost_snapshot`, `cost_stress_rows`, `exclusion_criteria`, `validation_gates`, `money_state`, `edge_autoarm_state`, and `safety_boundary`.
- **SC-003**: The report reads at least two stratified regime windows from current-style sidecar text and marks low-observation regimes as `WAIT`.
- **SC-004**: The report always emits exactly three cost stress rows: 10bp, 25bp, and 50bp.
- **SC-005**: Missing or malformed critical evidence produces `BLOCKED` and a failing validation gate.
- **SC-006**: Focused unit and integration tests for the new report and probe pass.
- **SC-007**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.
- **SC-008**: After completion marker is scanned, autonomous-work local replay marks this candidate `coverage_status=released` in `broad_no_edge_frontier_map` and exposes `candidate-broad-no-edge-data-gap-audit` as the next `coverage_status=open` broad no-edge candidate.

## Assumptions

- `regime-stratify` is the authoritative research-only regime evidence surface for this candidate.
- `execution-quality` is sufficient for a first no-live cost robustness contract even when live fill cost basis is still sparse.
- A low-observation regime is not a failed regime; it is a wait condition.
- Cost stress rows are planning thresholds, not live order pricing or capital allocation instructions.
- This feature is risk grade 2 because it changes operating reporting and candidate closure, while leaving the money path and safety perimeter unchanged.
