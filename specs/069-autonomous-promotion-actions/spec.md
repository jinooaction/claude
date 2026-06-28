# Feature Specification: Autonomous Promotion Actions

**Feature Branch**: `Codex/autonomous-promotion-actions`  
**Created**: 2026-06-29  
**Status**: Draft  
**Input**: User description: "남은 범위 모두 목표 스킬 사용해서 남김없이 세계 최고 수준으로 구현 배포해줘"

## User Scenarios & Testing

### User Story 1 - forward paper 등록까지 자동 연결 (Priority: P1)

자율 승격 루프가 `FORWARD_REGISTRATION_READY` 후보를 발견하면 사람이 다시 해석하지 않아도, 후보가 제공한 기계 판독 설정을 검증해 promotion 전용 forward paper 레지스트리에 등록한다.

**Why this priority**: 후보 발굴과 승격 판단 다음의 가장 큰 공백은 "어떤 후보를 실제 forward 관측에 태울지"를 사람이 옮기는 구간이다. 이 구간을 자동화해야 자율 성장 루프가 계속 전진한다.

**Independent Test**: `promotion_actions` 순수 코어에 `FORWARD_REGISTRATION_READY` 후보와 유효한 `forward_track` 증거를 넣으면 신규 레지스트리 항목이 생기고, 같은 후보를 다시 넣으면 중복 등록이 아니라 `already_registered`가 나온다.

**Acceptance Scenarios**:

1. **Given** 승격 요약에 `FORWARD_REGISTRATION_READY` 후보가 있고 `promotion_evidence.forward_track`이 유효함, **When** promotion action 루프가 실행됨, **Then** `promotion-forward-registry.json` 다음 상태에 해당 후보의 paper 트랙이 추가된다.
2. **Given** 같은 후보 또는 같은 `track_key`가 이미 레지스트리에 있음, **When** promotion action 루프가 다시 실행됨, **Then** 중복 없이 `already_registered`로 보고한다.
3. **Given** 후보가 forward track 설정을 누락하거나 위험한 경로를 제공함, **When** promotion action 루프가 실행됨, **Then** 등록하지 않고 누락 필드와 차단 사유를 남긴다.

---

### User Story 2 - canary 검증 제출까지 자동 연결 (Priority: P2)

자율 승격 루프가 `CANARY_CANDIDATE` 후보를 발견하면 사람이 수동으로 옮기지 않아도 promotion 전용 canary 제출 큐에 등록하고, 별도 워크플로가 hardened canary 검증을 실행한다.

**Why this priority**: 백테스트와 forward paper는 전략 품질을 줄여 보지만, 실계좌 전환 전에는 브로커 실행 경로와 운영 제약을 검증하는 canary 관문이 필요하다. 이 관문에 후보를 넣는 반복 작업을 자동화한다.

**Independent Test**: `CANARY_CANDIDATE` 후보와 유효한 `canary_track` 증거를 넣으면 canary 제출 상태 파일에 `pending` 제출이 생기고, 워크플로 텍스트 검증은 실주문 명령이 없음을 보장한다.

**Acceptance Scenarios**:

1. **Given** 승격 요약에 `CANARY_CANDIDATE` 후보가 있고 `promotion_evidence.canary_track`이 유효함, **When** promotion action 루프가 실행됨, **Then** `promotion-canary-submissions.json` 다음 상태에 `pending` 제출이 추가된다.
2. **Given** canary 제출 큐가 비어 있지 않음, **When** promotion canary 워크플로가 실행됨, **Then** 각 제출에 대해 `auto-invest canary-portfolio`를 실행하고 결과 사이드카를 발행한다.
3. **Given** 후보가 실제 주문 또는 자본 증액을 요구함, **When** promotion action 루프가 실행됨, **Then** 실거래 sentinel, live 설정, 자본 사다리를 수정하지 않는다.

---

### User Story 3 - 실행 자동화 생존 감시와 인계 (Priority: P3)

운영자와 다음 세션은 promotion action, promotion forward, promotion canary 자동화가 마지막으로 언제 실행됐는지 한 곳에서 확인할 수 있다.

**Why this priority**: 자동화는 만든 뒤 조용히 멈추는 순간 가치가 사라진다. 연구/검증 루프라도 침묵 정지는 드러나야 한다.

**Independent Test**: `pipeline_liveness.default_specs()`에 세 신규 사이드카가 비핵심으로 등록되고, 각 워크플로가 `LAST_RUN.md`를 publish한다.

**Acceptance Scenarios**:

1. **Given** 신규 워크플로가 정상 실행됨, **When** liveness probe가 사이드카를 읽음, **Then** `autonomous-promotion-actions`, `promotion-forward`, `promotion-canary`가 상태 표에 포함된다.
2. **Given** 신규 연구 자동화가 지연됨, **When** liveness probe가 판정함, **Then** 돈 경로를 빨간 실패로 만들지 않고 `DEGRADED`로 드러낸다.

### Edge Cases

- 승격 요약 파일이 없거나 깨졌으면 레지스트리 파일을 수정하지 않고 `degraded` summary를 쓴다.
- 후보가 `../`, 절대경로, live sentinel, 기본 live halt 경로를 지정하면 자동 제출하지 않는다.
- 기존 registry/submission 파일이 깨졌으면 안전하게 빈 상태로 덮지 않고 실행 실패로 드러낸다.
- 레지스트리 항목이 0개면 forward/canary 워크플로는 성공적으로 "할 일 없음" 사이드카를 발행한다.
- 같은 후보가 forward와 canary 둘 다 준비됐다고 표시되면 현재 stage에 맞는 하나의 행동만 수행한다.

## Requirements

### Functional Requirements

- **FR-001**: System MUST read the latest promotion summary JSON and derive deterministic action proposals from candidate stages.
- **FR-002**: System MUST append valid `FORWARD_REGISTRATION_READY` candidates to a promotion-only forward registry without duplicating candidate IDs or track keys.
- **FR-003**: System MUST append valid `CANARY_CANDIDATE` candidates to a promotion-only canary submission queue without duplicating candidate IDs.
- **FR-004**: System MUST validate candidate-provided paths and reject absolute paths, parent-directory traversal, live sentinel paths, and non-promotion DB/halt paths.
- **FR-005**: System MUST publish machine-readable JSON and Korean markdown summaries for every action run.
- **FR-006**: System MUST provide a CLI command and probe script that can run locally and in GitHub Actions.
- **FR-007**: System MUST add a workflow that turns promotion action decisions into tracked registry/submission updates through a pull request path, not direct main mutation.
- **FR-008**: System MUST add a promotion forward workflow that executes registered tracks only in `--mode paper` and publishes a sidecar.
- **FR-009**: System MUST add a promotion canary workflow that executes hardened canary validation and publishes a sidecar without touching `rebalance-live.request`, live config, or capital ladder sentinels.
- **FR-010**: System MUST register all new automation sidecars in pipeline liveness as non-critical monitored tracks.
- **FR-011**: System MUST register the new CLI command in the safety command registry with no order placement, no live config change, no capital scaling, no broker use, and no DB writes unless explicitly performed by downstream paper/canary commands.
- **FR-012**: System MUST not weaken constitution principles I-VII, VIII.A, IX, X, or the `Backtest -> Canary -> Full` sequence.

### Key Entities

- **Promotion Action Run**: One deterministic execution over a promotion summary, producing action records, next registry state, next canary submission state, and markdown/JSON artifacts.
- **Forward Track Registration**: A promotion-only paper track with candidate ID, track key, portfolio path, DB path, halt path, capital, and data-depth settings.
- **Canary Submission**: A promotion-only hardened canary request with candidate ID, portfolio path, DB path, halt path, bands config, and submission status.
- **Action Block**: A rejected action with machine-readable reason and Korean operator explanation.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A valid forward-ready fixture produces exactly one new forward registration and is idempotent on repeat.
- **SC-002**: A valid canary-ready fixture produces exactly one new canary submission and is idempotent on repeat.
- **SC-003**: Workflow regression tests prove promotion forward commands contain `--mode paper` and no promotion workflow contains `--mode live` or `--confirm-live`.
- **SC-004**: Liveness registry includes all three new sidecars and marks them non-critical.
- **SC-005**: Full test and lint pass before merge.

## Assumptions

- 실제 실주문 실행은 이번 스펙의 목표가 아니다. 기존 `rebalance-live-canary.yml`, 자본 사다리, 재지정 게이트만 실거래 경로를 통제한다.
- 후보가 실제 실행 가능한 portfolio를 만들려면 `promotion_evidence.forward_track` 또는 `promotion_evidence.canary_track`에 기계 판독 설정을 제공해야 한다.
- Promotion 전용 registry/submission 파일은 tracked JSON으로 둔다. 자동 워크플로는 변경이 생기면 PR로 반영한다.
- 신규 자동화는 연구/검증 루프이므로 liveness에서는 비핵심으로 감시한다.
