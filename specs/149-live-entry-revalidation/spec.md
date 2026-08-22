# Feature Specification: 최신 엣지 재검증과 병렬 탐색

**Feature Branch**: `Codex/149-live-entry-revalidation-parallel-edge`
**Created**: 2026-08-22
**Status**: In Progress
**Risk Grade**: 4 - 실제 주문 직전 자격 판정과 자동 무장 해제를 변경

## User Scenarios & Testing

### User Story 1 - 오래된 첫 주문 승인을 차단한다 (Priority: P1)

운영자는 탐색 캐너리가 과거에 합격했더라도 전략 체결이 아직 0건이면, 실제 주문 직전에 최신 홀드아웃·전진 성과·강화 캐너리·전략 지문을 다시 확인하기를 원한다.

**Independent Test**: 단 1이 무장돼 있어도 전략 체결 0건과 최신 `exploration_canary_ready=false`를 입력하면 주문 전 단계가 실패하고 주문은 0건이다. 최신 증거가 모두 통과하면 기존 시장·현금·한도 게이트로 진행한다.

**Acceptance Scenarios**:
1. **Given** 첫 전략 체결 0건과 최신 PSR 0.80 미만, **When** 예약 주문이 시작되면, **Then** 서명·브로커 주문 전에 차단한다.
2. **Given** 첫 전략 체결 0건과 최신 탐색 자격 및 강화 캐너리 PASS, **When** 예약 주문이 시작되면, **Then** 기존 주문 게이트로 진행한다.
3. **Given** 단 1, 체결 0건, 최신 탐색 자격 실패, **When** 자본 사다리가 재평가되면, **Then** 단 0으로 자동 강등해 무장을 해제한다.
4. **Given** 이미 전략 체결이 존재함, **When** 재검증하면, **Then** 매도·위험 축소를 막지 않고 기존 라이브 낙폭·정합성 게이트를 적용한다.

### User Story 2 - 감시 오탐을 복구한다 (Priority: P1)

운영자는 수익 증거 sidecar가 실제로 존재하는데 감시기가 `MISSING`으로 보고하지 않기를 원한다.

**Independent Test**: 와일드카드 fetch 뒤 첫 조회가 실패해도 해당 sidecar ref를 직접 다시 fetch해 수집하며, 실제 누락일 때만 `MISSING`이다.

### User Story 3 - 실거래 관찰과 신규 엣지 탐색을 병렬화한다 (Priority: P1)

운영자는 현재 전략의 forward 판정이 미달이어도 다음 자료만 기다리지 않고, 주문과 분리된 신규 후보 탐색을 계속하기를 원한다.

**Independent Test**: `HOLDOUT_EDGE`이지만 forward 미달인 수익 증거를 입력하면 관찰 패킷과 별도로 no-live challenger가 `EXECUTION_READY`로 선택된다. 같은 증거 주기의 완료 후보는 반복하지 않는다.

### User Story 4 - 주문 뒤 증거를 닫는다 (Priority: P2)

운영자는 주문 시도 뒤 체결 동기화, 전략 손익, 계좌 정합성, halt 상태가 한 실행 보고에 남기를 원한다.

**Independent Test**: 주문 성공·실패와 무관하게 체결 동기화, 측정, 정합성 복구 점검이 실행되고 sidecar에 각 결과가 남는다.

## Requirements

- **FR-001**: 전략 체결이 0건인 단 1은 매 실제 주문 직전 최신 탐색 자격을 다시 확인해야 한다.
- **FR-002**: 재검증은 역사 홀드아웃 통과, forward 관측 40개 이상, PSR 0.80 이상, Calmar 우위, 강화 캐너리 PASS를 모두 요구해야 한다.
- **FR-003**: 증거 누락·손상·오래됨·모순은 주문 전에 fail-closed 해야 한다.
- **FR-004**: 첫 체결 전 최신 자격이 실패하면 자본 사다리는 단 1을 단 0으로 자동 강등해야 한다.
- **FR-005**: 이미 체결된 전략은 주문 전 재검증 실패만으로 위험 축소 거래까지 막지 않고 기존 라이브 손실·정합성 게이트를 유지해야 한다.
- **FR-006**: pipeline 감시기는 일괄 수집 실패 시 개별 ref를 한 번 직접 재수집해야 한다.
- **FR-007**: forward 미달은 관찰 상태로 기록하되, 별도의 no-live challenger 후보 생성을 막지 않아야 한다.
- **FR-008**: challenger는 최소 5개 새 독립 관측 단위의 증거 지문으로 중복을 억제해야 한다.
- **FR-009**: challenger는 브로커 호출·실제 주문·자본 배분·live 전략 변경을 수행하지 않아야 한다.
- **FR-010**: 주문 시도 뒤 체결 동기화, 전략 손익 측정, 계좌 정합성 점검을 수행하고 결과를 추가 전용 증거에 남겨야 한다.
- **FR-011**: K1 한도, K2 whitelist, 손실 예산 20%, 정규장, 현금 1% 여유, production 서명, 감사 로그를 유지해야 한다.

## Success Criteria

- **SC-001**: 첫 체결 0건과 최신 PSR 0.80 미만인 모든 시험에서 실제 주문 제출은 0건이다.
- **SC-002**: 첫 체결 전 자격 실패는 자동으로 단 0 무장 해제 결정을 만든다.
- **SC-003**: 존재하는 수익 증거 sidecar의 감시 결과는 `MISSING`이 아니다.
- **SC-004**: forward 미달 상태에서도 중복되지 않은 no-live challenger가 자동 선택된다.
- **SC-005**: 주문 실행 보고는 체결, 손익, 정합성 결과를 모두 포함한다.
- **SC-006**: 전체 pytest, ruff, strict 하네스, HANDOFF 사실 검증, PR 품질 관문을 통과한다.

## Assumptions

- 첫 전략 체결 여부는 전략 범위 측정 계약의 `fills_count`를 사용한다.
- 이미 체결된 전략의 위험 축소는 최신 연구 점수보다 기존 손실·정합성 안전장치를 우선한다.
- challenger 주기는 forward 관측 5개 단위로 묶어 같은 자료의 반복 작업을 막는다.

## Out of Scope

- PSR 0.80 또는 0.95 기준 완화.
- 허용 종목·포지션 한도·손실 예산 확대.
- 신규 후보를 검증 없이 live로 교체.
