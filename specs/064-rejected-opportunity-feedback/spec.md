# Feature Specification: Rejected Opportunity Feedback Loop

**Feature Branch**: `Codex/opportunity-strategy-loop`  
**Created**: 2026-06-26  
**Status**: Draft  
**Input**: User description: "거부된 주문이 정상 체결됐다면 지금 돈을 벌었는지 잃었는지 판단하고, 그 판단이 전략 평가와 자율 고도화 루프에 들어가야 한다."

## User Scenarios & Testing

### User Story 1 - 누적 전략 의도 손익을 본다 (Priority: P1)

운영자는 브로커가 거부한 주문을 단발 사건으로만 보지 않고, 그 주문들이 정상 체결됐다면 이후 가격 기준으로 이익이었는지 손실이었는지를 누적해서 보고 싶다.

**Why this priority**: 단일 거부 주문 보고는 "이번 주문이 안 됐다"는 사실을 알려 주지만, 전략이 내린 의도 자체가 돈을 벌었는지 잃었는지 판단하지 못하면 전략 개선 여부를 평가할 수 없다.

**Independent Test**: 여러 실행의 거부 주문 기회손익 JSON을 기록으로 누적했을 때, 시스템이 누적 전략 의도 손익, 최근 신호, 연속 손실/이익 신호, 검토 verdict를 계산한다.

**Acceptance Scenarios**:

1. **Given** 거부된 매수 주문의 현재가가 주문가보다 낮음, **When** 누적 평가가 실행됨, **Then** 해당 주문의 전략 의도 손익은 음수로 기록되고 최신 신호는 `INTENT_LOSS`가 된다.
2. **Given** 평가 가능한 거부 주문 기록이 최소 표본 수보다 적음, **When** 누적 verdict를 계산함, **Then** 시스템은 자동 전략 변경이 아니라 `INSUFFICIENT_DATA`를 반환한다.
3. **Given** 평가 가능한 기록이 충분하고 누적 전략 의도 손익이 손실 임계값 이하임, **When** 누적 verdict를 계산함, **Then** 시스템은 `STRATEGY_REVIEW`를 반환한다.

---

### User Story 2 - 자동 실행 루프가 같은 증거를 계속 갱신한다 (Priority: P1)

운영자는 매 micro GTAA 실행마다 최신 거부 주문 평가가 이전 기록에 붙고, 같은 사이드카에서 최신 누적 판단을 확인할 수 있기를 원한다.

**Why this priority**: 수동으로 JSON을 모아 해석해야 한다면 자율 루프가 아니다. 자동 워크플로가 반복 실행될 때마다 같은 계산을 수행하고 durable sidecar에 남겨야 다음 세션도 같은 결론을 재현할 수 있다.

**Independent Test**: micro GTAA 워크플로가 이전 `opportunity_history.json`을 읽고 새 `/tmp/micro_opportunity.json`을 추가한 뒤 `opportunity_monitor.json`을 발행하는지 검증한다.

**Acceptance Scenarios**:

1. **Given** 이전 사이드카에 `opportunity_history.json`이 있음, **When** micro GTAA 워크플로가 끝남, **Then** 새 실행 기록이 추가되고 최대 보존 건수 안에서 오래된 기록은 잘린다.
2. **Given** 이전 기록이 없음, **When** 첫 실행이 끝남, **Then** 빈 기록에서 시작해 정상 JSON을 발행한다.
3. **Given** 현재가 조회 실패나 평가 대상 0건이 발생함, **When** 워크플로가 끝남, **Then** 주문·사이드카·텔레그램 단계는 실패하지 않고 불충분한 증거로 표시한다.

---

### User Story 3 - 자율 재지정 루프가 신호를 입력으로 본다 (Priority: P2)

운영자는 전략 재지정 루프가 forward 토너먼트만 보지 않고, 실제 라이브 주문 의도가 손실 신호를 냈는지도 함께 볼 수 있기를 원한다.

**Why this priority**: 실제 라이브 의도 손익은 전략 품질을 평가하는 운영 증거다. 단, 이 증거 하나로 자동 교체하면 단일 사건 과적합이 되므로 기존 5중 게이트를 유지해야 한다.

**Independent Test**: `reassign-on-tournament.yml`이 micro GTAA sidecar의 `opportunity_monitor.json`을 읽어 `reassign-decide` 입력과 최신 재지정 사이드카에 포함하되, 기존 재지정 action은 5중 게이트만으로 결정되는지 검증한다.

**Acceptance Scenarios**:

1. **Given** 누적 verdict가 `STRATEGY_REVIEW`임, **When** 재지정 루프가 실행됨, **Then** 결정 JSON에는 execution feedback이 포함되지만 도전자·다중검정·캐너리 게이트 없이는 자동 교체하지 않는다.
2. **Given** 누적 verdict가 `EXECUTION_REVIEW`임, **When** 재지정 루프가 실행됨, **Then** 시스템은 전략 교체가 아니라 주문 실행 경로 검토 신호로 표시한다.

### Edge Cases

- `opportunity_pnl_usd` 문자열에 `+`, 쉼표, `USD`, 빈 값이 섞여도 파싱은 안전해야 한다.
- 이전 history JSON이 손상되었거나 없는 경우 새 history로 복구해야 한다.
- 거부 주문 수가 0이거나 현재가가 없어 평가 가능한 기록이 없으면 자동 전략 검토로 단정하지 않는다.
- 누적 평가와 텔레그램은 주문 재시도, 주문 취소, 자본 변경, 전략 파일 변경을 직접 수행하면 안 된다.
- 재지정 루프는 이 신호를 입력 증거로 기록하지만, 기존 5중 게이트를 우회하면 안 된다.

## Requirements

### Functional Requirements

- **FR-001**: System MUST maintain a rolling rejected-order opportunity history for micro GTAA runs.
- **FR-002**: System MUST compute cumulative intended-order mark PnL where positive means rejected orders would have been favorable and negative means rejection avoided a worse outcome.
- **FR-003**: System MUST classify the latest valued signal as `INTENT_GAIN`, `INTENT_LOSS`, or `FLAT_OR_UNVALUED`.
- **FR-004**: System MUST emit a monitor verdict among `NO_VALUED_REJECTIONS`, `INSUFFICIENT_DATA`, `OBSERVE`, `STRATEGY_REVIEW`, and `EXECUTION_REVIEW`.
- **FR-005**: `STRATEGY_REVIEW` MUST mean the strategy intent has enough negative cumulative evidence to require review, not that live strategy is automatically replaced.
- **FR-006**: `EXECUTION_REVIEW` MUST mean rejected orders likely missed gains and execution/broker path needs review, not that strategy is bad.
- **FR-007**: The micro GTAA workflow MUST publish `opportunity_history.json` and `opportunity_monitor.json` to `automation/rebalance-micro-gtaa-last-run`.
- **FR-008**: Telegram micro GTAA alerts MUST include a readable cumulative strategy/execution verdict section.
- **FR-009**: The autonomous reassignment workflow MUST read the latest `opportunity_monitor.json` and include it in `reassign-decide` output and sidecar evidence.
- **FR-010**: The feature MUST NOT place, retry, cancel, or alter orders; change capital; change whitelists; change caps; or change strategy config by itself.

### Key Entities

- **Opportunity History**: Rolling JSON document with run metadata and the rejected-order opportunity report for each micro GTAA execution.
- **Opportunity Monitor Summary**: Cumulative verdict and metrics derived from the history.
- **Execution Feedback Input**: Read-only monitor summary attached to the autonomous reassignment decision artifact.

## Success Criteria

- **SC-001**: Unit tests prove positive/negative cumulative verdict classification and history capping.
- **SC-002**: CLI/script tests prove a new opportunity report can update history and emit monitor JSON without broker access.
- **SC-003**: Workflow tests prove micro GTAA publishes history/monitor files and Telegram includes cumulative verdict text.
- **SC-004**: Reassignment tests prove execution feedback is present in decision JSON without changing 5-gate action semantics.
- **SC-005**: Full `uv run pytest`, `uv run ruff check src tests`, handoff fact check, and strict agent harness pass before merge.

## Assumptions

- A rejected order's opportunity PnL is a diagnostic mark-to-current comparison, not accounting PnL.
- Minimum sample thresholds should be conservative because a single rejected order can be noise.
- Future work may add a stronger strategy improvement policy, but this feature only builds the durable measurement and evidence loop.
