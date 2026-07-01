# Feature Specification: Capital Path Readiness Loop

**Feature Branch**: `Codex/076-capital-path-readiness-loop`  
**Created**: 2026-07-01  
**Status**: Draft  
**Input**: User description: "돈을 더 많이 벌기 위해, money-path·edge-autoarm·reassign·forward 토너먼트·KIS smoke·promotion/evolution sidecar를 읽어 자본 투입 준비도와 다음 안전 행동을 자동 산출하는 루프 시스템으로 확장한다. 실제 주문, 실거래 전환, 자본 배분, 브로커 주문 경로, whitelist/caps/live 설정, 헌법/커널은 변경하지 않는다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 자본 경로 준비도를 단일 루프가 판정 (Priority: P1)

운영자는 돈을 더 벌기 위해 지금 자본 투입이 가능한지, 아니면 어떤 기존 게이트가 아직 부족한지 한 곳에서 알고 싶다.

**Why this priority**: 현재 `money-path`, `edge-autoarm`, `reassign`, forward 토너먼트, KIS smoke, promotion/evolution 결과가 흩어져 있어 다음 돈 행동을 사람이 다시 합쳐 판단해야 한다.

**Independent Test**: 최신 sidecar 텍스트와 JSON을 모사한 입력으로 readiness scan을 실행했을 때 `readiness_state`, `blocking_gate`, `next_action_ko`, `required_existing_gates`가 JSON과 Markdown에 함께 출력되면 검증된다.

**Acceptance Scenarios**:

1. **Given** money-path가 `ACCUMULATING_EDGE`와 전진 관측 부족을 보고함, **When** readiness loop가 실행됨, **Then** readiness state는 `ACCUMULATING_EDGE`이고 다음 행동은 기존 전진 관측/자본 사다리 게이트를 기다리는 것으로 표시된다.
2. **Given** live money state가 `PREVIEW_ONLY`임, **When** readiness loop가 실행됨, **Then** 실주문 불가와 남은 기존 게이트가 명확히 분리되어 표시된다.

---

### User Story 2 - 실패 후보와 돈 경로 후보를 함께 반영 (Priority: P2)

운영자는 이미 실패로 학습된 전략/포트폴리오 후보를 다시 돈 경로 준비 후보처럼 보지 않고, 실제 돈 경로에 가까운 후보만 다음 행동으로 보고 싶다.

**Why this priority**: 실패 후보를 다시 붙잡으면 수익력 개선보다 반복 검증 비용이 커진다.

**Independent Test**: evolution learning ledger에 `rejected` 후보가 있고 candidate backlog에 `live_readiness` 후보가 있을 때 readiness output이 실패 후보를 `suppressed_candidates`에 넣고 `live_readiness` 후보를 `priority_candidates`에 넣으면 검증된다.

**Acceptance Scenarios**:

1. **Given** learning ledger에 `candidate-1ed634d8bf6d` rejected entry가 있음, **When** readiness loop가 실행됨, **Then** 해당 후보는 돈 경로 승격 대상으로 출력되지 않는다.
2. **Given** candidate backlog에 `candidate-fd04772a23c5` live readiness 후보가 있음, **When** readiness loop가 실행됨, **Then** 해당 후보는 돈 경로 증거 패키지 후보로 출력된다.

---

### User Story 3 - 자동화 sidecar로 지속 발행 (Priority: P3)

운영자는 이 판단이 대화 안에서만 끝나지 않고 매일 자동 실행되어 다음 루프들이 소비할 수 있기를 원한다.

**Why this priority**: 루프 시스템은 실행 결과가 sidecar로 남아야 다음 세션과 promotion/evolution 계층이 같은 사실을 반복 조사하지 않는다.

**Independent Test**: workflow manifest가 필요한 sidecar들을 수집하고, probe가 `LAST_RUN.md`와 `capital_path_readiness.json`을 생성하며, pipeline liveness가 새 sidecar를 감시 목록에 포함하면 검증된다.

**Acceptance Scenarios**:

1. **Given** automation sidecar refs가 존재함, **When** capital-path readiness workflow가 실행됨, **Then** `automation/capital-path-readiness-last-run`에 Markdown과 JSON 산출물이 발행된다.
2. **Given** 일부 비핵심 sidecar가 누락됨, **When** workflow가 실행됨, **Then** 보고서는 `UNKNOWN` 또는 `MISSING_EVIDENCE`를 표시하되 주문·자본·live 설정 변경 없이 종료한다.

### Edge Cases

- money-path 결정 JSON이 누락되면 readiness state는 `UNKNOWN`이 되고 실주문 가능으로 오판하지 않는다.
- live money state가 `BLOCKED`이면 readiness state는 `LIVE_BLOCKED`가 되고 자동 승격 후보로 쓰지 않는다.
- rejected learning ledger 후보는 priority candidate에서 제외한다.
- KIS smoke가 오래되거나 누락되어도 이 루프는 브로커를 직접 호출하지 않고 누락 증거로 기록한다.
- sidecar 문서가 malformed JSON을 포함하면 해당 입력만 누락 처리하고 전체 보고서는 발행한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST collect read-only sidecars for money-path, edge-autoarm, reassign, rebalance-paper-forward, KIS smoke, autonomous promotion, autonomous evolution candidate backlog, and autonomous evolution learning ledger.
- **FR-002**: System MUST produce a machine-readable readiness JSON with `readiness_state`, `live_money_status`, `capital_ladder_stage`, `blocking_gate`, `next_action_ko`, `required_existing_gates`, `priority_candidates`, and `suppressed_candidates`.
- **FR-003**: System MUST produce an operator-readable Markdown summary with the same core facts as the JSON.
- **FR-004**: System MUST derive readiness only from already-published sidecars and local repo files; it MUST NOT call broker APIs, KIS APIs, SSH, order commands, capital mutation commands, whitelist/caps mutation, or live strategy mutation.
- **FR-005**: System MUST keep `Backtest -> Canary -> Full` intact by routing readiness outcomes to existing gates rather than introducing a new order or capital path.
- **FR-006**: System MUST classify rejected learning ledger candidates as suppressed and exclude them from priority money-path candidates.
- **FR-007**: System MUST expose live readiness candidates from evolution backlog as priority candidates when they are not rejected.
- **FR-008**: System MUST publish the readiness sidecar and register it in pipeline liveness so stale readiness is visible.
- **FR-009**: System MUST fail open for missing noncritical inputs but fail closed for money-path absence by refusing to state that capital is ready.

### Key Entities *(include if feature involves data)*

- **Capital Path Readiness Report**: Single read-only decision surface that states the current capital readiness, blocking gate, next action, and source evidence.
- **Readiness Evidence Surface**: One consumed sidecar or JSON artifact with key, source ref, presence, and parse status.
- **Readiness Candidate**: Candidate from autonomous evolution that may affect capital readiness, including live readiness, execution quality, data quality, or rejected strategy/portfolio candidates.
- **Suppressed Candidate**: Candidate with a rejected learning ledger entry that must not be treated as an active money-path opportunity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With current-style sidecars showing `ACCUMULATING_EDGE` and `PREVIEW_ONLY`, readiness JSON states `readiness_state=ACCUMULATING_EDGE`, `live_money_status=PREVIEW_ONLY`, and contains a non-empty blocking gate.
- **SC-002**: With rejected ledger entries for two strategy/portfolio candidates, readiness JSON excludes them from priority candidates and includes them in suppressed candidates.
- **SC-003**: The workflow manifest includes every required sidecar source and the workflow publishes both `LAST_RUN.md` and `capital_path_readiness.json`.
- **SC-004**: Pipeline liveness manifest includes the new capital-path readiness sidecar.
- **SC-005**: Full repository tests and lint pass before merge, with focused unit and integration tests for the new loop.

## Assumptions

- `money-path` remains the source of truth for current live money state and capital ladder stage.
- `autonomous-evolution` remains the source of truth for candidate backlog and learning ledger.
- This feature is a reporting and routing loop only; any future capital movement must still happen through existing capital ladder, live canary, and reassignment gates.
- The new sidecar is noncritical for direct money safety at launch, but it must be monitored so stale readiness does not mislead future sessions.
