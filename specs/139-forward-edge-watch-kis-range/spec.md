# Feature Specification: Forward Edge Watch and KIS Range Query

**Feature Branch**: `codex/forward-edge-watch-kis-range`
**Created**: 2026-08-16
**Status**: Complete

## User Scenarios & Testing

### User Story 1 - 최근 주문을 적은 호출로 빠짐없이 확인하기 (Priority: P1)

운영자는 KIS 최근 주문 검사가 휴장일 단일 날짜 조회 때문에 실패하지 않으면서도, 어느 거래소의 조회 실패도 정상으로 숨기지 않기를 원한다.

**Independent Test**: 최근 7일을 시작일과 종료일 범위 한 번으로 각 거래소에 조회하고, 한 거래소라도 오류면 전체 호출이 실패하는지 확인한다.

### User Story 2 - 역사 엣지의 전진 검증을 자율 추적하기 (Priority: P1)

운영자는 `HOLDOUT_EDGE` 후보가 있는데도 자율 작업 루프가 일반적인 새 증거 대기로 돌아가지 않고, 후보명·관측 수·현재 PSR·기준을 명시적으로 추적하기를 원한다.

**Independent Test**: `FORWARD_VALIDATION` 수익 증거를 입력하면 `wait-for-globalfixed-forward-edge`가 선택되고, forward 통과 입력이면 주문 후보가 아닌 `candidate-globalfixed-promotion-recheck`가 선택된다.

### Edge Cases

- 종료일이 시작일보다 이르면 네트워크 요청 전에 거부한다.
- NASD, NYSE, AMEX 중 하나라도 실패하면 결과 일부를 성공으로 반환하지 않는다.
- profit-evidence sidecar가 없거나 손상되면 기존 일반 대기 또는 생존 복구 동작을 유지한다.
- 역사 검증만 통과하고 forward가 미달이면 코드 작업이나 주문을 시작하지 않는다.
- forward가 통과해도 기존 다중검정, 전략 지문, hardened canary, 자본 사다리를 재확인할 뿐 주문하지 않는다.

## Requirements

- **FR-001**: `get_order_executions`는 선택적 종료일을 받아 `ORD_STRT_DT`와 `ORD_END_DT`를 전달해야 한다.
- **FR-002**: 종료일 기본값은 시작일이어야 하며 기존 단일일 호출 동작을 보존해야 한다.
- **FR-003**: 종료일이 시작일보다 이르면 API 호출 전에 `ValueError`를 발생시켜야 한다.
- **FR-004**: 최근 주문 live smoke는 최근 7일을 날짜별 7회가 아니라 범위 1회로 조회해야 한다.
- **FR-005**: 멀티 거래소 조회는 한 거래소 오류도 전파하는 fail-closed 동작을 유지해야 한다.
- **FR-006**: autonomous-work manifest는 `profit-evidence-engine` JSON sidecar를 수집해야 한다.
- **FR-007**: 역사 통과·forward 미달이면 후보명, 관측 수, PSR, 기준을 포함한 `OBSERVATION_WAIT` 패킷을 발행해야 한다.
- **FR-008**: forward 통과이면 `EXECUTION_READY` 승격 재검토 패킷을 발행하되 주문·자본 변경을 요구해서는 안 된다.
- **FR-009**: 누락·손상 sidecar는 기존 fallback 동작을 깨뜨리지 않아야 한다.
- **FR-010**: 실제 주문, 자본 배분, whitelist/caps, 비밀값, 감사 로그, 헌법, kernel을 변경해서는 안 된다.

## Success Criteria

- **SC-001**: 최근 7일 주문 smoke의 주문내역 요청 수가 21회에서 거래소별 3회로 줄어든다.
- **SC-002**: 거래소 하나의 HTTP 500 입력에서 전체 조회는 100% 실패한다.
- **SC-003**: 현재 sidecar 재생에서 `wait-for-globalfixed-forward-edge`, 관측 41, PSR 0.82727, 기준 0.95가 보고된다.
- **SC-004**: forward 통과 fixture는 실주문 없이 승격 재검토 패킷을 만든다.
- **SC-005**: 전체 pytest, ruff, 엄격 하네스, HANDOFF 사실 검증을 통과한다.

## Safety

위험 등급은 3이다. 브로커의 읽기 전용 주문내역 검사를 바꾸므로 안전 검증 표면에 닿지만 주문 제출·취소 경로는 바꾸지 않는다. KIS 오류는 계속 fail-closed이며 `Backtest -> Canary -> Full`은 유지한다.

completed_candidate_id: candidate-forward-edge-watch-kis-range
next_candidate_id: wait-for-globalfixed-forward-edge
