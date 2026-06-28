# Feature Specification: Autonomous Promotion Loop

**Feature Branch**: `Codex/autonomous-promotion-loop`  
**Created**: 2026-06-29  
**Status**: Draft  
**Input**: User description: "승격 루프도 자동화하자. 새 전략은 과거 데이터를 세계 최고 수준으로 백테스트하면 충분한 것 아닌가? 최근 30일 백테스트와 앞으로 30일 소액 실거래 검증이 사실상 같은 효과인지 이해가 안 된다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 성장 후보를 검증 단계로 자동 분류한다 (Priority: P1)

운영자는 자율 성장 루프가 만든 후보가 대화나 보고서에서 멈추지 않고, 백테스트·최근 표본외 검증·forward paper·캐너리 후보·기존 돈 게이트 중 어디로 가야 하는지 자동으로 분류되기를 원한다.

**Why this priority**: 후보 발굴만으로는 돈 버는 능력이 커지지 않는다. 후보를 다음 검증 단계로 자동 배치해야 연구 시간이 실행 가능한 증거로 바뀐다.

**Independent Test**: `candidate_backlog.json`, `evolution_summary.json`, 기존 money-path/reassign/forward sidecar를 입력하면 각 후보별 현재 승격 단계, 다음 필요 증거, 차단 이유, 허용 가능한 다음 행동이 결정론적으로 산출된다.

**Acceptance Scenarios**:

1. **Given** 후보가 새 전략 연구이고 아직 evidence package가 없음, **When** 승격 스캔을 실행함, **Then** 후보는 `BACKTEST_REQUIRED`로 분류되고 live 주문이나 자본 변경은 금지된다.
2. **Given** 후보가 백테스트 통과 증거는 있지만 forward 관측이 없음, **When** 승격 스캔을 실행함, **Then** 후보는 `FORWARD_REGISTRATION_READY` 또는 `FORWARD_ACCUMULATING`으로 분류되고 캐너리나 자본 사다리로 바로 가지 않는다.
3. **Given** 후보가 live 전략 교체 또는 자본 확대를 요구함, **When** 승격 스캔을 실행함, **Then** 후보는 기존 스펙 055 재지정 게이트 또는 스펙 050 자본 사다리로만 라우팅된다.

---

### User Story 2 - 백테스트와 소액 실거래의 역할을 분리한다 (Priority: P1)

운영자는 세계 최고 수준의 백테스트를 적극 활용하되, 백테스트가 실제 브로커·계좌·주문·체결 문제를 검증했다고 오해하지 않기를 원한다.

**Why this priority**: 백테스트는 전략 논리와 과최적화 위험을 줄이는 핵심 필터다. 그러나 실제 주문 경로 검증을 대체한다고 보면 검증되지 않은 실행 위험이 실계좌로 들어간다.

**Independent Test**: 백테스트 통과 후보를 넣으면 시스템은 전략 논리 검증 완료와 실행 경로 미검증을 별도 필드로 표시하고, 소액 live canary 전에는 "실제 브로커 검증 완료"라고 표시하지 않는다.

**Acceptance Scenarios**:

1. **Given** 후보가 과거·최근 표본외·walk-forward 백테스트를 모두 통과함, **When** 승격 판단을 실행함, **Then** 결과는 "전략 검증은 통과, 브로커 실행 검증은 미완료"로 표시한다.
2. **Given** 후보가 forward paper 관측을 충분히 쌓아 `EDGE_CONFIRMED`임, **When** 승격 판단을 실행함, **Then** 결과는 캐너리 후보 제출 가능으로 표시하되 실주문 실행 자체는 하지 않는다.
3. **Given** 후보가 실제 브로커에서 주문 거부·미체결·현금 부족·계좌 보유 충돌을 아직 겪어보지 않음, **When** 보고서를 생성함, **Then** 소액 실거래 검증의 남은 이유를 쉬운 한글로 설명한다.

---

### User Story 3 - 자동 승격 sidecar를 발행하고 생존 감시에 등록한다 (Priority: P2)

운영자는 다음 세션이 최신 승격 상태를 다시 계산하지 않고도, 어떤 후보가 어디까지 올라왔고 무엇이 남았는지 한 파일로 확인하기를 원한다.

**Why this priority**: 승격 루프가 조용히 멈추면 후보 발굴과 돈 경로 사이가 다시 끊긴다. 최신 실행 sidecar와 생존 감시가 있어야 다음 세션이 같은 일을 반복하지 않는다.

**Independent Test**: 스캔을 실행하면 `LAST_RUN.md`, `promotion_summary.json`, `promotion_queue.json`이 생성되고, pipeline liveness registry가 `autonomous-promotion` sidecar를 감시한다.

**Acceptance Scenarios**:

1. **Given** 최신 후보와 증거가 있음, **When** 승격 루프 workflow가 실행됨, **Then** 사람이 읽는 한국어 요약과 기계 판독 JSON이 sidecar branch에 발행된다.
2. **Given** 후보 증거가 누락됨, **When** 승격 루프가 실행됨, **Then** 누락을 전략 실패로 보지 않고 `EVIDENCE_MISSING` 또는 `OBSERVE`로 분류한다.
3. **Given** 승격 루프 sidecar가 오래됨, **When** pipeline liveness가 실행됨, **Then** 돈 이동 없이 연구/승격 가시성 저하로 드러난다.

### Edge Cases

- 자율 성장 후보가 안전 경계나 돈 경로 변경을 요구한다.
- candidate backlog가 없거나 손상되었다.
- 백테스트 통과 증거는 있으나 사용한 데이터가 후보 설계에 이미 노출된 데이터일 수 있다.
- 최근 30일 백테스트는 통과했지만 앞으로의 forward paper 또는 live canary가 아직 없다.
- forward sidecar가 이전 코드로 생성되어 현재 판정 규칙과 다를 수 있다.
- 소액 실거래 중 브로커 주문 거부, 미체결, 현금 부족, whitelist 거부, caps 거부가 발생할 수 있다.
- 유료 데이터나 새 외부 서비스가 필요한 후보가 나올 수 있다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read autonomous-evolution `candidate_backlog.json`, `evolution_summary.json`, and existing money-path/reassign/forward sidecars without calling broker APIs.
- **FR-002**: System MUST produce a deterministic promotion stage per candidate: `EVIDENCE_MISSING`, `BACKTEST_REQUIRED`, `RECENT_OOS_REQUIRED`, `FORWARD_REGISTRATION_READY`, `FORWARD_ACCUMULATING`, `CANARY_CANDIDATE`, `EXISTING_GATE_READY`, `OPERATOR_REVIEW`, or `DISCARD`.
- **FR-003**: System MUST distinguish strategy validation status from execution validation status.
- **FR-004**: System MUST treat historical backtest, recent out-of-sample test, walk-forward, forward paper, and small live canary as separate evidence layers.
- **FR-005**: System MUST NOT mark broker execution validation complete until small live canary or existing live evidence has observed real broker order path behavior.
- **FR-006**: System MUST explain in Korean why a world-class backtest cannot validate broker rejection, partial fills, cash settlement, order timing, live account holdings, API failures, audit/reconciliation, or live slippage.
- **FR-007**: System MUST route strategy reassignment only to existing spec 055 gates and capital scaling only to existing spec 050 gates.
- **FR-008**: System MUST NOT place, retry, cancel, or modify real broker orders.
- **FR-009**: System MUST NOT increase capital, widen whitelist, relax caps, change account allowlists, change live strategy files, or arm real-order sentinels.
- **FR-010**: System MUST classify any candidate touching safety boundary, paid external services, secrets, kernel, order limits, live authority, whitelist, caps, or capital as operator review or existing-gate-only.
- **FR-011**: System MUST produce `promotion_summary.json`, `promotion_queue.json`, and Korean `LAST_RUN.md` artifacts.
- **FR-012**: System MUST expose the promotion loop in pipeline liveness as a non-critical visibility loop.
- **FR-013**: System MUST mask secrets and account-sensitive values in all outputs.
- **FR-014**: System MUST run without secrets and without network access to broker services.

### Key Entities *(include if feature involves data)*

- **Promotion Candidate**: A growth candidate with source evidence, risk, safety impact, and current verification state.
- **Evidence Layer**: A distinct verification layer: historical backtest, recent OOS, walk-forward, forward paper, small live canary, or existing gate evidence.
- **Promotion Stage**: The current stage and next required proof for a candidate.
- **Promotion Queue**: Ordered list of candidates and allowed next actions.
- **Promotion Run Summary**: Latest run report for operator and next sessions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given fixed candidate backlog and sidecar evidence, repeated runs produce identical promotion stages and queue order.
- **SC-002**: 100% of candidates with only backtest evidence are blocked from `EXISTING_GATE_READY` and `CANARY_CANDIDATE` until forward or canary evidence exists.
- **SC-003**: 100% of strategy-swap and capital-scaling candidates route to spec 055 or spec 050, never to a new direct money path.
- **SC-004**: Latest-run summary explains the backtest-vs-canary distinction in Korean without requiring the operator to infer it from identifiers.
- **SC-005**: The loop runs in read-only mode with no broker secrets and publishes all three artifacts.
- **SC-006**: Focused unit/integration tests, full tests, lint, HANDOFF fact check, strict harness, and PR quality gate pass before merge.

## Assumptions

- First implementation is read-only and does not create PRs that modify live portfolios or sentinels.
- Existing capital ladder, reassignment, money-path, and canary workflows remain the only authority for real-money effects.
- Backtests should be made stronger over time, but no backtest can verify live broker execution behavior by itself.
- The promotion loop may later grow into automatic forward-track registration, but that will still be paper-only unless a separate spec safely wires config generation.
