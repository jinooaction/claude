# Feature Specification: Candidate Implementation Factory

**Feature Branch**: `Codex/candidate-implementation-factory`  
**Created**: 2026-06-29  
**Status**: Draft  
**Input**: User description: "모든 후보 구현해볼까? 목표 스킬 사용해보면 어때?"

## User Scenarios & Testing

### User Story 1 - BACKTEST_REQUIRED 후보를 실행 패키지로 변환 (Priority: P1)

자율 성장 루프가 만든 후보가 `BACKTEST_REQUIRED`에 멈춰 있으면, 사람이 다시 해석하지 않아도 후보별 검증 패키지와 실행 명령, 필요한 데이터, 승격 차단 사유가 자동으로 만들어진다.

**Why this priority**: 후보 발굴과 승격 판단은 이미 자동화됐지만, 현재 모든 후보가 검증 패키지 부재로 정체된다. 이 간극이 남아 있으면 자율 루프는 보고서만 만들고 실제 성장 행동으로 이어지지 못한다.

**Independent Test**: fixture 후보 9개를 넣으면 각 후보가 정확히 하나의 implementation package를 얻고, 지원 불가 후보도 누락 없이 `blocked` 또는 `pending` 상태와 이유를 갖는다.

**Acceptance Scenarios**:

1. **Given** candidate backlog에 `BACKTEST_REQUIRED` 후보가 있음, **When** factory가 실행됨, **Then** 후보별 `package_id`, `package_kind`, `commands`, `required_inputs`, `promotion_patch`가 생성된다.
2. **Given** 후보가 전략 또는 포트폴리오 검증 후보임, **When** factory가 실행됨, **Then** 기존 `auto-invest portfolio-walk-forward` 또는 관련 검증 도구를 사용하는 실행 계획이 만들어진다.
3. **Given** 후보가 운영, 데이터, 회고 후보임, **When** factory가 실행됨, **Then** 전략 백테스트를 허위 통과시키지 않고 해당 후보에 맞는 읽기 전용 검증 패키지와 차단 사유를 남긴다.

---

### User Story 2 - 실제 증거가 있을 때 promotion_evidence 자동 보강 (Priority: P2)

검증 결과가 기계 판독 가능한 형태로 주어지면 factory는 후보의 `promotion_evidence`를 보강해, 전략 검증을 실제로 통과한 후보만 다음 승격 루프가 forward 등록 후보로 볼 수 있게 한다.

**Why this priority**: 백테스트, 최근 표본외, walk-forward가 통과했다는 증거는 사람이 문장으로 선언하면 안 된다. 증거가 통과 기준을 만족할 때만 승격 루프가 읽는 필드를 채워야 한다.

**Independent Test**: 결과 fixture에 `historical_backtest`, `recent_oos`, `walk_forward`가 모두 통과한 후보를 넣으면 enriched backlog의 해당 후보만 세 필드가 `pass`가 되고, 누락 후보는 `pending`으로 남는다.

**Acceptance Scenarios**:

1. **Given** 검증 결과 JSON에 후보별 통과 결과가 있음, **When** factory가 실행됨, **Then** enriched candidate backlog의 `promotion_evidence`에 통과 상태와 source가 추가된다.
2. **Given** 검증 결과가 없거나 실패함, **When** factory가 실행됨, **Then** `promotion_evidence`는 `pass`로 위조되지 않고 `factory_status`, `factory_block_reason_ko`만 남는다.
3. **Given** 전략 후보가 세 검증을 모두 통과하고 안전 경계 영향이 없음, **When** 다음 promotion scan이 enriched backlog를 읽음, **Then** 기존 promotion loop가 `FORWARD_REGISTRATION_READY`로 분류할 수 있다.

---

### User Story 3 - 승격 루프와 자동 실행 순서에 연결 (Priority: P3)

factory는 자율 성장 루프와 자율 승격 루프 사이에서 매일 실행되고, 결과 sidecar와 enriched backlog를 발행한다. promotion scan은 factory 산출물이 있으면 그것을 우선 사용한다.

**Why this priority**: 자동화가 로컬 명령으로만 있으면 다음날 루프가 또 같은 후보를 `BACKTEST_REQUIRED`로 재발견한다. sidecar와 workflow 순서가 있어야 영구 자율 루프가 된다.

**Independent Test**: workflow 파일은 evolution 이후, promotion scan 이전 시간에 실행되며, promotion loop workflow는 factory enriched backlog를 우선 수집한다.

**Acceptance Scenarios**:

1. **Given** factory sidecar가 존재함, **When** promotion scan workflow가 증거를 수집함, **Then** `candidate_backlog.enriched.json`을 raw evolution backlog보다 우선 사용한다.
2. **Given** factory sidecar가 없거나 깨짐, **When** promotion scan workflow가 실행됨, **Then** raw evolution backlog로 fallback하고 실패를 조용히 숨기지 않는다.
3. **Given** factory workflow가 정상 실행됨, **When** pipeline liveness가 확인함, **Then** `candidate-implementation-factory`가 비핵심 감시 대상으로 표시된다.

### Edge Cases

- candidate backlog가 없거나 JSON이 깨졌으면 빈 결과를 publish하되 tracked 상태 파일을 직접 바꾸지 않는다.
- 후보가 live strategy, caps, whitelist, sentinels, broker order를 요구하면 자동 실행 패키지는 만들지 않고 operator review 또는 blocked로 남긴다.
- 결과 JSON이 후보 ID를 알 수 없거나 필수 검증 필드를 누락하면 `promotion_evidence`를 통과로 채우지 않는다.
- 같은 입력은 같은 패키지 ID와 같은 enriched backlog를 만든다.
- package command는 repo 내부의 읽기 전용 또는 paper/backtest 명령만 허용한다.

## Requirements

### Functional Requirements

- **FR-001**: System MUST parse candidate backlog and promotion summary inputs without requiring broker secrets.
- **FR-002**: System MUST create one implementation package per candidate and never silently drop a candidate.
- **FR-003**: System MUST classify candidates into deterministic package kinds using domain, title, risk, safety impact, and evidence fields.
- **FR-004**: System MUST generate runnable command plans only from existing vetted CLI/probe surfaces.
- **FR-005**: System MUST not mark `historical_backtest`, `recent_oos`, or `walk_forward` as `pass` unless machine-readable result evidence satisfies the required fields.
- **FR-006**: System MUST produce an enriched candidate backlog that preserves every original candidate field and only adds `promotion_evidence` keys.
- **FR-007**: System MUST publish Korean markdown and JSON sidecar artifacts for every run.
- **FR-008**: System MUST provide a CLI command and probe script for local and workflow execution.
- **FR-009**: System MUST run in GitHub Actions between autonomous evolution and autonomous promotion.
- **FR-010**: System MUST update autonomous promotion evidence collection to prefer factory enriched backlog and fallback safely.
- **FR-011**: System MUST classify non-strategy factory packages separately from strategy `BACKTEST_REQUIRED` candidates.
- **FR-012**: System MUST register the new sidecar in pipeline liveness as non-critical.
- **FR-013**: System MUST register the new CLI command in the safety command registry with no order placement, no live config change, no capital scaling, no broker use, and no DB writes.
- **FR-014**: System MUST not weaken constitution principles I-VII, VIII.A, IX, X, or the `Backtest -> Canary -> Full` sequence.

### Key Entities

- **Implementation Package**: Candidate-specific execution plan with package kind, commands, required inputs, produced evidence keys, status, and safety note.
- **Evidence Result**: Machine-readable result keyed by candidate ID with `historical_backtest`, `recent_oos`, `walk_forward`, source refs, and optional forward track configuration.
- **Promotion Patch**: Candidate-local `promotion_evidence` additions derived from package status and evidence result.
- **Factory Run**: One deterministic execution over candidate backlog and optional results, producing packages, enriched backlog, and summary artifacts.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Current nine autonomous candidates all receive implementation packages in unit tests.
- **SC-002**: A strategy candidate with all three passing result fields becomes `FORWARD_REGISTRATION_READY` when the enriched backlog is fed to promotion scan.
- **SC-003**: Missing or failed result evidence never creates a false `pass`.
- **SC-004**: Non-strategy candidates with factory packages are shown as `FACTORY_PACKAGE_READY`, not misleading strategy backtest work.
- **SC-005**: Workflow regression tests prove the factory runs before promotion scan and promotion scan prefers enriched backlog.
- **SC-006**: Full `uv run pytest` and `uv run ruff check src tests` pass before merge.

## Assumptions

- The factory can plan and merge evidence automatically, but it does not invent a profitable strategy or fabricate market results.
- Heavy historical data collection may happen in separate data workflows. When data is absent, the package remains `pending` with exact missing inputs.
- Strategy candidates can only move toward forward registration after historical, recent out-of-sample, and walk-forward evidence are all machine-verified.
- Non-trading candidates still get implementation packages, but they do not bypass the strategy promotion ladder.
