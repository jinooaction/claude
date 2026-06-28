# Feature Specification: Autonomous Evolution Loop

**Feature Branch**: `Codex/autonomous-evolution-loop`
**Created**: 2026-06-28
**Status**: Draft
**Input**: User description: "데이터 수집, 데이터 분석, 전략 설계, 포트폴리오 설계, 실시간 매매, 회고 등 모든 분야에서 세계 최고 수준이 될 수 있게 계속 자동 자율 고도화하고 싶다. 기다리는 시간이 아까우니 자동 루프로 설계해서 스스로 진화하게 하고 싶다." Clarification: this is not a waiting-time-only loop. The goal is a permanent autonomous growth engine that starts now and continuously compounds profit capacity, evidence quality, capital-path readiness, safety, and learning speed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 전 영역 고레버리지 돌파 후보를 자동으로 발굴한다 (Priority: P1)

운영자는 지금부터 영구적으로 데이터 수집·데이터 품질·분석·전략 연구·포트폴리오 구성·실행 품질·실시간 매매 상태·회고·에이전트 운영 품질 전 영역에서 돈 버는 능력과 검증 능력을 가장 크게 키울 고레버리지 돌파 후보를 스스로 찾아 우선순위화하기를 원한다.

**Why this priority**: 자동 고도화의 첫 단계는 "무엇을 개선할지"를 매번 사람이 다시 찾지 않게 만드는 것이 아니라, 장기 수익력·증거 품질·자본 연결성·안전성·학습 속도를 가장 크게 복리화할 돌파 과제를 계속 찾는 것이다. 후보 발굴이 없으면 실험·승격 루프가 시작되지 않는다.

**Independent Test**: 최신 자동화 사이드카, `HANDOFF.md`, 출시된 스펙, 최근 실행 결과를 입력으로 주면 시스템이 영역별 돌파 후보와 근거, 위험 등급, 성장 레버리지, 자본 경로 정렬도, 증거 의존성, 다음 행동을 포함한 후보 목록을 산출한다.

**Acceptance Scenarios**:

1. **Given** 최신 money-path가 `PREVIEW_ONLY`이고 micro GTAA가 `latest_intent_loss`로 차단됨, **When** 자율 고도화 스캔이 실행됨, **Then** 후보 목록은 "실주문 재개"가 아니라 "전략 증거 재검토 또는 대체 후보 연구"처럼 돈 경로를 안전하게 다시 열 가능성이 큰 돌파 후보를 상위 후보로 표시한다.
2. **Given** 특정 사이드카가 오래됐거나 누락됨, **When** 스캔이 실행됨, **Then** 시스템은 그 영역을 돌파 후보가 아니라 관측 불능 또는 생존 감시 이슈로 분리한다.
3. **Given** 후보가 자본 증액, 허용 종목 확대, 주문 제한 완화, live 전략 교체를 요구함, **When** 후보를 분류함, **Then** 자동 실행 후보가 아니라 안전 경계 또는 돈 경로 검토 후보로 표시한다.

---

### User Story 2 - 돌파 후보를 안전한 실험으로 바꾼다 (Priority: P1)

운영자는 좋은 아이디어가 대화로 사라지지 않고, 자동 루프가 각 돌파 후보를 작은 실험으로 쪼개고 재현 가능한 성공 기준을 붙이기를 원한다.

**Why this priority**: "세계 최고 수준"은 선언이 아니라 반복 가능한 실험과 폐기 기준으로만 가까워진다. 실험 설계가 없으면 자동 개선은 추측 기반 변경이 된다.

**Independent Test**: 후보 하나를 선택하면 시스템이 비목표, 안전 경계, 필요한 데이터, 성공 지표, 실패 시 폐기 조건, 필요한 스펙 또는 코드 변경 범위를 포함한 실험 계획을 생성한다.

**Acceptance Scenarios**:

1. **Given** 후보가 "새 비상관 전략 연구"임, **When** 실험 계획을 생성함, **Then** 계획은 백테스트·전진 검증·상관 측정·비교 기준을 포함하고, 실거래 또는 자본 변경은 비목표로 둔다.
2. **Given** 후보가 "실행 품질 개선"임, **When** 계획을 생성함, **Then** 계획은 거부 주문 기회손익, 체결 품질, 브로커 오류율 같은 기존 관측면을 활용한다.
3. **Given** 후보가 단일 표본 또는 최근 한 번의 실패에만 근거함, **When** 실험 계획을 생성함, **Then** 계획은 즉시 변경이 아니라 추가 관측 또는 낮은 신뢰도 실험으로 분류한다.

---

### User Story 3 - 검증된 돌파 후보만 기존 안전 게이트로 승격한다 (Priority: P1)

운영자는 자동 루프가 증거를 충분히 쌓으면 다음 단계로 밀어 올리되, 기존 안전 게이트와 돈 경로를 우회하지 않기를 원한다.

**Why this priority**: 자율 고도화는 실제 돈을 벌기 위한 속도를 높여야 하지만, 안전장치를 넘는 자동 권한 확대가 되면 시스템의 생존성이 깨진다.

**Independent Test**: 충분한 증거를 가진 개선 후보와 부족한 후보를 함께 넣으면, 시스템은 충분한 후보만 기존 스펙·풀 리퀘스트·전진 토너먼트·재지정 루프·자본 사다리 입력으로 보낼 수 있고, 안전 경계 후보는 운영자 승인 대기로 둔다.

**Acceptance Scenarios**:

1. **Given** 후보가 실험에서 사전 선언한 기준을 충족함, **When** 승격 판단을 실행함, **Then** 시스템은 새 구현 작업 또는 기존 자동화 입력으로 승격하고 증거 패키지를 남긴다.
2. **Given** 후보가 live 전략 교체를 요구함, **When** 승격 판단을 실행함, **Then** 시스템은 스펙 055의 5중 재지정 게이트를 우회하지 않는다.
3. **Given** 후보가 자본 배분 확대를 요구함, **When** 승격 판단을 실행함, **Then** 시스템은 스펙 050 자본 사다리와 운영자 소유 낙폭 예산 밖에서 자본을 늘리지 않는다.

---

### User Story 4 - 루프의 학습 기록과 정지 상태를 남긴다 (Priority: P2)

운영자는 다음 세션이 같은 사실을 다시 조사하지 않고, 어떤 후보가 채택·보류·폐기됐는지와 왜 그런지 바로 알기를 원한다.

**Why this priority**: 자동 고도화가 오래 지속되려면 개선보다 중요한 것이 기억이다. 폐기한 아이디어가 다시 등장하거나, 오래된 상태를 최신처럼 해석하면 시간이 낭비된다.

**Independent Test**: 여러 후보의 상태 변경을 입력으로 주면 시스템은 후보별 증거, 결정, 다음 조건, 재검토 예정 시점, 안전 경계 판정을 포함한 학습 기록과 최신 실행 사이드카를 생성한다.

**Acceptance Scenarios**:

1. **Given** 후보가 실패 기준을 만족함, **When** 회고를 생성함, **Then** 후보는 폐기 또는 보류로 기록되고 재시도 조건이 명시된다.
2. **Given** 후보가 성공했지만 안전 경계를 건드림, **When** 회고를 생성함, **Then** 성공 증거와 별도로 운영자 승인 필요 상태가 남는다.
3. **Given** 자율 고도화 루프 자체가 일정 기간 실행되지 않음, **When** 생존 감시가 평가함, **Then** 루프 정지는 돈 경로 변경 없이 명확히 드러난다.

### Edge Cases

- 최신 사이드카가 이전 코드로 생성되어 현재 코드의 판정과 다를 수 있다.
- 자동화 사이드카가 누락되거나 손상되어 후보 근거를 재현할 수 없다.
- 단기 성과가 좋아 보이지만 표본 수가 부족하거나 여러 후보 중 운 좋은 결과일 수 있다.
- 개선 후보가 실거래 재무장, 자본 증액, 허용 종목 확대, 포지션 한도 완화, 주문 제한 완화를 요구할 수 있다.
- 외부 데이터 수집 실패 또는 브로커 장애가 전략 실패처럼 보일 수 있다.
- LLM이 생성한 연구 아이디어가 그럴듯하지만 기존 스펙, 헌법, 안전 경계와 충돌할 수 있다.
- 자동 루프가 같은 실패 후보를 반복 재발굴할 수 있다.
- 비용이 있는 외부 서비스나 유료 데이터 사용이 필요한 후보가 나올 수 있다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST maintain a domain map covering at least data collection, data quality, analysis, strategy design, portfolio design, execution quality, live trading readiness, post-trade review, operator reporting, and agent operating quality.
- **FR-002**: System MUST scan current evidence surfaces before proposing improvements: latest handoff, released specs, automation sidecars, money-path status, reassignment status, pipeline liveness, tests, and recent known blockers.
- **FR-003**: System MUST create breakthrough candidates with domain, evidence, expected benefit, growth leverage, capability compounding value, capital-path alignment, risk grade, safety boundary impact, confidence, required next action, evidence dependency, and expiry or recheck condition.
- **FR-004**: System MUST deterministically score and order candidates by expected long-term profit capacity, evidence confidence, capital-path alignment, safety preservation, learning velocity, repeatability, and compounding/reuse value.
- **FR-005**: System MUST distinguish evidence gaps from breakthrough opportunities. Missing or stale evidence cannot be treated as proof that a strategy or execution path is bad.
- **FR-006**: System MUST convert selected candidates into bounded experiments with declared goal, non-goal, required data, success metrics, failure criteria, rollback or discard path, and affected safety surfaces.
- **FR-007**: System MUST require every experiment that can affect trading behavior to begin read-only, backtest, paper, or canary before any live-money effect.
- **FR-008**: System MUST prohibit the evolution loop from directly placing, retrying, canceling, or modifying broker orders.
- **FR-009**: System MUST prohibit the evolution loop from directly increasing capital, widening position caps, widening whitelists, changing account allowlists, or enabling real-order mode outside existing safety gates.
- **FR-010**: System MUST route strategy replacement only through the existing autonomous reassignment gate and MUST NOT create a parallel live strategy swap path.
- **FR-011**: System MUST route capital scaling only through the existing capital ladder and MUST NOT create a parallel capital allocation path.
- **FR-012**: System MUST classify candidates that touch constitution, kernel, order limits, audit, secrets, deployment restrictions, external paid services, or live-money authority as safety-boundary review items.
- **FR-013**: System MUST produce an evidence package before any candidate is promoted. The package must include source evidence, experiment results, comparison baseline, known limitations, safety review, and next gate.
- **FR-014**: System MUST maintain a learning ledger of accepted, rejected, expired, and evidence-dependent candidates so future sessions do not rediscover the same conclusion without new evidence.
- **FR-015**: System MUST publish a latest-run summary for the evolution loop that identifies highest-leverage breakthrough candidates, evidence-dependent candidates, stale evidence, and safety-boundary items.
- **FR-016**: System MUST expose loop health to pipeline liveness monitoring so a silent stop is visible without moving money.
- **FR-017**: System MUST mask secrets and account-sensitive values in all reports, prompts, sidecars, and handoff-ready summaries.
- **FR-018**: System MUST keep operator-facing summaries in Korean while preserving code identifiers, commit hashes, workflow names, and spec IDs.
- **FR-019**: System MUST record real market observation time as one evidence dependency when relevant, but the permanent evolution loop must continue selecting other high-leverage safe work instead of treating waiting time as the loop's purpose.

### Key Entities *(include if feature involves data)*

- **Evolution Domain**: One improvement area such as data collection, strategy research, portfolio construction, execution, live readiness, review, or agent operations.
- **Evidence Surface**: A current source used for decisions, such as a sidecar, handoff row, spec finding, test result, or live-money state summary.
- **Breakthrough Candidate**: A proposed high-leverage improvement with domain, evidence, expected benefit, growth leverage, capability compounding value, capital-path alignment, confidence, risk grade, safety impact, next action, evidence dependency, and expiry condition.
- **Experiment Plan**: A bounded plan that turns a candidate into measurable work with success and failure criteria.
- **Evidence Package**: The artifact produced after an experiment, containing results, baselines, limitations, and safety review.
- **Promotion Decision**: A decision to discard, keep observing, create a spec, open an implementation PR, feed existing gates, or require operator approval.
- **Learning Ledger**: Durable record of candidate lifecycle and decisions.
- **Evolution Run Summary**: Latest-run report for operators and future sessions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a fixed set of evidence inputs, the system produces the same ordered candidate list and safety classifications on repeated runs.
- **SC-002**: 100% of candidates that require orders, capital increase, whitelist expansion, cap relaxation, live strategy swap, secret handling change, or paid external service use are classified as safety-boundary or operator-review items.
- **SC-003**: The top candidate report covers at least eight configured domains and includes a concrete next action for each non-empty domain.
- **SC-004**: Every promoted candidate has an evidence package with success criteria, baseline comparison, limitations, and the next gate before implementation or gate submission.
- **SC-005**: The learning ledger prevents a previously rejected candidate from returning to active status unless new evidence or an explicit recheck condition is present.
- **SC-006**: Latest-run summaries allow a new session to identify within five minutes the top breakthrough candidate, the top evidence-dependency item, and any safety-boundary item.
- **SC-007**: The loop can run in read-only mode without broker access, without secrets, and without modifying trading configuration.
- **SC-008**: Full repository tests, lint, handoff fact check, and strict agent harness pass before any implementation PR for this feature is merged.

## Assumptions

- The first implementation slice is read-only: it scans evidence, ranks candidates, writes reports, and opens no live-money path.
- Existing autonomous tuner, reassignment, capital ladder, money-path state, opportunity feedback, and pipeline liveness features remain the authority for their own domains.
- "World-class" is treated as a measurable operating direction: faster safe discovery, better evidence quality, fewer repeated investigations, stricter gate preservation, and higher-quality promoted experiments. It is not a guarantee of profit.
- Real market observation time is only one possible evidence dependency. The permanent loop should keep running regardless of waiting, selecting high-leverage safe work across research, backtests, data-quality checks, experiment design, execution quality, review, and agent operations.
- Any future step that changes safety boundaries or money paths will require the risk grade and SDD thickness defined in `AGENTS.md`.
