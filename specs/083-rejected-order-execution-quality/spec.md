# Feature Specification: Rejected Order Execution Quality Package

**Feature Branch**: `Codex/083-rejected-order-execution-quality`
**Created**: 2026-07-02
**Status**: Draft
**Input**: User description: "새로 시작할 수 있는 다음 작업을 목표 스킬로 꼼꼼하게 진행해줘" and autonomous work packet `candidate-dff4f9344b02`.

## User Scenarios & Testing

### User Story 1 - 실행 품질 증거를 한 패키지로 본다 (Priority: P1)

운영자는 거부 주문 기회손익, 누적 monitor verdict, 브로커 거부 코드, KIS smoke 상태를 여러 sidecar에서 따로 찾지 않고 하나의 읽기 전용 실행 품질 패키지로 보고 싶다.

**Why this priority**: 064번 스펙은 거부 주문 손익을 만들었지만, 자율 성장 후보가 같은 증거를 독립 실행 품질 표면으로 소비하지 못하면 다음 세션이 같은 원인을 다시 조사하게 된다.

**Independent Test**: `opportunity_monitor.json`, `opportunity_history.json`, micro GTAA `LAST_RUN.md`, KIS smoke `LAST_RUN.md`를 입력하면 probe가 `execution_quality.json`과 Markdown 요약을 생성한다.

**Acceptance Scenarios**:

1. **Given** 최신 monitor가 `INTENT_LOSS`와 누적 손익을 담고 있음, **When** 실행 품질 probe가 실행됨, **Then** JSON에는 verdict, 최신 신호, 누적 손익, 다음 조치가 기록된다.
2. **Given** history row의 broker reason에 KIS 거부 코드가 있음, **When** probe가 실행됨, **Then** 코드별 거부 관측 수와 거부 주문 내 브로커 오류 관측률이 기록된다.
3. **Given** KIS smoke가 성공함, **When** probe가 실행됨, **Then** smoke 테스트 실패율은 0으로 기록되고 브로커 연결 자체가 정상임을 분리한다.

---

### User Story 2 - 자율 성장 루프가 실행 품질 표면을 소비한다 (Priority: P1)

운영자는 자율 성장 루프가 실행 품질 후보를 고를 때 일반 micro GTAA `LAST_RUN.md`뿐 아니라 독립 `execution-quality` sidecar도 근거로 삼기를 원한다.

**Why this priority**: 후보 `candidate-dff4f9344b02`의 목적은 "증거 패키징"이다. 패키지가 만들어져도 성장 루프 manifest와 후보 근거에 연결되지 않으면 완료 효과가 다음 루프에 남지 않는다.

**Independent Test**: evolution loop manifest와 후보 backlog가 `execution-quality` evidence ref를 포함하고, 해당 sidecar가 없거나 오래되면 후보가 증거 신선도 의존 상태가 된다.

**Acceptance Scenarios**:

1. **Given** 신선한 `execution-quality` sidecar가 있음, **When** evolution scan이 실행됨, **Then** 실행 품질 후보의 근거에는 `execution-quality`가 포함된다.
2. **Given** `execution-quality` sidecar가 없음, **When** evolution scan이 실행됨, **Then** 후보는 계속 보이지만 `sidecar_freshness` 의존으로 낮아진다.
3. **Given** 실행 품질 패키지가 `STRATEGY_REVIEW` 또는 `EXECUTION_REVIEW` 신호를 담음, **When** evolution scan이 실행됨, **Then** 후보 요약은 실행 품질 근거를 구조화 신호로 읽는다.

---

### User Story 3 - 새 sidecar의 생존을 감시한다 (Priority: P2)

운영자는 새 실행 품질 패키징 workflow가 조용히 멈추면 pipeline liveness에서 저하로 드러나기를 원한다.

**Why this priority**: 보고 전용 sidecar라도 멈추면 다음 자율 작업 선택이 오래된 실행 품질 근거에 기대게 된다. 돈 경로 핵심은 아니므로 빨간 핵심 실패가 아니라 비핵심 저하로 드러나야 한다.

**Independent Test**: `pipeline_liveness.default_specs()`가 `execution-quality`를 비핵심 sidecar로 등록하고, probe manifest가 해당 branch와 파일을 포함한다.

**Acceptance Scenarios**:

1. **Given** `execution-quality` sidecar가 신선함, **When** liveness가 실행됨, **Then** 해당 check는 OK다.
2. **Given** 첫 실행 예정 전 또는 직후임, **When** sidecar가 아직 없음, **Then** 거짓 핵심 실패를 만들지 않는다.
3. **Given** 첫 실행 예정과 허용 시간이 지난 뒤 sidecar가 없음, **When** liveness가 실행됨, **Then** 비핵심 DEGRADED로 드러난다.

### Edge Cases

- `opportunity_history.json`이 없거나 손상되면 주문·자본 변경 없이 `MISSING_EVIDENCE` 또는 malformed evidence로 기록한다.
- broker reason이 JSON 문자열이 아니어도 probe는 실패하지 않고 파싱 실패 수를 기록한다.
- KIS smoke 출력 형식이 바뀌어 테스트 수를 못 읽으면 smoke 상태와 원문 존재만 기록한다.
- 민감값처럼 보이는 계좌번호, 토큰, Authorization 값은 출력하지 않는다.
- 이 feature는 주문 재시도, 주문 취소, 전략 교체, 자본 배분, whitelist/caps 변경을 절대 하지 않는다.

## Requirements

### Functional Requirements

- **FR-001**: System MUST build a deterministic `execution_quality.json` from already published sidecars only.
- **FR-002**: System MUST include rejected-order monitor verdict, latest signal, cumulative intended-order mark PnL, valued record count, and next action.
- **FR-003**: System MUST summarize broker rejection evidence from opportunity history rows without exposing raw account values or full broker payload bodies.
- **FR-004**: System MUST compute an observed broker rejection error rate within rejected opportunity rows when counts are available.
- **FR-005**: System MUST summarize latest KIS smoke state and smoke test failure rate when the smoke sidecar exposes enough text to infer it.
- **FR-006**: System MUST publish `LAST_RUN.md` and `execution_quality.json` to `automation/execution-quality-last-run`.
- **FR-007**: Autonomous evolution MUST include `execution-quality` in its manifest and execution-quality candidate evidence refs.
- **FR-008**: Pipeline liveness MUST include `execution-quality` as non-critical freshness monitoring.
- **FR-009**: The workflow and probe MUST NOT call broker APIs, SSH, KIS secrets, order commands, capital commands, PR commands, or merge commands.
- **FR-010**: The completed Speckit contract MUST mark `candidate-dff4f9344b02` as completed so `released-work` can suppress repeat selection after merge.

### Key Entities

- **Execution Quality Package**: Machine-readable JSON and Markdown summary combining opportunity monitor, opportunity history, micro live gate, and KIS smoke evidence.
- **Broker Rejection Summary**: Aggregated KIS rejection codes, exception types, and observed error rate derived from already recorded rejected order rows.
- **Broker Smoke Summary**: Latest KIS smoke state and inferred smoke test pass/fail counts from the smoke sidecar.
- **Evolution Evidence Surface**: `execution-quality` sidecar entry consumed by autonomous evolution.

## Success Criteria

- **SC-001**: Unit tests prove the execution quality package summarizes monitor, history, broker code distribution, and smoke failure rate.
- **SC-002**: Integration tests prove the probe manifest, JSON output, Markdown output, and workflow read-only contract.
- **SC-003**: Evolution loop tests prove `candidate-dff4f9344b02` keeps a stable id while adding `execution-quality` evidence and freshness dependency handling.
- **SC-004**: Pipeline liveness tests prove `execution-quality` is registered as non-critical.
- **SC-005**: Full `uv run pytest`, `uv run ruff check src tests`, `scripts/check_handoff_facts.py`, and strict agent harness pass before merge.

## Assumptions

- Existing 064번 monitor semantics remain authoritative for strategy/execution verdicts.
- KIS smoke is a broker connectivity health signal, not proof that a rejected order would now be accepted.
- Broker rejection rate here is an observation over rejected opportunity rows, not a whole-account broker availability statistic.
