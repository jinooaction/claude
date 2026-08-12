# Feature Specification: Broad NO_EDGE Data Gap Audit

**Feature Branch**: `codex/broad-no-edge-data-gap-audit`
**Created**: 2026-08-12
**Status**: Draft
**Input**: User description: "다음 작업 후보 `candidate-broad-no-edge-data-gap-audit`를 목표 스킬로 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 데이터 결측 원인을 한 곳에서 분리한다 (Priority: P1)

운영자는 `NO_EDGE_YET`가 이어질 때, 공개 데이터의 어떤 항목이 정상이고 어떤 항목이 누락·미발행·신선도 문제인지 JSON과 Markdown 보고서로 확인한다. 보고서는 `public-data` summary와 `regime.json`을 읽어 발행 실패 항목, 교차검증 생략, 레짐 지표 누락을 같은 표면에서 분리한다.

**Why this priority**: 이번 후보의 핵심은 "엣지가 없다"는 결론이 실제 전략 한계인지, 데이터 입력 결함 때문에 그렇게 보이는지 먼저 나누는 것이다.

**Independent Test**: 현재 스타일의 `public-data` summary와 `regime.json` 입력을 주면 보고서가 CPI 미발행, 교차검증 생략, inflation 레짐 지표 누락을 결정론적으로 분류하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `public-data` summary에 `bls:CUUR0000SA0` 미발행과 CPI 교차검증 생략이 있음, **When** 보고서를 생성하면, **Then** 데이터 결측 항목을 `GAP_DETECTED`로 표시하고 원인과 영향 범위를 함께 발행한다.
2. **Given** `regime.json`에서 `inflation` 지표가 `UNAVAILABLE`임, **When** 보고서를 생성하면, **Then** 해당 지표를 레짐 원인 결측으로 분류하되 실거래 허가로 해석하지 않는다.

---

### User Story 2 - 레짐 타임라인 결측이 NO_EDGE 판정에 끼친 영향을 본다 (Priority: P2)

운영자는 `regime_timeline.csv`와 `regime-stratify`를 함께 보며, 레짐 라벨이 충분히 붙어 있는지, 어떤 열이 비어 있는지, 어떤 레짐의 관측 수가 적어서 no-edge 판정을 약하게 만드는지 확인한다.

**Why this priority**: 공개 데이터 항목 하나가 빠져도 레짐 라벨 전체가 무너졌는지, 아니면 특정 해석만 제한되는지 구분해야 다음 no-live 연구가 정확해진다.

**Independent Test**: timeline에 canonical label 세 가지가 모두 있고 inflation 열이 100% 비어 있으면, 보고서는 레짐 라벨은 사용 가능하지만 inflation 해석은 제한된다고 표시한다.

**Acceptance Scenarios**:

1. **Given** `regime_timeline.csv`에 `RISK_ON`, `CAUTION`, `RISK_OFF` 라벨이 모두 있음, **When** 보고서를 생성하면, **Then** 레짐 라벨 커버리지는 no-edge 판정을 전면 무효화하지 않는다고 표시한다.
2. **Given** `inflation_yoy` 열이 모두 비어 있음, **When** 보고서를 생성하면, **Then** inflation 관련 해석을 `MEDIUM` 영향 결측으로 분류한다.
3. **Given** `regime-stratify`에서 어떤 레짐의 관측 수가 20개 미만임, **When** 보고서를 생성하면, **Then** 해당 레짐은 실패 단정이 아니라 관측 대기로 표시한다.

---

### User Story 3 - 후보 완료 뒤 같은 broad no-edge 후보를 반복하지 않는다 (Priority: P3)

운영자는 이번 데이터 결측 감사 후보가 완료된 뒤 broad no-edge frontier의 네 번째 축까지 닫혔음을 확인하고, 자동 루프가 같은 후보를 다시 고르지 않는지 본다.

**Why this priority**: 완료 후보가 released-work에 소비되지 않으면 다음 세션이 이미 끝낸 감사를 다시 수행하게 된다.

**Independent Test**: released-work 로컬 재현에 `candidate-broad-no-edge-data-gap-audit`가 나타나고, autonomous-work 로컬 재현의 `broad_no_edge_frontier_map`에서 네 축이 모두 `released`이며 selected work가 broad no-edge 후보가 아님을 확인한다.

**Acceptance Scenarios**:

1. **Given** 스펙 133이 완료된 상태, **When** released-work가 스펙을 스캔하면, **Then** `candidate-broad-no-edge-data-gap-audit`가 released 후보로 기록된다.
2. **Given** broad no-edge 네 축이 모두 released됨, **When** autonomous-work 보고서를 생성하면, **Then** `candidate-broad-no-edge-data-gap-audit`를 다시 선택하지 않는다.

### Edge Cases

- `public-data` summary가 없거나 malformed이면 핵심 결측 원인을 분류할 수 없으므로 `BLOCKED` 처리한다.
- `regime_timeline.csv`가 없거나 날짜·라벨 구조가 깨졌으면 `BLOCKED` 처리한다.
- `regime.json`이 없으면 레짐 지표 결측 원인을 알 수 없으므로 `BLOCKED` 처리한다.
- `regime-stratify`가 없거나 stratified JSON이 없으면 no-edge 판정과 레짐 라벨 연결을 확인할 수 없으므로 `BLOCKED` 처리한다.
- canonical label 중 일부가 timeline에 없으면 no-edge 원인 영향도를 `HIGH`로 올리고 관측 대기 상태로 둔다.
- 개별 데이터 항목의 신선도 문제는 전체 no-edge 결론을 자동 무효화하지 않고, 어떤 해석이 제한되는지 별도 impact로 남긴다.
- money-path가 실주문 가능 상태처럼 보이면 이 보고서는 live readiness를 열지 않고 관측 대기로 낮춘다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a deterministic broad no-edge data gap audit report with JSON and Markdown outputs.
- **FR-002**: System MUST consume these required inputs: `automation/public-data:LAST_RUN.md`, `automation/public-data:summary.json`, `automation/public-data:regime.json`, `automation/public-data:regime_timeline.csv`, `automation/regime-stratify-last-run:LAST_RUN.md`, `automation/rebalance-paper-forward-last-run:LAST_RUN.md`, `automation/money-path-last-run:LAST_RUN.md`, `automation/edge-autoarm-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, and `automation/pipeline-liveness-last-run:LAST_RUN.md`.
- **FR-003**: System MUST preserve the no-live safety boundary in the report: no broker API calls, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel change, no fresh external collection, and no paid external services.
- **FR-004**: System MUST summarize public-data item publication with kind, id, ok status, row count, first/last date, missing count, published path, issues, and gap causes.
- **FR-005**: System MUST summarize cross-check status and classify skipped or failed checks as data gap evidence without throwing away passed checks.
- **FR-006**: System MUST summarize regime indicators with status, state, reason, source, and no-edge impact.
- **FR-007**: System MUST summarize regime timeline shape, label counts, date range, missing canonical labels, and per-column missing counts.
- **FR-008**: System MUST parse `regime-stratify` sections and expose section count, total return days, sparse labels, non-forward joins, and label count mismatches.
- **FR-009**: System MUST summarize forward paper rows and separate `NO_EDGE` verdict evidence from data gap evidence.
- **FR-010**: System MUST emit causal findings that distinguish `LOW`, `MEDIUM`, `HIGH`, and `UNKNOWN` impact on no-edge interpretation.
- **FR-011**: System MUST classify the report as `CONTRACT_READY` when required evidence is present and parseable, no-live safety is preserved, timeline labels are usable, and causal findings are emitted.
- **FR-012**: System MUST classify the report as `OBSERVATION_WAIT` when evidence is parseable but important label or liveness coverage is incomplete.
- **FR-013**: System MUST classify the report as `BLOCKED` when critical public-data, regime, timeline, stratify, money, edge, released-work, forward, or liveness evidence is missing or malformed.
- **FR-014**: System MUST include validation gates for input evidence, public-data gap classification, regime indicator coverage, timeline label coverage, stratified join coverage, forward no-edge context, money gate alignment, pipeline liveness, and released-work closure.
- **FR-015**: System MUST mark this work's completed candidate as `candidate-broad-no-edge-data-gap-audit`.
- **FR-016**: System MUST identify `wait-for-fresh-evidence` as the next state after this broad no-edge audit is released.
- **FR-017**: System MUST NOT modify constitution, kernel, order routing, capital ladder, auto-reassign gates, live config, broker integrations, secrets, whitelist/caps, or deployment guard behavior.

### Key Entities *(include if feature involves data)*

- **Data Gap Audit Report**: Top-level JSON/Markdown artifact that records status, evidence, data gaps, timeline gaps, stratified join quality, causal findings, gates, and safety boundary.
- **Evidence Surface**: One consumed sidecar with presence, parse status, source ref, and extracted summary.
- **Public Data Item Gap**: One public-data item with publication status, row coverage, missing observations, issue text, gap causes, and no-edge impact.
- **Cross Check Gap**: One public-data cross-check with status, overlap, detail, and gap cause.
- **Regime Indicator Gap**: One `regime.json` indicator with status, state, reason, source, and impact.
- **Timeline Gap Summary**: CSV-derived label and column missingness summary.
- **Stratified Join Summary**: `regime-stratify` section summary for forward join quality and sparse labels.
- **Forward No Edge Summary**: Forward paper rows and no-edge verdict counts used to separate data and strategy evidence.
- **Causal Finding**: One deterministic conclusion about whether a data gap likely invalidates, limits, or does not materially explain the no-edge verdict.
- **Validation Gate**: A named pass/wait/fail item explaining whether the report can be used.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-broad-no-edge-data-gap-audit`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Probe manifest lists all ten required sidecars with stable keys and refs.
- **SC-002**: With current-style sidecars, JSON output includes `audit_id`, `overall_status`, `public_data_gaps`, `cross_check_gaps`, `regime_indicator_gaps`, `timeline_gap_summary`, `stratified_join_summary`, `forward_no_edge_summary`, `causal_findings`, `validation_gates`, `money_state`, `edge_autoarm_state`, and `safety_boundary`.
- **SC-003**: Current-style evidence classifies CPI publication and inflation regime gaps while preserving treasury and VIX ready evidence.
- **SC-004**: Current-style timeline evidence reports all three canonical labels and column missingness, including `inflation_yoy` at 100% missing.
- **SC-005**: Missing or malformed critical evidence produces `BLOCKED` and a failing validation gate.
- **SC-006**: Focused unit and integration tests for the new report and probe pass.
- **SC-007**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.
- **SC-008**: After completion marker is scanned, autonomous-work local replay marks all broad no-edge frontier entries released and no longer selects `candidate-broad-no-edge-data-gap-audit`.

## Assumptions

- `public-data` is the authoritative research-only source for this audit; the report must not fetch fresh external data.
- Missing CPI and inflation fields limit inflation-sensitive interpretation, but do not automatically prove the whole no-edge verdict is false.
- Regime labels remain usable when canonical labels are present and joined stratified returns are parseable.
- A sparse `RISK_OFF` stratified sample is a wait condition, not a failed strategy conclusion.
- This feature is risk grade 2 because it changes operating reporting and candidate closure, while leaving the money path and safety perimeter unchanged.
